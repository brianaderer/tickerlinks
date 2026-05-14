from dataclasses import dataclass

import numpy as np
import pandas as pd
from xgboost import XGBRegressor


FEATURE_DROP_COLUMNS = {"target_close", "as_of", "symbol", "company_id"}
TRAIN_TEST_SPLIT = 0.8
MODEL_PARAMS = {
    "objective": "reg:squarederror",
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "random_state": 42,
    "n_jobs": 4,
}


@dataclass
class HorizonTraining:
    horizon: int
    model: XGBRegressor
    metrics: dict
    encoded_columns: list[str]
    train_count: int
    test_count: int
    sample_count: int


def chronological_split(frame: pd.DataFrame, ratio: float = TRAIN_TEST_SPLIT) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        raise ValueError("Cannot split empty frame")
    sorted_df = frame.copy()
    sorted_df["as_of"] = pd.to_datetime(sorted_df["as_of"], utc=True)
    sorted_df = sorted_df.sort_values("as_of").reset_index(drop=True)
    split_idx = int(len(sorted_df) * ratio)
    if split_idx <= 0 or split_idx >= len(sorted_df):
        raise ValueError(f"Not enough rows for split: {len(sorted_df)}")
    return sorted_df.iloc[:split_idx], sorted_df.iloc[split_idx:]


def train_horizon_models(frames_by_horizon: dict[int, pd.DataFrame]) -> dict[int, HorizonTraining]:
    trained: dict[int, HorizonTraining] = {}

    for horizon, frame in sorted(frames_by_horizon.items()):
        if frame.empty:
            continue
        train_df, test_df = chronological_split(frame, TRAIN_TEST_SPLIT)
        if len(train_df) < 50 or len(test_df) < 20:
            continue

        X_train, y_train, encoded_cols = _prepare_training_matrix(train_df)
        X_test, y_test, _ = _prepare_training_matrix(test_df, encoded_columns=encoded_cols)

        model = XGBRegressor(**MODEL_PARAMS)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        current_price = test_df["current_close"].astype(float).to_numpy()
        metrics = _metrics(y_test, preds, current_price)

        trained[horizon] = HorizonTraining(
            horizon=horizon,
            model=model,
            metrics=metrics,
            encoded_columns=encoded_cols,
            train_count=len(train_df),
            test_count=len(test_df),
            sample_count=len(frame),
        )

    if not trained:
        raise ValueError("No horizons produced trainable datasets")
    return trained


def encode_inference_row(row: dict, encoded_columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame([row])
    for col in FEATURE_DROP_COLUMNS:
        if col in frame.columns:
            frame = frame.drop(columns=[col])
    if "industry" not in frame.columns:
        frame["industry"] = "Unknown"
    encoded = pd.get_dummies(frame, columns=["industry"], dummy_na=True)
    encoded = encoded.reindex(columns=encoded_columns, fill_value=0.0)
    return encoded.astype(float)


def _prepare_training_matrix(
    frame: pd.DataFrame,
    encoded_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    data = frame.copy()
    y = data["target_close"].astype(float).to_numpy()

    for col in FEATURE_DROP_COLUMNS:
        if col in data.columns:
            data = data.drop(columns=[col])

    if "industry" not in data.columns:
        data["industry"] = "Unknown"
    data = pd.get_dummies(data, columns=["industry"], dummy_na=True)

    if encoded_columns is None:
        encoded_columns = list(data.columns)
    data = data.reindex(columns=encoded_columns, fill_value=0.0).astype(float)
    return data, y, encoded_columns


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, current_close: np.ndarray) -> dict:
    mae = float(np.mean(np.abs(y_pred - y_true)))
    rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    denom = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1.0 - (np.sum((y_true - y_pred) ** 2) / denom)) if denom > 0 else 0.0
    nz = np.where(np.abs(y_true) > 1e-8, np.abs(y_true), np.nan)
    mape = float(np.nanmean(np.abs((y_true - y_pred) / nz)) * 100.0) if np.any(~np.isnan(nz)) else 0.0

    true_move = np.sign(y_true - current_close)
    pred_move = np.sign(y_pred - current_close)
    directional_acc = float(np.mean(pred_move == true_move))

    return {
        "mae": round(mae, 6),
        "rmse": round(rmse, 6),
        "r2": round(r2, 6),
        "mape": round(mape, 6),
        "directional_accuracy": round(directional_acc, 6),
    }
