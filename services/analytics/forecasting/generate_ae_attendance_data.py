#!/usr/bin/env python3
"""Generate a SYNTHETIC daily A&E (Emergency Department) attendance time series.

There is no real A&E attendance data anywhere in this project. This script
fabricates a plausible daily count series with the seasonal structure real
A&E demand actually shows (weekly pattern, winter surge, gradual trend, and
occasional spike days like flu outbreaks or holidays) purely so the Prophet
forecasting model and dashboard have something realistic to work with. Do
not treat this as real NHS/hospital data.

Usage:
    python forecasting/generate_ae_attendance_data.py --years 3 --output data/ae_attendances.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_series(start_date: str, num_days: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start_date, periods=num_days, freq="D")

    day_index = np.arange(num_days)

    # Slow upward trend: demand growing ~4% per year.
    trend = 180 * (1 + 0.04) ** (day_index / 365.25)

    # Weekly seasonality: Mondays and weekends busier than midweek.
    dow = dates.dayofweek.to_numpy()  # 0=Mon ... 6=Sun
    is_weekend = np.isin(dow, [5, 6])
    weekly_effect = np.select([dow == 0, is_weekend], [1.12, 1.18], default=1.0)

    # Annual seasonality: winter (Dec-Feb) surge, summer dip.
    day_of_year = dates.dayofyear.to_numpy()
    annual_effect = 1 + 0.15 * np.cos(2 * np.pi * (day_of_year - 15) / 365.25)

    noise = rng.normal(loc=0, scale=8, size=num_days)

    attendances = trend * weekly_effect * annual_effect + noise

    # A handful of outbreak-style spike days (e.g. flu season peaks).
    num_spikes = max(1, num_days // 400)
    spike_days = rng.choice(num_days, size=num_spikes, replace=False)
    attendances[spike_days] += rng.uniform(40, 90, size=num_spikes)

    attendances = np.clip(attendances, a_min=20, a_max=None).round().astype(int)

    return pd.DataFrame({"ds": dates, "y": attendances})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--start-date", default=None, help="Defaults to `years` before today")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parent / "data" / "ae_attendances.csv"
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    num_days = int(args.years * 365.25)
    start_date = args.start_date or (pd.Timestamp.today() - pd.Timedelta(days=num_days)).date().isoformat()

    df = generate_series(start_date, num_days, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} rows ({df['ds'].min().date()} to {df['ds'].max().date()}) to {args.output}")


if __name__ == "__main__":
    main()
