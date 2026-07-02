# NBA Player Valuation Dashboard

Ranks NBA players from three factors — **position-adjusted stats**, **age**, and
**availability (injury proxy)** — in a runnable Streamlit dashboard.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. It runs immediately on a bundled sample of
real players with *approximate* stats. For accurate live numbers:

```bash
python fetch_data.py --season 2024-25 --min-gp 15
```

This writes `players.csv`, which the app picks up automatically over the sample.

## How the model works

**Stats (position-adjusted).** Each stat is z-scored *within its position group*,
so a centre's assists are judged against other centres and a point guard's
against other point guards — the positional-expectations requirement. The
weighted z-total is standardised league-wide and mapped linearly to a 0–100
`STATS_SCORE` (50 = league average, ±15 per SD) — gap-preserving, so a
generational season isn't squashed against a merely-good one the way a
percentile rank would. Turnovers carry a negative weight; minutes played carry
a positive one (a 36-minute engine beats a 20-minute bench role). Edit weights
live in the sidebar.

**Age.** A multiplier, not an added stat: exponential decline past the `prime`
age (28 by default), plus a small *upside bonus* per year under prime (capped
at +15%) — identical production from a 21-year-old is a better asset because
of the runway ahead. **Elite age resistance**: the decline rate is scaled down
for players whose *current* production is still elite — a 36-year-old
producing 2 SD above average hasn't shown the collapse the curve predicts, so
the full penalty isn't applied. The protection fades with the stats, so it
rewards sustained greatness, never reputation.

**Availability.** `(games_played / games_in_season) ** exponent`, as a
multiplier. Default exponent 0.5 (square root) softens the penalty — per-game
stats already earn nothing for missed games, so a linear multiplier
double-punishes. If `GP_PREV1`/`GP_PREV2` columns exist (fetch_data.py writes
them), they're averaged with `GP` for multi-season durability.

**The model is multiplicative** — production you don't own (unavailable, or
past the runway) isn't worth partial credit. Two views (sidebar):
- `Asset value`: `VALUE = stats × age_factor × avail_factor` — worth going forward.
- `Win-now`: `VALUE = stats × avail_factor` — how good right now, age ignored.

Position z-scores are blended 25% with league-wide z-scores (sidebar →
Advanced) to damp noise from small or stacked position groups.

## Files
| file | purpose |
|---|---|
| `app.py` | Streamlit dashboard |
| `valuation.py` | scoring logic (pure functions) |
| `fetch_data.py` | pull live data → `players.csv` |
| `make_sample.py` | regenerate `sample_players.csv` |
| `sample_players.csv` | bundled fallback data |

## Extending to other sports
Keep `valuation.py` as the engine. Per sport, supply a CSV with `PLAYER, POS,
AGE, GP` plus that sport's stat columns, and a matching `stat_weights` dict. The
position-adjustment, age, and availability logic is sport-agnostic — only the
stat set and weights change. That's the path to a cross-sport ranking.
