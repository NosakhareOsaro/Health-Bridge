"""Tests for the synthetic A&E attendance generator and Prophet forecasting pipeline.

These actually run Prophet (no mocking) since the point is verifying the
forecasting pipeline works end-to-end; each test uses a short series to keep
runtime reasonable.
"""

from __future__ import annotations

from forecasting.generate_ae_attendance_data import generate_series
from forecasting.train_prophet_model import evaluate_holdout, fit_and_forecast


def test_generate_series_shape_and_columns():
    df = generate_series("2024-01-01", 400)
    assert list(df.columns) == ["ds", "y"]
    assert len(df) == 400
    assert (df["y"] > 0).all()


def test_generate_series_is_deterministic_for_a_given_seed():
    a = generate_series("2024-01-01", 200, seed=1)
    b = generate_series("2024-01-01", 200, seed=1)
    assert a.equals(b)


def test_generate_series_has_weekly_seasonality():
    df = generate_series("2024-01-01", 365)
    df["dow"] = df["ds"].dt.dayofweek
    weekday_avg = df[df["dow"] < 5]["y"].mean()
    weekend_avg = df[df["dow"] >= 5]["y"].mean()
    assert weekend_avg > weekday_avg


def test_fit_and_forecast_extends_beyond_history():
    history = generate_series("2024-01-01", 400)
    _, forecast = fit_and_forecast(history, forecast_days=14)
    assert forecast["ds"].max() > history["ds"].max()
    assert {"yhat", "yhat_lower", "yhat_upper"}.issubset(forecast.columns)
    assert len(forecast) == len(history) + 14


def test_evaluate_holdout_reports_reasonable_accuracy_on_synthetic_data():
    history = generate_series("2023-01-01", 700)
    metrics = evaluate_holdout(history, holdout_days=30)
    assert metrics["holdout_days"] == 30
    assert metrics["mae"] >= 0
    # The synthetic series is smooth/seasonal, so Prophet should track it well.
    assert metrics["mape_pct"] < 15
