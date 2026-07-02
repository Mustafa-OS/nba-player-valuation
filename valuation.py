"""
Core valuation logic for ranking NBA players.

The model is MULTIPLICATIVE:

    VALUE = STATS_SCORE x AGE_FACTOR x AVAIL_FACTOR      ("asset" view)
    VALUE = STATS_SCORE x AVAIL_FACTOR                   ("win_now" view)

Multiplicative (not additive) because the components genuinely compound:
production you don't own — because the player is unavailable or past their
runway — isn't worth partial credit. The "win_now" view answers a different
question (how good are they right now?) by ignoring age entirely.

Design decisions:

1. POSITION ADJUSTMENT — each stat is z-scored *within its position group*,
   blended with a league-wide z (default 25% league). The blend keeps
   positional expectations (a C's assists vs other Cs) while damping noise
   from small or unusually strong position groups.

2. STATS SCALE — the weighted z-total is standardised across the league and
   mapped linearly to 0-100 (50 = league average, +/-15 per SD), then
   clipped. Unlike a percentile rank, this PRESERVES GAPS: a generational
   season sits far above a merely-good one.

3. AGE — full value at `prime` (28), exponential decline after, small upside
   bonus per year under prime (capped). ELITE AGE RESISTANCE: the decline
   rate is scaled down for players whose *current* production is elite —
   if a 36-year-old is still producing 2 SD above average, the collapse the
   age curve predicts hasn't materialised, so the full prior isn't applied.
   The protection fades automatically as their stats fade: it rewards
   sustained greatness, never reputation.

4. AVAILABILITY — (games played / season length) ** exponent. Default
   exponent 0.5 (square root) softens the penalty: per-game stats already
   earn nothing for missed games, so a linear multiplier double-punishes.
   If GP_PREV1 / GP_PREV2 columns exist they are averaged with GP for a
   multi-season durability signal (NaN prior seasons — rookies — are
   skipped, not counted as 0).

5. MINUTES — MIN carries a positive weight in the stats score, so a
   36-minute engine outranks a 20-minute bench player with similar
   per-game numbers.
"""

import numpy as np
import pandas as pd

# Stats used in the model. Positive weight = good, negative = bad (turnovers).
DEFAULT_STAT_WEIGHTS = {
    "PTS":    1.00,
    "TRB":    0.70,
    "AST":    0.90,
    "STL":    0.80,
    "BLK":    0.80,
    "TOV":   -0.70,
    "TS_PCT": 0.60,
    "MIN":    0.50,
}

REQUIRED_COLS = ["PLAYER", "POS", "AGE", "GP",
                 "PTS", "TRB", "AST", "STL", "BLK", "TOV", "TS_PCT"]

# 0-100 mapping of the standardised weighted z-total: 50 = league average,
# STATS_SCALE points per standard deviation.
STATS_CENTER = 50.0
STATS_SCALE = 15.0

# Production this many SD above league average earns full age resistance.
ELITE_SD = 2.0


# ---------------------------------------------------------------------------
# Component scores
# ---------------------------------------------------------------------------
def position_adjusted_stats_score(df, stat_weights=None, group_col="POS",
                                  league_blend=0.25):
    """Weighted sum of position-relative z-scores (blended `league_blend`
    with league-wide z), standardised and mapped linearly to 0-100."""
    if stat_weights is None:
        stat_weights = DEFAULT_STAT_WEIGHTS
    df = df.copy()

    weighted_z = pd.Series(0.0, index=df.index)
    for stat, w in stat_weights.items():
        if stat not in df.columns or w == 0:
            continue
        grp = df.groupby(group_col)[stat]
        mu_p = grp.transform("mean")
        sd_p = grp.transform("std").replace(0, np.nan)
        z_pos = ((df[stat] - mu_p) / sd_p).fillna(0.0)

        sd_l = df[stat].std()
        z_lg = ((df[stat] - df[stat].mean()) / sd_l).fillna(0.0) if sd_l else 0.0

        z = (1.0 - league_blend) * z_pos + league_blend * z_lg
        weighted_z = weighted_z + z * w

    sd = weighted_z.std()
    if not sd or np.isnan(sd):
        standardized = weighted_z * 0.0
    else:
        standardized = (weighted_z - weighted_z.mean()) / sd
    score = (STATS_CENTER + STATS_SCALE * standardized).clip(0.0, 100.0)
    return score, standardized


def age_factor(age, prime=28.0, decline=0.10, youth_bonus=0.02, youth_cap=1.15):
    """
    Multiplier on production reflecting asset runway.
      * age <= prime: 1 + youth_bonus per year under prime, capped at youth_cap.
      * age >  prime: exponential decline, `decline` fraction lost per year.
    `decline` may be a scalar or a per-player array (elite age resistance).
    """
    age = np.asarray(age, dtype=float)
    decline = np.asarray(decline, dtype=float)
    over = np.maximum(age - prime, 0.0)
    under = np.maximum(prime - age, 0.0)
    factor = np.exp(-decline * over) * np.minimum(1.0 + youth_bonus * under, youth_cap)
    return np.clip(factor, 0.0, youth_cap)


def availability_factor(gp, games_in_season=82, exponent=0.5):
    """Multiplier in [0, 1]: (share of games played) ** exponent.
    exponent 1.0 = linear (harsh); 0.5 = square root (default, softer)."""
    share = np.clip(np.asarray(gp, dtype=float) / games_in_season, 0.0, 1.0)
    return share ** exponent


# ---------------------------------------------------------------------------
# Composite value
# ---------------------------------------------------------------------------
def compute_valuation(df,
                      stat_weights=None,
                      view="asset",
                      prime=28.0,
                      decline=0.10,
                      youth_bonus=0.02,
                      youth_cap=1.15,
                      elite_age_resistance=0.5,
                      games_in_season=82,
                      avail_exponent=0.5,
                      league_blend=0.25):
    """
    Returns df with STATS_SCORE, AGE_FACTOR, AVAIL_FACTOR, VALUE, RANK.

    view:
      "asset"   — VALUE = stats x age x availability (runway matters)
      "win_now" — VALUE = stats x availability       (age ignored)

    elite_age_resistance in [0, 1]: how much elite current production slows
    the age decline. At 0.5, a player producing ELITE_SD above average
    declines at half the base rate; an average player gets no break.
    """
    df = df.copy()

    stats_score, standardized = position_adjusted_stats_score(
        df, stat_weights, league_blend=league_blend)
    df["STATS_SCORE"] = stats_score

    # Elite age resistance: 0 (average or worse) -> 1 (>= ELITE_SD above avg).
    elite = np.clip(standardized / ELITE_SD, 0.0, 1.0)
    effective_decline = decline * (1.0 - elite_age_resistance * elite)
    df["AGE_FACTOR"] = age_factor(df["AGE"], prime, effective_decline,
                                  youth_bonus, youth_cap)

    gp_cols = ["GP"] + [c for c in ("GP_PREV1", "GP_PREV2") if c in df.columns]
    gp = df[gp_cols].mean(axis=1)
    df["AVAIL_FACTOR"] = availability_factor(gp, games_in_season, avail_exponent)

    if view == "asset":
        df["VALUE"] = df["STATS_SCORE"] * df["AGE_FACTOR"] * df["AVAIL_FACTOR"]
    elif view == "win_now":
        df["VALUE"] = df["STATS_SCORE"] * df["AVAIL_FACTOR"]
    else:
        raise ValueError("view must be 'asset' or 'win_now'")

    df["VALUE"] = df["VALUE"].round(1)
    df = df.sort_values("VALUE", ascending=False).reset_index(drop=True)
    df.insert(0, "RANK", np.arange(1, len(df) + 1))
    return df


def stat_percentiles_within_position(df, player_name, stats=None, group_col="POS"):
    """Percentile (0-100) of a player's raw stats vs their positional peers.
    Used for the per-player breakdown chart. TOV is inverted (fewer = better)."""
    if stats is None:
        stats = ["PTS", "TRB", "AST", "STL", "BLK", "TOV", "TS_PCT", "MIN"]
    row = df[df["PLAYER"] == player_name].iloc[0]
    pos = row[group_col]
    peers = df[df[group_col] == pos]
    out = {}
    for s in stats:
        if s not in df.columns:
            continue
        pct = (peers[s] <= row[s]).mean() * 100.0
        if s == "TOV":            # fewer turnovers is better -> invert
            pct = 100.0 - pct
        out[s] = round(pct, 1)
    return out
