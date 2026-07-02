"""
Pull live per-game stats from stats.nba.com (via nba_api) into players.csv,
which app.py will use automatically in place of the sample.

    python fetch_data.py --season 2024-25 --min-gp 15

Notes:
  * stats.nba.com sometimes rate-limits or blocks datacenter IPs. Run this on
    your own machine. If a call times out, re-run — results are written only
    on success. Sleeps are added between roster calls to stay polite.
  * Positions come from team rosters (G / F / C granularity). If you have a
    finer PG/SG/SF/PF/C source, overwrite the POS column and the model will
    group on it automatically.
"""
import argparse
import time
import sys
import pandas as pd

from nba_api.stats.endpoints import leaguedashplayerstats, commonteamroster
from nba_api.stats.static import teams


def true_shooting(pts, fga, fta):
    denom = 2.0 * (fga + 0.44 * fta)
    return (pts / denom).where(denom > 0, 0.0)


def fetch_positions(season, pause=0.6):
    """Map PLAYER_ID -> coarse position (G/F/C) from every team roster."""
    pos = {}
    for t in teams.get_teams():
        try:
            r = commonteamroster.CommonTeamRoster(
                team_id=t["id"], season=season, timeout=30
            ).get_data_frames()[0]
            for _, row in r.iterrows():
                p = str(row.get("POSITION", "") or "").split("-")[0].strip().upper()
                pos[row["PLAYER_ID"]] = p if p in {"G", "F", "C"} else "F"
            print(f"  roster ok: {t['abbreviation']}")
            time.sleep(pause)
        except Exception as e:
            print(f"  roster FAILED {t['abbreviation']}: {e}", file=sys.stderr)
    return pos


def prev_season(season):
    """'2024-25' -> '2023-24'"""
    start = int(season.split("-")[0]) - 1
    return f"{start}-{str(start + 1)[-2:]}"


def fetch_prev_gp(season):
    """Map PLAYER_ID -> GP for a season (for the multi-season durability signal)."""
    s = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season, per_mode_detailed="PerGame", timeout=60
    ).get_data_frames()[0]
    return dict(zip(s["PLAYER_ID"], s["GP"].astype(int)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2024-25")
    ap.add_argument("--min-gp", type=int, default=15)
    args = ap.parse_args()

    print(f"Fetching league per-game stats for {args.season} ...")
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=args.season, per_mode_detailed="PerGame", timeout=60
    ).get_data_frames()[0]

    df = stats[stats["GP"] >= args.min_gp].copy()

    print("Fetching positions from team rosters ...")
    pos_map = fetch_positions(args.season)

    out = pd.DataFrame({
        "PLAYER": df["PLAYER_NAME"],
        "TEAM":   df["TEAM_ABBREVIATION"],
        "POS":    df["PLAYER_ID"].map(pos_map).fillna("F"),
        "AGE":    df["AGE"].astype(int),
        "GP":     df["GP"].astype(int),
        "MIN":    df["MIN"],
        "PTS":    df["PTS"],
        "TRB":    df["REB"],
        "AST":    df["AST"],
        "STL":    df["STL"],
        "BLK":    df["BLK"],
        "TOV":    df["TOV"],
        "TS_PCT": true_shooting(df["PTS"], df["FGA"], df["FTA"]).round(3),
    })

    # Prior-season games played -> multi-season durability in the model.
    for i in range(1, 3):
        season_i = args.season
        for _ in range(i):
            season_i = prev_season(season_i)
        try:
            print(f"Fetching GP for {season_i} (durability) ...")
            # No fillna: rookies/absent players stay NaN so the model's
            # multi-season average skips them instead of counting a 0.
            gp_map = fetch_prev_gp(season_i)
            out[f"GP_PREV{i}"] = df["PLAYER_ID"].map(gp_map)
            time.sleep(1.0)
        except Exception as e:
            print(f"  skipping {season_i} GP: {e}", file=sys.stderr)

    out.to_csv("players.csv", index=False)
    print(f"Wrote players.csv ({len(out)} players). app.py will now use it.")


if __name__ == "__main__":
    main()
