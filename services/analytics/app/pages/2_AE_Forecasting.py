"""A&E demand forecasting: Prophet forecast vs. actual, refreshed on demand.

The underlying series is entirely SYNTHETIC (see
forecasting/generate_ae_attendance_data.py) -- there is no real A&E
attendance data in this project. The point is to demonstrate a working
Prophet forecasting pipeline end-to-end, not to model any real health
system's demand.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from forecasting.generate_ae_attendance_data import generate_series  # noqa: E402
from forecasting.train_prophet_model import evaluate_holdout, fit_and_forecast  # noqa: E402

logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

st.set_page_config(page_title="A&E Forecasting | HealthBridge", layout="wide")
st.title("A&E Demand Forecasting")
st.warning(
    "**Synthetic data.** This chart forecasts a fabricated daily attendance series "
    "(weekly + winter-surge seasonality, trend, noise) -- it does not represent any "
    "real hospital or NHS trust.",
    icon="⚠️",
)

with st.sidebar:
    st.header("Forecast settings")
    years_history = st.slider("Years of synthetic history", 1, 5, 3)
    forecast_days = st.slider("Forecast horizon (days)", 7, 90, 30)
    holdout_days = st.slider("Holdout window for accuracy check (days)", 7, 60, 30)


@st.cache_data(show_spinner=False)
def load_history(years: float) -> pd.DataFrame:
    num_days = int(years * 365.25)
    start = (pd.Timestamp.today() - pd.Timedelta(days=num_days)).date().isoformat()
    return generate_series(start, num_days)


@st.cache_resource(show_spinner="Fitting Prophet model...")
def run_forecast(history: pd.DataFrame, horizon: int):
    return fit_and_forecast(history, horizon)


@st.cache_data(show_spinner="Evaluating holdout accuracy...")
def run_holdout(history: pd.DataFrame, holdout: int) -> dict:
    return evaluate_holdout(history, holdout)


history = load_history(years_history)
_, forecast = run_forecast(history, forecast_days)
metrics = run_holdout(history, holdout_days)

col1, col2, col3 = st.columns(3)
col1.metric("Holdout MAE (attendances/day)", metrics["mae"])
col2.metric("Holdout MAPE", f"{metrics['mape_pct']}%")
col3.metric("Forecast horizon", f"{forecast_days} days")

today = pd.Timestamp.today().normalize()

actual = history.rename(columns={"y": "value"})
actual["series"] = "Actual"

forecast_future = forecast[forecast["ds"] > history["ds"].max()].copy()
forecast_future = forecast_future.rename(columns={"yhat": "value"})
forecast_future["series"] = "Forecast"

plot_history = actual.tail(180)[["ds", "value", "series"]]
plot_forecast = forecast_future[["ds", "value", "series"]]
band = forecast_future[["ds", "yhat_lower", "yhat_upper"]]

base = alt.Chart(plot_history).mark_line(color="#4c78a8").encode(x="ds:T", y=alt.Y("value:Q", title="Attendances"))
forecast_line = alt.Chart(plot_forecast).mark_line(color="#e45756", strokeDash=[4, 2]).encode(x="ds:T", y="value:Q")
confidence_band = (
    alt.Chart(band)
    .mark_area(opacity=0.2, color="#e45756")
    .encode(x="ds:T", y="yhat_lower:Q", y2="yhat_upper:Q")
)
today_rule = alt.Chart(pd.DataFrame({"ds": [today]})).mark_rule(color="gray", strokeDash=[2, 2]).encode(x="ds:T")

st.altair_chart(
    (base + confidence_band + forecast_line + today_rule).properties(height=420).interactive(),
    use_container_width=True,
)

with st.expander("Forecast data (future days only)"):
    st.dataframe(
        forecast_future[["ds", "value", "yhat_lower", "yhat_upper"]].rename(
            columns={"value": "yhat"}
        ),
        use_container_width=True,
    )
