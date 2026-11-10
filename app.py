
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json

import pandas as pd
import streamlit as st


# ============================================================
# VERSE NBA — DASHBOARD
# ============================================================

st.set_page_config(
    page_title="VERSE NBA",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA = Path(__file__).resolve().parent / "data"
TODAY = datetime.now(
    ZoneInfo("America/New_York")
).date()

MARKET_NAMES = {
    "player_points": "Points",
    "player_rebounds": "Rebounds",
    "player_assists": "Assists",
    "player_threes": "3-Pointers",
    "player_points_rebounds": "Points + Rebounds",
    "player_points_assists": "Points + Assists",
    "player_rebounds_assists": "Rebounds + Assists",
    "player_points_rebounds_assists": "PRA",
}


# ============================================================
# DESIGN
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1550px;
    }

    h1, h2, h3 {
        letter-spacing: -0.5px;
    }

    div[data-testid="stMetric"] {
        background: #151b29;
        border: 1px solid #293247;
        border-radius: 12px;
        padding: 16px;
    }

    div[data-testid="stMetricLabel"] {
        color: #aab4c8;
    }

    div[data-testid="stMetricValue"] {
        color: #ffffff;
    }

    .verse-header {
        padding: 18px 0 12px;
    }

    .verse-subtitle {
        color: #9ba9c2;
        font-size: 14px;
    }

    .verse-green {
        color: #32d583;
        font-weight: 700;
    }

    .verse-muted {
        color: #9ba9c2;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def load_csv(filename):
    path = DATA / filename

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def market_label(value):
    return MARKET_NAMES.get(value, value)


def american_odds(value):
    try:
        value = int(value)
        return f"+{value}" if value > 0 else str(value)
    except (ValueError, TypeError):
        return "—"


def format_time(value):
    try:
        timestamp = pd.to_datetime(
            value, utc=True
        )

        return timestamp.tz_convert(
            "America/New_York"
        ).strftime("%I:%M %p")
    except (ValueError, TypeError):
        return "—"


def numeric_column(df, name, default=0):
    if name not in df.columns:
        df[name] = default

    df[name] = pd.to_numeric(
        df[name], errors="coerce"
    )

    return df


def prepare_props(df):
    df = df.copy()

    for col in [
        "projection",
        "line",
        "odds",
        "win_probability",
        "roi",
        "games",
    ]:
        df = numeric_column(df, col)

    df = df.dropna(
        subset=[
            "projection",
            "line",
            "odds",
            "win_probability",
            "roi",
        ]
    )

    df["Market"] = df["market"].map(
        market_label
    )

    df["Projected"] = df["projection"].round(1)

    df["FanDuel Line"] = df["line"]

    df["Difference"] = (
        df["projection"] - df["line"]
    ).round(1)

    df["Win %"] = (
        df["win_probability"] * 100
    ).round(1)

    df["ROI %"] = (
        df["roi"] * 100
    ).round(1)

    df["FanDuel Odds"] = df["odds"].map(
        american_odds
    )

    df["Tipoff"] = df["tipoff_utc"].map(
        format_time
    )

    return df


def classify_prop(row, min_games, min_roi, min_win):
    if row["games"] < min_games:
        return "PASS"

    if row["Win %"] < min_win:
        return "PASS"

    if row["ROI %"] < min_roi:
        return "PASS"

    if row["odds"] < -200:
        return "PASS"

    if row["odds"] > 250:
        return "PASS"

    return "REVIEW"


def style_signal(value):
    if value == "REVIEW":
        return (
            "background-color: #173f30;"
            "color: #b7f7d1;"
            "font-weight: bold;"
        )

    return ""


def style_roi(value):
    if pd.isna(value):
        return ""

    if value > 0:
        return "color: #32d583; font-weight: bold;"

    if value < 0:
        return "color: #f97066;"

    return ""


def display_props(df):
    columns = [
        "game",
        "Tipoff",
        "player",
        "Market",
        "side",
        "Projected",
        "FanDuel Line",
        "Difference",
        "FanDuel Odds",
        "Win %",
        "ROI %",
        "games",
        "Signal",
    ]

    if df.empty:
        st.info("No props match these filters.")
        return

    view = df[columns].rename(
        columns={
            "game": "Matchup",
            "player": "Player",
            "side": "Pick",
            "games": "Games Used",
        }
    )

    styled = (
        view.style
        .map(
            style_signal,
            subset=["Signal"],
        )
        .map(
            style_roi,
            subset=["ROI %"],
        )
        .format({
            "Projected": "{:.1f}",
            "FanDuel Line": "{:.1f}",
            "Difference": "{:+.1f}",
            "Win %": "{:.1f}%",
            "ROI %": "{:+.1f}%",
        })
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="verse-header">
        <h1>🏀 VERSE NBA</h1>
        <div class="verse-subtitle">
            NBA Player Prop Analytics · FanDuel Odds
            · Automated ESPN Projections
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# STATUS
# ============================================================

status_path = DATA / "status.json"

status = {}

if status_path.exists():
    try:
        status = json.loads(
            status_path.read_text()
        )
    except (ValueError, OSError):
        status = {}

snapshot_date = status.get("date_et")
updated_at = status.get("updated_utc")

stale = snapshot_date != TODAY.isoformat()

if updated_at:
    updated_label = format_time(updated_at)
else:
    updated_label = "Unknown"

st.caption(
    f"Slate: {snapshot_date or 'Unknown'} ET"
    f"  |  Last update: {updated_label} ET"
    f"  |  Odds: {status.get('odds_mode', 'Unknown')}"
)

if stale:
    st.error(
        "STALE DATA — This dashboard does not contain "
        "today's verified projections and odds."
    )


# ============================================================
# LOAD DATA
# ============================================================

projections = load_csv("projections.csv")
props = load_csv("props.csv")

if projections.empty:
    st.warning(
        "No projections available. "
        "Check your GitHub Actions update workflow."
    )
    st.stop()

required_props = {
    "game",
    "player",
    "market",
    "side",
    "projection",
    "line",
    "odds",
    "win_probability",
    "roi",
    "games",
    "tipoff_utc",
}

if not props.empty:
    if not required_props.issubset(props.columns):
        st.error(
            "props.csv is missing required columns."
        )
        props = pd.DataFrame()
    else:
        props = prepare_props(props)

        # Never present previous-day bets as current.
        if stale:
            props = pd.DataFrame()

        elif "date" in props.columns:
            props = props[
                props["date"].astype(str)
                == TODAY.isoformat()
            ].copy()

        # Exclude games already underway.
        if not props.empty:
            tipoffs = pd.to_datetime(
                props["tipoff_utc"],
                utc=True,
                errors="coerce",
            )

            now = pd.Timestamp.now(tz="UTC")

            props = props[
                tipoffs > now
            ].copy()

        # Exclude odds that are too old.
        if (
            not props.empty
            and "fanduel_observed_at" in props.columns
        ):
            observed = pd.to_datetime(
                props["fanduel_observed_at"],
                utc=True,
                errors="coerce",
            )

            now = pd.Timestamp.now(tz="UTC")

            props = props[
                (observed <= now + pd.Timedelta(minutes=5))
                & (observed >= now - pd.Timedelta(hours=2))
            ].copy()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("VERSE Controls")

st.sidebar.subheader("Recommendation Settings")

min_games = st.sidebar.slider(
    "Minimum historical games",
    min_value=8,
    max_value=30,
    value=15,
    step=1,
)

min_roi = st.sidebar.slider(
    "Minimum estimated ROI %",
    min_value=0,
    max_value=50,
    value=8,
    step=1,
)

min_win = st.sidebar.slider(
    "Minimum estimated win probability %",
    min_value=40,
    max_value=90,
    value=55,
    step=1,
)

st.sidebar.caption(
    "These are adjustable screening thresholds, "
    "not statistically validated betting criteria."
)

st.sidebar.divider()

st.sidebar.subheader("Market Filters")

available_markets = sorted(
    projections["market"].dropna().unique()
)

selected_markets = st.sidebar.multiselect(
    "Markets",
    options=available_markets,
    default=available_markets,
    format_func=market_label,
)

available_games = sorted(
    projections["game"].dropna().unique()
)

selected_games = st.sidebar.multiselect(
    "Games",
    options=available_games,
    default=available_games,
)

selected_sides = st.sidebar.multiselect(
    "Bet Direction",
    options=["Over", "Under"],
    default=["Over", "Under"],
)


# ============================================================
# FILTER PROPS
# ============================================================

if not props.empty:
    filtered = props[
        props["market"].isin(selected_markets)
        & props["game"].isin(selected_games)
        & props["side"].isin(selected_sides)
    ].copy()

    filtered["Signal"] = filtered.apply(
        lambda row: classify_prop(
            row,
            min_games,
            min_roi,
            min_win,
        ),
        axis=1,
    )

    filtered = filtered.sort_values(
        ["ROI %", "Win %"],
        ascending=False,
    )

    best_bets = filtered[
        filtered["Signal"] == "REVIEW"
    ].copy()

else:
    filtered = pd.DataFrame()
    best_bets = pd.DataFrame()


# ============================================================
# OVERVIEW METRICS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "NBA Games",
        len(available_games),
    )

with col2:
    st.metric(
        "Player Projections",
        len(projections),
    )

with col3:
    st.metric(
        "Priced Props",
        len(props),
    )

with col4:
    st.metric(
        "Review Candidates",
        len(best_bets),
    )


# ============================================================
# MAIN DASHBOARD
# ============================================================

tab1, tab2, tab3 = st.tabs([
    "🔥 Best Bets",
    "📊 All FanDuel Props",
    "🏀 Player Projections",
])


# ============================================================
# TAB 1 — BEST BETS
# ============================================================

with tab1:
    st.subheader("Top Player Prop Candidates")

    st.caption(
        "Selections meeting your probability, ROI, "
        "sample-size and odds filters."
    )

    if best_bets.empty:
        st.info(
            "No selections currently meet the "
            "screening criteria."
        )

    else:
        top = best_bets.head(20)

        display_props(top)

        st.caption(
            f"Showing {len(top)} of "
            f"{len(best_bets)} review candidates."
        )

    st.warning(
        "REVIEW does not mean a bet is likely to "
        "be profitable. The model is experimental "
        "and has not been calibrated or backtested."
    )


# ============================================================
# TAB 2 — ALL FANDUEL PROPS
# ============================================================

with tab2:
    st.subheader("All Evaluated FanDuel Props")

    if filtered.empty:
        st.info(
            "No current priced props available "
            "for the selected filters."
        )

    else:
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.metric(
                "Filtered Props",
                len(filtered),
            )

        with col_b:
            st.metric(
                "Review Candidates",
                len(best_bets),
            )

        with col_c:
            st.metric(
                "Unique Players",
                filtered["player"].nunique(),
            )

        show_only_review = st.checkbox(
            "Show only REVIEW candidates",
            value=False,
        )

        if show_only_review:
            display_props(best_bets)
        else:
            display_props(filtered)


# ============================================================
# TAB 3 — PLAYER PROJECTIONS
# ============================================================

with tab3:
    st.subheader("VERSE NBA Projections")

    f = projections[
        projections["market"].isin(
            selected_markets
        )
        & projections["game"].isin(
            selected_games
        )
    ].copy()

    if f.empty:
        st.info(
            "No projections match these filters."
        )

    else:
        f["Market"] = f["market"].map(
            market_label
        )

        f["Projected"] = pd.to_numeric(
            f["projection"],
            errors="coerce",
        ).round(1)

        projection_columns = [
            "game",
            "player",
            "team",
            "opponent",
            "Market",
            "Projected",
            "minutes",
            "recent_avg",
            "season_window_avg",
            "opp_factor",
            "games",
            "rest_days",
        ]

        projection_columns = [
            col for col in projection_columns
            if col in f.columns
        ]

        st.dataframe(
            f[projection_columns].rename(
                columns={
                    "game": "Matchup",
                    "player": "Player",
                    "team": "Team",
                    "opponent": "Opponent",
                    "minutes": "Projected Minutes",
                    "recent_avg": "Recent Average",
                    "season_window_avg": "Season Average",
                    "opp_factor": "Opponent Factor",
                    "games": "Games Used",
                    "rest_days": "Rest Days",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# MODEL INFORMATION
# ============================================================

st.divider()

with st.expander("How VERSE NBA evaluates player props"):
    st.markdown(
        """
        **1. Historical performance**

        Uses ESPN player box scores to estimate
        performance from recent games.

        **2. Minutes and matchup adjustments**

        Applies the existing VERSE NBA projection
        model, including its team-level defensive
        adjustment.

        **3. FanDuel lines**

        Compares projected statistics against
        FanDuel Over/Under lines.

        **4. Estimated probability**

        Uses the probability distribution defined
        in model.py.

        **5. Estimated ROI**

        Compares estimated win probability with
        the sportsbook payout.

        **6. Review screening**

        Highlights selections that meet your
        chosen thresholds.

        **Limitations**

        - Probabilities are not calibrated.
        - ROI estimates are not validated.
        - Injury and lineup information is not verified.
        - Odds may change after collection.
        - Only collected markets are evaluated.
        - REVIEW signals are not guaranteed wins.
        """
    )

st.caption(
    "VERSE NBA · Experimental player-prop analytics "
    "· Verify all FanDuel lines before use."
)
