from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

@app.route("/standings", methods=["GET", "POST"])
def standings():
    df = pd.read_csv("data/matches.csv")
    coaches_df = pd.read_csv("data/teams.csv")
    seasons = sorted(df["season"].unique())

    selected_from = request.form.get("season_from") or seasons[0]
    selected_to = request.form.get("season_to") or seasons[-1]
    mode = "goals" #mode = request.form.get("mode") or "goals"
    group_by = request.form.get("group_by") or "team"

    season_range = seasons[seasons.index(selected_from):seasons.index(selected_to)+1]
    df = df[df["season"].isin(season_range)]

    # Merge coach names
    df = pd.merge(df, coaches_df, how="left", left_on=["season", "team1"], right_on=["season", "team"])
    df = df.rename(columns={"coach": "coach1"})
    df = pd.merge(df, coaches_df, how="left", left_on=["season", "team2"], right_on=["season", "team"])
    df = df.rename(columns={"coach": "coach2"})

    stats = {}

    for _, row in df.iterrows():
        t1, t2 = row["team1"], row["team2"]
        c1, c2 = row.get("coach1"), row.get("coach2")
        key1 = c1 if group_by == "coach" else t1
        key2 = c2 if group_by == "coach" else t2

        if pd.isna(key1) or pd.isna(key2):
            continue

        for key in [key1, key2]:
            if key not in stats:
                stats[key] = {
                    "MP": 0, "W": 0, "D": 0, "L": 0,
                    "GF": 0, "GA": 0, "GD": 0, "Pts": 0,
                    "FPFor": 0, "FPAgainst": 0, "FPDiff": 0,
                    "FP Matches": 0, "FPW": 0, "FPD": 0, "FPL": 0
                }

        g1, g2 = row["goal1"], row["goal2"]
        stats[key1]["MP"] += 1
        stats[key2]["MP"] += 1
        stats[key1]["GF"] += g1
        stats[key1]["GA"] += g2
        stats[key2]["GF"] += g2
        stats[key2]["GA"] += g1

        if g1 > g2:
            stats[key1]["W"] += 1
            stats[key2]["L"] += 1
            stats[key1]["Pts"] += 3
        elif g1 < g2:
            stats[key2]["W"] += 1
            stats[key1]["L"] += 1
            stats[key2]["Pts"] += 3
        else:
            stats[key1]["D"] += 1
            stats[key2]["D"] += 1
            stats[key1]["Pts"] += 1
            stats[key2]["Pts"] += 1

        # Fantapunti logic
        if pd.notna(row["score1"]) and pd.notna(row["score2"]):
            s1, s2 = row["score1"], row["score2"]
            stats[key1]["FPFor"] += s1
            stats[key1]["FPAgainst"] += s2
            stats[key1]["FP Matches"] += 1
            stats[key1]["FPDiff"] += s1 - s2

            stats[key2]["FPFor"] += s2
            stats[key2]["FPAgainst"] += s1
            stats[key2]["FP Matches"] += 1
            stats[key2]["FPDiff"] += s2 - s1

            if s1 > s2:
                stats[key1]["FPW"] += 1
                stats[key2]["FPL"] += 1
            elif s1 < s2:
                stats[key2]["FPW"] += 1
                stats[key1]["FPL"] += 1
            else:
                stats[key1]["FPD"] += 1
                stats[key2]["FPD"] += 1

    standings = []
    for key, s in stats.items():
        s["Team"] = key
        s["GD"] = s["GF"] - s["GA"]
        s["FP"] = s["FPFor"]
        s["AvgPts"] = round(s["Pts"] / s["MP"], 2) if s["MP"] else 0
        s["AvgFP"] = round(s["FPFor"] / s["FP Matches"], 2) if s["FP Matches"] else 0
        standings.append(s)

    standings = sorted(standings, key=lambda x: (x["Pts"], x["GD"], x["GF"]), reverse=True)

    # Add this before render_template()
    df["matchday"] = pd.to_numeric(df["matchday"], errors="coerce")
    df = df.dropna(subset=["matchday"])

    df["matchday"] = df["matchday"].astype(int)

    points_timeline = {}

    for _, row in df.iterrows():
        entity1 = row["coach1"] if group_by == "coach" else row["team1"]
        entity2 = row["coach2"] if group_by == "coach" else row["team2"]
        g1, g2 = row["goal1"], row["goal2"]
        mday = row["matchday"]
        season = row["season"]

        if pd.isna(entity1) or pd.isna(entity2):
            continue

        for e in [entity1, entity2]:
            if e not in points_timeline:
                points_timeline[e] = {}

        # Determine results
        if g1 > g2:
            result = {entity1: 3, entity2: 0}
        elif g1 < g2:
            result = {entity1: 0, entity2: 3}
        else:
            result = {entity1: 1, entity2: 1}

        for entity in [entity1, entity2]:
            key = f"{season} - Giornata {mday:02d}"
            if key not in points_timeline[entity]:
                points_timeline[entity][key] = 0
            points_timeline[entity][key] += result[entity]

    # Prepare data for Plotly
    plot_data = []
    all_keys = sorted({k for data in points_timeline.values() for k in data.keys()})

    for entity, timeline in points_timeline.items():
        cumulative = []
        total = 0
        for k in all_keys:
            total += timeline.get(k, 0)
            cumulative.append(total)
        plot_data.append({"name": entity, "x": all_keys, "y": cumulative})


    return render_template("standings.html",
                           standings=standings,
                           seasons=seasons,
                           selected_from=selected_from,
                           selected_to=selected_to,
                           mode=mode,
                           group_by=group_by,
                           plot_data=plot_data)



@app.route("/head_to_head", methods=["GET", "POST"])
def head_to_head():
    df = pd.read_csv("data/matches.csv")
    coaches_df = pd.read_csv("data/teams.csv")
    seasons = sorted(df["season"].unique())

    selected_from = request.form.get("season_from") or seasons[0]
    selected_to = request.form.get("season_to") or seasons[-1]
    group_by = request.form.get("group_by") or "team"
    mode = request.form.get("mode") or "matrix"
    entity1 = request.form.get("entity1")
    entity2 = request.form.get("entity2")

    season_range = seasons[seasons.index(selected_from):seasons.index(selected_to) + 1]
    df = df[df["season"].isin(season_range)]

    # Merge coach names
    df = pd.merge(df, coaches_df, how="left", left_on=["season", "team1"], right_on=["season", "team"])
    df = df.rename(columns={"coach": "coach1"})
    df = pd.merge(df, coaches_df, how="left", left_on=["season", "team2"], right_on=["season", "team"])
    df = df.rename(columns={"coach": "coach2"})

    # Assign entity1 and entity2
    if group_by == "coach":
        df["entity1"] = df["coach1"]
        df["entity2"] = df["coach2"]
    else:
        df["entity1"] = df["team1"]
        df["entity2"] = df["team2"]

    df = df.dropna(subset=["entity1", "entity2"])
    df["matchday"] = pd.to_numeric(df["matchday"], errors="coerce").fillna(0).astype(int)

    entities = sorted(set(df["entity1"]).union(set(df["entity2"])))

    # Matrix data
    matrix_data = {
        e1: {e2: {"W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "SF": 0.0, "SA": 0.0, "N": 0} for e2 in entities}
        for e1 in entities
    }

    for _, row in df.iterrows():
        e1 = row["entity1"]
        e2 = row["entity2"]
        g1, g2 = row["goal1"], row["goal2"]
        s1, s2 = row.get("score1"), row.get("score2")

        for a, b, ga, gb, sa, sb in [(e1, e2, g1, g2, s1, s2), (e2, e1, g2, g1, s2, s1)]:
            if pd.isna(a) or pd.isna(b):
                continue
            data = matrix_data[a][b]
            data["GF"] += ga
            data["GA"] += gb
            if pd.notna(sa) and pd.notna(sb):
                data["SF"] += sa
                data["SA"] += sb
            data["N"] += 1
            if ga > gb:
                data["W"] += 1
            elif ga < gb:
                data["L"] += 1
            else:
                data["D"] += 1

    matrix = []
    for e1 in entities:
        row = {"entity": e1}
        for e2 in entities:
            if e1 == e2:
                row[e2] = "-"
                continue
            data = matrix_data[e1][e2]
            if data["N"] == 0:
                row[e2] = ""
            else:
                result = f"{data['W']}-{data['D']}-{data['L']}<br>{data['GF']}-{data['GA']}"
                if data["SF"] > 0 or data["SA"] > 0:
                    result += f"<br>{round(data['SF'],1)}-{round(data['SA'],1)}"
                row[e2] = result
        matrix.append(row)

    # Comparison mode
    comparison = []
    aggregate = {
        "matchday": None,
        "season": "TOTAL",
        "team1": entity1,
        "team2": entity2,
        "goal1": 0,
        "goal2": 0,
        "score1": 0.0,
        "score2": 0.0,
        "W": 0,
        "D": 0,
        "L": 0
    }

    if mode == "compare" and entity1 and entity2:
        filtered = df[((df["entity1"] == entity1) & (df["entity2"] == entity2)) |
                      ((df["entity1"] == entity2) & (df["entity2"] == entity1))]

        for _, row in filtered.iterrows():
            if row["entity1"] == entity1:
                g1, g2 = row["goal1"], row["goal2"]
                s1, s2 = row["score1"], row["score2"]
                t1, t2 = row["entity1"], row["entity2"]
            else:
                g1, g2 = row["goal2"], row["goal1"]
                s1, s2 = row["score2"], row["score1"]
                t1, t2 = row["entity2"], row["entity1"]

            comparison.append({
                "matchday": row["matchday"],
                "season": row["season"],
                "team1": t1,
                "goal1": g1,
                "goal2": g2,
                "team2": t2,
                "score1": s1,
                "score2": s2
            })

            # Aggregate update
            aggregate["goal1"] += g1
            aggregate["goal2"] += g2
            if pd.notna(s1) and pd.notna(s2):
                aggregate["score1"] += s1
                aggregate["score2"] += s2
            if g1 > g2:
                aggregate["W"] += 1
            elif g1 < g2:
                aggregate["L"] += 1
            else:
                aggregate["D"] += 1

        if comparison:
            aggregate["matchday"] = "-"
            comparison.sort(key=lambda x: (x["season"], x["matchday"]))
            comparison.append(aggregate)

    return render_template("head_to_head.html",
                           mode=mode,
                           seasons=seasons,
                           selected_from=selected_from,
                           selected_to=selected_to,
                           group_by=group_by,
                           entity1=entity1,
                           entity2=entity2,
                           entities=entities,
                           matrix=matrix,
                           comparison=comparison)

@app.route("/")
def homepage():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)


