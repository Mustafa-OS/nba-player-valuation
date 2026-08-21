"""
NBA Player Valuation Dashboard
Run with:  streamlit run app.py
"""
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from valuation import (
    DEFAULT_STAT_WEIGHTS, REQUIRED_COLS,
    compute_valuation, stat_percentiles_within_position,
)

st.set_page_config(page_title="NBA Player Valuation", layout="wide")

# Resolve relative to this file so the app works from any working directory.
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "players.csv")          # written by fetch_data.py (live data)
SAMPLE_FILE = os.path.join(HERE, "sample_players.csv")  # bundled fallback (approximate stats)


@st.cache_data
def load_data(path, mtime):
    # mtime is part of the cache key so a refreshed CSV invalidates the cache
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        st.error(f"{path} is missing columns: {missing}")
        st.stop()
    return df, os.path.basename(path)


_path = DATA_FILE if os.path.exists(DATA_FILE) else SAMPLE_FILE
df_raw, source = load_data(_path, os.path.getmtime(_path))

st.title("🏀 NBA Player Valuation")
st.caption(
    f"Data source: **{source}** · position-adjusted stats × age × availability. "
    "Run `fetch_data.py` for live numbers."
)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Model controls")

    view_label = st.radio(
        "Valuation view",
        ["Asset value", "Win-now"],
        help="Asset value = stats × age × availability (what the player is "
             "worth going forward — runway matters).\n"
             "Win-now = stats × availability (how good they are right now — "
             "age ignored).",
    )
    view = "asset" if view_label == "Asset value" else "win_now"

    positions = ["All"] + sorted(df_raw["POS"].unique().tolist())
    pos_filter = st.selectbox("Position filter", positions)

    st.subheader("Age curve")
    prime = st.slider("Prime age", 22, 32, 28)
    decline = st.slider("Decline / yr past prime", 0.0, 0.25, 0.10, 0.01,
                        help="Fraction of value lost per year beyond prime.")
    youth_bonus = st.slider("Youth upside / yr under prime", 0.0, 0.05, 0.02, 0.005,
                            help="Asset premium per year of runway before prime "
                                 "(capped at +15%).")
    elite_age_resistance = st.slider(
        "Elite age resistance", 0.0, 1.0, 0.5, 0.05,
        help="How much elite CURRENT production slows the age decline. At 0.5, "
             "a player still producing 2 SD above league average declines at "
             "half the base rate (LeBron/KD logic). Protection fades as the "
             "stats fade — it rewards sustained greatness, never reputation.")

    st.subheader("Availability")
    games_in_season = st.number_input("Games in season", 40, 82, 82)
    avail_exponent = st.slider("Injury penalty severity", 0.25, 1.0, 0.5, 0.05,
                               help="Exponent on games-played share. 1.0 = linear "
                                    "(harsh), 0.5 = square root (softer — per-game "
                                    "stats already earn nothing for missed games).")

    with st.expander("Advanced"):
        league_blend = st.slider(
            "League blend", 0.0, 0.5, 0.25, 0.05,
            help="Share of each z-score taken vs the whole league instead of "
                 "the position group. Damps noise from small/stacked position "
                 "groups; 0 = pure positional comparison.")
        st.caption("Stat weights")
        stat_weights = {}
        for stat, default in DEFAULT_STAT_WEIGHTS.items():
            stat_weights[stat] = st.slider(
                stat, -1.5, 1.5, float(default), 0.1, key=f"sw_{stat}"
            )

# ---------------------------------------------------------------- compute
ranked = compute_valuation(
    df_raw,
    stat_weights=stat_weights,
    view=view,
    prime=prime,
    decline=decline,
    youth_bonus=youth_bonus,
    elite_age_resistance=elite_age_resistance,
    games_in_season=games_in_season,
    avail_exponent=avail_exponent,
    league_blend=league_blend,
)

view = ranked if pos_filter == "All" else ranked[ranked["POS"] == pos_filter]
view = view.reset_index(drop=True)

if view.empty:
    st.warning("No players match the current filter.")
    st.stop()

# ---------------------------------------------------------------- top metrics
c1, c2, c3, c4 = st.columns(4)
top = view.iloc[0]
c1.metric("Top player", top["PLAYER"], f"{top['VALUE']:.1f}")
c2.metric("Players shown", len(view))
c3.metric("Median age", f"{view['AGE'].median():.0f}")
c4.metric("Median availability", f"{view['AVAIL_FACTOR'].median()*100:.0f}%")

# ---------------------------------------------------------------- table + bar
left, right = st.columns([1.15, 1])

with left:
    st.subheader("Rankings")
    show_cols = ["RANK", "PLAYER", "TEAM", "POS", "AGE", "GP", "MIN",
                 "STATS_SCORE", "AGE_FACTOR", "AVAIL_FACTOR", "VALUE"]
    show_cols = [c for c in show_cols if c in view.columns]
    st.dataframe(
        view[show_cols],
        column_config={
            "STATS_SCORE": st.column_config.NumberColumn("STATS_SCORE", format="%.0f"),
            "AGE_FACTOR": st.column_config.NumberColumn("AGE_FACTOR", format="%.2f"),
            "AVAIL_FACTOR": st.column_config.NumberColumn("AVAIL_FACTOR", format="%.2f"),
            "VALUE": st.column_config.ProgressColumn(
                "VALUE", format="%.1f", min_value=0.0,
                max_value=float(ranked["VALUE"].max()),
            ),
        },
        width="stretch", height=460, hide_index=True,
    )

with right:
    st.subheader("Top by value")
    if len(view) > 5:
        n = st.slider("Show top N", 5, min(25, len(view)), min(12, len(view)))
    else:
        n = len(view)
    bar = view.head(n).iloc[::-1]
    fig = px.bar(bar, x="VALUE", y="PLAYER", orientation="h", color="POS",
                 height=460, text="VALUE")
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig.update_layout(margin=dict(l=0, r=10, t=10, b=0),
                      yaxis=dict(title="", categoryorder="total ascending"),
                      xaxis_title="Value")
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- scatter
st.subheader("Age vs value")
sc = px.scatter(
    view, x="AGE", y="VALUE", color="POS", size="STATS_SCORE",
    hover_name="PLAYER", size_max=22, height=420,
    hover_data={"GP": True, "STATS_SCORE": ":.0f"},
)
sc.update_layout(margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(sc, width="stretch")

# ---------------------------------------------------------------- player card
st.subheader("Player breakdown (percentile vs positional peers)")
player = st.selectbox("Select player", view["PLAYER"].tolist())
pct = stat_percentiles_within_position(df_raw, player)

col_a, col_b = st.columns([1, 1])
with col_a:
    cats = list(pct.keys())
    vals = list(pct.values())
    radar = go.Figure()
    radar.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]], fill="toself", name=player
    ))
    radar.update_layout(polar=dict(radialaxis=dict(range=[0, 100])),
                        showlegend=False, height=380,
                        margin=dict(l=30, r=30, t=30, b=30))
    st.plotly_chart(radar, width="stretch")
with col_b:
    prow = ranked[ranked["PLAYER"] == player].iloc[0]
    st.metric("Overall value", f"{prow['VALUE']:.1f}", f"Rank #{int(prow['RANK'])} overall")
    st.write(f"**Position:** {prow['POS']}  |  **Age:** {int(prow['AGE'])}  |  "
             f"**GP:** {int(prow['GP'])}")
    st.write("Percentiles are computed **within position** "
             "(fewer turnovers scores higher).")
    st.dataframe(pd.DataFrame({"stat": list(pct.keys()),
                               "percentile": list(pct.values())}),
                 hide_index=True, width="stretch")
