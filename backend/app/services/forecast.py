from __future__ import annotations

from collections.abc import Sequence
from statistics import mean

import pandas as pd

try:
    from xgboost import XGBRegressor
except Exception:  # pragma: no cover - optional dependency
    XGBRegressor = None


def build_daily_series(records: Sequence[object]) -> pd.Series:
    if not records:
        return pd.Series(dtype=float)

    frame = pd.DataFrame(
        {
            "date": [getattr(record, "consumed_on") for record in records],
            "quantity": [float(getattr(record, "quantity")) for record in records],
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    daily = frame.groupby("date", as_index=True)["quantity"].sum().asfreq("D", fill_value=0.0)
    return daily.sort_index()


def _lag_frame(series: pd.Series, lags: int = 7) -> pd.DataFrame:
    frame = pd.DataFrame({"target": series})
    for lag in range(1, lags + 1):
        frame[f"lag_{lag}"] = series.shift(lag)
    frame["rolling_7"] = series.shift(1).rolling(7).mean()
    frame["rolling_30"] = series.shift(1).rolling(30).mean()
    frame["trend_7"] = series.shift(1).diff().rolling(7).mean()
    return frame.dropna()


def _fallback_forecast(series: pd.Series, horizon: int) -> float:
    if series.empty:
        return 0.0
    recent_7 = float(series.tail(7).mean())
    recent_30 = float(series.tail(30).mean())
    slope = float(series.tail(14).diff().fillna(0.0).mean()) if len(series) > 1 else 0.0
    return max(0.0, recent_7 * 0.7 + recent_30 * 0.3 + slope * horizon * 0.05)


def forecast_consumption(records: Sequence[object], horizons: Sequence[int] = (30, 60, 90)) -> dict[str, object]:
    series = build_daily_series(records)
    recent_daily_avg = float(series.tail(30).mean()) if not series.empty else 0.0

    predictions: list[dict[str, float]] = []
    if len(series) >= 14 and XGBRegressor is not None:
        frame = _lag_frame(series)
        if not frame.empty:
            features = frame.drop(columns=["target"])
            target = frame["target"]
            model = XGBRegressor(
                n_estimators=160,
                max_depth=4,
                learning_rate=0.08,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="reg:squarederror",
                random_state=42,
            )
            model.fit(features, target)
            history = series.tolist()
            for horizon in horizons:
                value = 0.0
                temp_history = history.copy()
                for _ in range(horizon):
                    rolling = pd.Series(temp_history)
                    lag_values = [rolling.iloc[-lag] if len(rolling) >= lag else rolling.mean() for lag in range(1, 8)]
                    row = pd.DataFrame(
                        [
                            {
                                **{f"lag_{index + 1}": lag_values[index] for index in range(7)},
                                "rolling_7": float(rolling[-7:].mean()) if len(rolling) >= 7 else float(rolling.mean()),
                                "rolling_30": float(rolling[-30:].mean()) if len(rolling) >= 30 else float(rolling.mean()),
                                "trend_7": float(rolling.diff().tail(7).mean()) if len(rolling) > 1 else 0.0,
                            }
                        ]
                    )
                    value = max(0.0, float(model.predict(row)[0]))
                    temp_history.append(value)
                predictions.append({"horizon_days": horizon, "predicted_quantity": round(value, 2)})
        else:
            predictions = [
                {"horizon_days": horizon, "predicted_quantity": round(_fallback_forecast(series, horizon), 2)}
                for horizon in horizons
            ]
    else:
        predictions = [
            {"horizon_days": horizon, "predicted_quantity": round(_fallback_forecast(series, horizon), 2)}
            for horizon in horizons
        ]

    recommendation = int(round(mean(point["predicted_quantity"] for point in predictions) * 1.15)) if predictions else 0
    return {
        "recent_daily_avg": round(recent_daily_avg, 2),
        "points": predictions,
        "recommendation": recommendation,
    }
