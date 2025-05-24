import streamlit as st # type: ignore
import pandas as pd # type: ignore
from datetime import datetime
import os

# Page config
st.set_page_config(page_title="Trade Scoring Tool", layout="wide")

# Styling
st.markdown("""
    <style>
        .stApp { background-color: #1e1e1e; color: #ffffff; }
        .metric-card {
            padding: 1rem;
            margin-top: 1rem;
            margin-bottom: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            font-size: 1.2rem;
            background-color: #2962ff;
            use_container_width: False;
        }
        .metric-card.low {
            background-color: #cc4444;
            margin-top: 1rem;
            margin-bottom: 1rem;
            use_container_width: False;
        }
        .suggestion-box {
            background-color: #be965f;
            color: #1b1107;
            padding: 1rem;
            border-radius: 0.5rem;
            font-weight: bold;
            margin-top: 1rem;
            margin-bottom: 1rem;
            text-align: center;
            use_container_width: False;
        }
        h1 {
            text-align: center;
            margin-bottom: 20px;
        }
        /* Mobile responsiveness */
        @media (max-width: 768px) {
            .metric-card {
                padding: 1rem;
                margin-bottom: 15px;
                min-height: 100px;
            }
            .metric-card strong {
                font-size: 1.1rem;
            }
        }
    </style>

    </style>
""", unsafe_allow_html=True)

# ------------------- Header ------------------- #
st.markdown("<h1>📊 Trade Scoring Tool</h1>", unsafe_allow_html=True)

# Scoring dictionaries
direction_values = {
    "Select...": (0, 0),
    "Trending up w high vol": (3, 0),
    "Trending down w high vol": (0, 3),
    "Trending up w low vol": (0.75, 0),
    "Trending down w low vol": (0, 0.75),
    "Ranging w high vol": (1, 1),
    "Ranging w low vol": (0, 0),
}

phase_values = {
    "Select...": (0, 0),
    "Phase A": (3, 3),
    "Phase B": (2, 2),
    "Phase C": (1, 1),
    "Phase D": (0, 0),
    "Range": (0.5, 0.5),
}

profile_values = {
    "Select...": (0, 0),
    "P-shape": (2, 0),
    "b-shape": (0, 2),
    "D-shape": (1.5, 1.5),
    "narrow day type": (1, 1),
    "non-standard": (0.5, 0.5),
}

access_values = {
    "Select...": (0, 0),
    "LVN 0.50 above POC": (0.25, 1),
    "LVN 0.50 below POC": (1, 0.25),
    "HVN 0.50 above POC": (0.25, 1),
    "HVN 0.50 below POC": (1, 0.25),
    "LVN 0.50 above VAH": (0, 1),
    "HVN 0.50 above VAH": (0, 1),
    "LVN 0.50 below VAL": (1, 0),
    "HVN 0.50 below VAL": (1, 0),
    "VAL": (0.5, 0),
    "VAH": (0, 0.5),
    "POC": (0.5, 0.5),
}

past_day_values = {
    "Select...": (0, 0),
    "Asia close inside PDR": (0.5, 0.5),
    "Asia close outside PDH": (0.5, 0.25),
    "Asia close outside PDL": (0.25, 0.5),
}

catalyst_values = {"Select...": (0, 0),
    "Purely technical": (0.4, 0.4),
    "Macro event": (0.5, 0.5),
    "Data Driven": (0.25, 0.25),
    "News event": (0.25, 0.25),
    "no catalyst": (0, 0),
}

def get_risk_step(score, last_outcome):
    after_win = {(5, 6.5): 1, (6.6, 7.5): 2, (7.6, 8.5): 3, (8.5, 10): 4}
    after_loss = {(5, 6.5): 1, (6.6, 7.5): 1, (7.6, 8.5): 1, (8.5, 10): 2}
    if score < 5: return 0
    table = after_win if last_outcome == "Win" else after_loss
    return next(
        (step for (low, high), step in table.items() if low <= score <= high),
        1,
    )

# Initialize session state variables for tracking cooldown
if 'last_logged_params' not in st.session_state:
    st.session_state.last_logged_params = None
if 'log_cooldown_until' not in st.session_state:
    st.session_state.log_cooldown_until = None
if 'last_instrument' not in st.session_state:
    st.session_state.last_instrument = None

# Layout: Input (left) and Log (right)
main_col1, main_col2 = st.columns([2, 2])

# Input Fields
with main_col1:
    col1, col2 = st.columns(2)
    with col1:
        direction = st.selectbox("Direction", list(direction_values.keys()))
        phase = st.selectbox("Market Phase", list(phase_values.keys()))
        profile = st.selectbox("Volume Profile", list(profile_values.keys()))
    with col2:
        access = st.selectbox("Access", list(access_values.keys()))
        pd_context = st.selectbox("Past Day Context", list(past_day_values.keys()))
        catalyst = st.selectbox("Catalyst", list(catalyst_values.keys()))

    # Scores
    short_score = sum([
        direction_values[direction][1],
        phase_values[phase][1],
        profile_values[profile][1],
        access_values[access][1],
        past_day_values[pd_context][1],
        catalyst_values[catalyst][1],
    ])

    long_score = sum([
        direction_values[direction][0],
        phase_values[phase][0],
        profile_values[profile][0],
        access_values[access][0],
        past_day_values[pd_context][0],
        catalyst_values[catalyst][0],
    ])

    if long_score >= 5 and long_score > short_score:
        suggested_side = "Long"
        active_score = long_score
    elif short_score >= 5 and short_score > long_score:
        suggested_side = "Short"
        active_score = short_score
    elif short_score < 5 and long_score < 5:
        suggested_side = "No Trade"
        active_score = 0
    else:
        suggested_side = "No Edge"
        active_score = max(long_score, short_score)

    # Safely get last outcome
    last_outcome = "Loss"
    if os.path.isfile("trade_log.csv"):
        df_out = pd.read_csv("trade_log.csv")
        if "Outcome" in df_out.columns:
            df_clean = df_out[df_out["Outcome"].isin(["Win", "Loss", "BE"])]
            if not df_clean.empty:
                last_outcome = df_clean["Outcome"].iloc[-1]

    risk_step = get_risk_step(active_score, last_outcome)
    risk_map = {0: "Skip trade", 1: "x1 (0.25%)", 2: "x2 (0.5%)", 3: "x3 (1%)", 4: "x4 (2%)"}
    risk_string = risk_map[risk_step]

    # Suggested Side Box (before result)
    st.markdown(f"<div class='suggestion-box'>Suggested Side: {suggested_side}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='suggestion-box'>Suggested Risk: {risk_string}</div>", unsafe_allow_html=True)

    outcome = st.selectbox("Trade Outcome", ["Win", "Loss", "Breakeven", "Not Executed"])

    # Result Cards
    st.markdown("---")
    st.subheader("📈 Scores")
    col_res1, col_res2 = st.columns(2)
    score_style_long = "metric-card" if long_score >= 5 else "metric-card low"
    score_style_short = "metric-card" if short_score >= 5 else "metric-card low"

    with col_res1:
        st.markdown(f"<div class='{score_style_short}'><strong>Short Score</strong><br>{round(short_score, 2)} </br> </div>", unsafe_allow_html=True)
    with col_res2:
        st.markdown(f"<div class='{score_style_long}'><strong>Long Score</strong><br>{round(long_score, 2)}</div>", unsafe_allow_html=True)

# Log Panel
with main_col2:
    st.subheader("📝 Log Your Trade")
    market = st.selectbox("Market Instrument", ["GC", "MGC", "6E", "M6E", "6B", "M6B", "CL", "MCL", "ES", "MES", "NQ", "MNQ"])
    side_choice = st.selectbox("Select trade side to log:", ["Buy (Long)", "Sell (Short)"])

    # Store current trade parameters
    current_params = {
        "instrument": market,
        "direction": direction,
        "phase": phase,
        "profile": profile,
        "access": access,
        "pd_context": pd_context,
        "catalyst": catalyst,
        "side": side_choice
    }

    # Check if instrument changed from the last time
    if st.session_state.last_instrument != market:
        # Reset cooldown if instrument changed
        st.session_state.log_cooldown_until = None

    # Update last instrument
    st.session_state.last_instrument = market

    # Check cooldown status
    can_log = True
    cooldown_message = None

    if st.session_state.log_cooldown_until is not None:
        now = datetime.now()
        if now < st.session_state.log_cooldown_until:
        # Check if parameters match those that triggered cooldown
            if st.session_state.last_logged_params is not None:
            # Compare current params with last logged params
                params_match = True
                for key, value in current_params.items():
                    if key in st.session_state.last_logged_params and st.session_state.last_logged_params[key] != value:
                        if key != "instrument":
                            params_match = False

                if params_match:
                    time_left = (st.session_state.log_cooldown_until - now).total_seconds()
                    can_log = False
                    cooldown_message = f"Cannot log duplicate trade. Please wait {int(time_left)} seconds."

    # Selected score based on trade side
    selected_score = long_score if side_choice == "Long" else short_score

    # Logic for log button state
    if can_log:
        if selected_score < 5:
            log_button_disabled = True
            log_message = "Cannot log: Score for selected side must be 5 or higher"
        else:
            log_button_disabled = False
            log_message = None
    else:
        log_button_disabled = True
        log_message = cooldown_message

    # Display warning message if needed
    if log_message:
        st.warning(log_message)

    # Log trade button
    if st.button("Log Trade",use_container_width=False, disabled=log_button_disabled):
        if selected_score >= 5:
            log_entry = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Instrument": market,
                "Direction": direction,
                "Market Phase": phase,
                "Volume Profile": profile,
                "Access": access,
                "Past Day Context": pd_context,
                "Catalyst": catalyst,
                "Long Score": round(long_score, 2),
                "Short Score": round(short_score, 2),
                "Trade Side": "Long" if side_choice == "Buy (Long)" else "Short",
                "Suggested Side": suggested_side
            }
            file_exists = os.path.isfile("trade_log.csv")
            df_log = pd.DataFrame([log_entry])
            df_log.to_csv("trade_log.csv", mode='a', header=not file_exists, index=False)

            # Update session state with logged parameters and cooldown time
            st.session_state.last_logged_params = current_params.copy()
            st.session_state.log_cooldown_until = datetime.now() + pd.Timedelta(minutes=1)

            #st.success("Trade logged successfully!")

# Update session state with logged parameters and cooldown time
            st.session_state.last_logged_params = current_params.copy()
            st.session_state.log_cooldown_until = datetime.now() + pd.Timedelta(minutes=1)

    if os.path.isfile("trade_log.csv"):
        st.markdown("---")
        st.subheader("📂 Logged Trades")
        df_existing = pd.read_csv("trade_log.csv")
        st.dataframe(df_existing, use_container_width=True)
        csv = df_existing.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Trade Log",
            data=csv,
            file_name='trade_log.csv',
            mime='text/csv'
        )