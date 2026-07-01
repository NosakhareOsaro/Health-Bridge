#!/usr/bin/env python3
"""Fit a Prophet model to the (synthetic) daily A&E attendance series and
forecast future demand.

Usage:
    python forecasting/train_prophet_model.py --input data/ae_attendances.csv \
        --forecast-days 30 --output data/ae_forecast.csv
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from prophet import Prophet

logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)


def fit_and_forecast(history: pd.DataFrame, forecast_days: int) -> tuple[Prophet, pd.DataFrame]:
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.9,
    )
    model.fit(history)
    future = model.make_future_dataframe(periods=forecast_days)
    forecast = model.predict(future)
    return model, forecast


def evaluate_holdout(history: pd.DataFrame, holdout_days: int) -> dict[str, float]:
    """Fit on all but the last `holdout_days`, forecast that window, and score it."""
    train = history.iloc[:-holdout_days]
    test = history.iloc[-holdout_days:]

    model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
    model.fit(train)
    future = model.make_future_dataframe(periods=holdout_days)
    forecast = model.predict(future)

    merged = test.merge(forecast[["ds", "yhat"]], on="ds", how="left")
    errors = merged["y"] - merged["yhat"]
    mae = errors.abs().mean()
    mape = (errors.abs() / merged["y"]).mean() * 100
    return {"holdout_days": holdout_days, "mae": round(mae, 2), "mape_pct": round(mape, 2)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path(__file__).resolve().parent / "data" / "ae_attendances.csv"
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parent / "data" / "ae_forecast.csv"
    )
    parser.add_argument("--forecast-days", type=int, default=30)
    parser.add_argument("--holdout-days", type=int, default=30)
    args = parser.parse_args()

    history = pd.read_csv(args.input, parse_dates=["ds"])

    metrics = evaluate_holdout(history, args.holdout_days)
    print(f"Holdout evaluation (last {metrics['holdout_days']} days): "
          f"MAE={metrics['mae']}, MAPE={metrics['mape_pct']}%")

    _, forecast = fit_and_forecast(history, args.forecast_days)
    output_cols = ["ds", "yhat", "yhat_lower", "yhat_upper"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    forecast[output_cols].to_csv(args.output, index=False)
    print(f"Wrote {args.forecast_days}-day forecast to {args.output}")


if __name__ == "__main__":
    main()
