import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Analytics", layout="wide")
st.title("📈 Analytics Dashboard")

# Load and process the trade log
if not os.path.isfile("trade_log.csv"):
    st.warning("No trade log found. Please log some trades first.")
else:
    df = pd.read_csv("trade_log.csv")

    if "Instrument" in df.columns and "Trade Side" in df.columns:
        df = df.dropna(subset=["Instrument", "Trade Side"])
        df["Executed Score"] = df.apply(
            lambda row: row["Long Score"] if row["Trade Side"] == "Long" else row["Short Score"],
            axis=1
        )

        avg_scores = df.groupby("Instrument")["Executed Score"].mean().reset_index()

        st.subheader("Average Executed Score per Instrument")
        fig = px.bar(
            avg_scores,
            x="Instrument",
            y="Executed Score",
            color="Instrument",
            title="Average Executed Score per Instrument",
            text_auto=".2f"
        )
        fig.update_layout(yaxis_range=[0, 10], template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Required columns not found in trade log.")
