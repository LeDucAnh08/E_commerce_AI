from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DATA_PATH = DATA_DIR / "user_behavior_sessions.csv"
DEFAULT_MODEL_PATH = BASE_DIR / "ai_service" / "lstm" / "model_lstm.keras"
DEFAULT_ENCODER_PATH = BASE_DIR / "ai_service" / "lstm" / "encoders.json"

ACTIONS = ["view", "click", "add_to_cart", "buy"]


def _ensure_dataset(path: Path, rows: int = 300, users: int = 5, products: int = 25) -> Path:
    if path.exists():
        return path
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 4, 1, 9, 0, 0)
    data = []
    for i in range(rows):
        user_id = random.randint(1, users)
        product_id = random.randint(100, 100 + products - 1)
        action = random.choice(ACTIONS)
        timestamp = start + timedelta(minutes=i)
        session_id = f"s{(i // 20) + 1}"
        data.append((user_id, product_id, action, timestamp.isoformat(sep=" "), session_id))
    df = pd.DataFrame(data, columns=["user_id", "product_id", "action", "timestamp", "session_id"])
    df.to_csv(path, index=False)
    return path


def _load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required_cols = {"user_id", "product_id", "action", "timestamp"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required_cols}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["user_id", "action", "timestamp"]).copy()
    sort_cols = ["user_id", "timestamp"]
    if "session_id" in df.columns:
        sort_cols = ["user_id", "session_id", "timestamp"]
    return df.sort_values(sort_cols).reset_index(drop=True)


def _encode_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, LabelEncoder, LabelEncoder]:
    action_encoder = LabelEncoder()
    product_encoder = LabelEncoder()
    df["action_enc"] = action_encoder.fit_transform(df["action"].astype(str))
    df["product_enc"] = product_encoder.fit_transform(df["product_id"].astype(str))
    return df, action_encoder, product_encoder


def _make_sequences(
    df: pd.DataFrame,
    seq_len: int,
    feature_cols: list[str],
    target_col: str,
) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    group_cols = ["user_id"]
    if "session_id" in df.columns:
        group_cols.append("session_id")
    for _, grp in df.groupby(group_cols):
        features = grp[feature_cols].to_numpy().tolist()
        targets = grp[target_col].tolist()
        for i in range(len(targets) - seq_len):
            X.append(features[i : i + seq_len])
            y.append(targets[i + seq_len])
    return np.array(X), np.array(y)


def _build_lstm(seq_len: int, num_features: int, num_classes: int):
    import tensorflow as tf
    from tensorflow.keras.layers import LSTM, Dense
    from tensorflow.keras.models import Sequential

    model = Sequential(name="lstm_recommender")
    model.add(LSTM(64, input_shape=(seq_len, num_features)))
    model.add(Dense(32, activation="relu"))
    model.add(Dense(num_classes, activation="softmax"))
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    return model


def _save_encoders(path: Path, action_encoder: LabelEncoder, product_encoder: LabelEncoder, seq_len: int) -> None:
    payload = {
        "action_classes": action_encoder.classes_.tolist(),
        "product_classes": product_encoder.classes_.tolist(),
        "seq_len": int(seq_len),
        "feature_cols": ["action_enc", "product_enc"],
        "target_col": "product_enc",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_encoders(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def train_lstm(
    data_path: Path,
    model_path: Path,
    encoder_path: Path,
    seq_len: int = 5,
    epochs: int = 6,
    batch_size: int = 32,
) -> None:
    df = _load_dataset(data_path)
    df, action_encoder, product_encoder = _encode_columns(df)
    X, y = _make_sequences(df, seq_len, ["action_enc", "product_enc"], "product_enc")
    if len(X) == 0:
        raise ValueError("No sequences created. Increase data size or reduce seq_len.")
    X = X.astype("float32")
    num_classes = len(product_encoder.classes_)

    import tensorflow as tf

    y_cat = tf.keras.utils.to_categorical(y, num_classes=num_classes)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_cat,
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )
    model = _build_lstm(seq_len, X.shape[2], num_classes)
    model.fit(
        X_train,
        y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_test, y_test),
        verbose=0,
    )
    model.save(model_path)
    _save_encoders(encoder_path, action_encoder, product_encoder, seq_len)


def _coerce_product_id(value: str):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def predict_topn(
    user_id: int,
    top_n: int = 5,
    data_path: Path = DEFAULT_DATA_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    encoder_path: Path = DEFAULT_ENCODER_PATH,
) -> list:
    df = _load_dataset(data_path)
    enc = _load_encoders(encoder_path)
    seq_len = int(enc.get("seq_len", 5))
    action_classes = [str(x) for x in enc["action_classes"]]
    product_classes = [str(x) for x in enc["product_classes"]]
    action_to_idx = {value: idx for idx, value in enumerate(action_classes)}
    product_to_idx = {value: idx for idx, value in enumerate(product_classes)}

    user_rows = df[df["user_id"] == user_id]
    if user_rows.empty or len(user_rows) < seq_len:
        return []
    sort_cols = ["user_id", "timestamp"]
    if "session_id" in user_rows.columns:
        sort_cols = ["user_id", "session_id", "timestamp"]
    user_rows = user_rows.sort_values(sort_cols).tail(seq_len)

    features = []
    for _, row in user_rows.iterrows():
        action_idx = action_to_idx.get(str(row["action"]))
        product_idx = product_to_idx.get(str(row["product_id"]))
        if action_idx is None or product_idx is None:
            return []
        features.append([action_idx, product_idx])

    X = np.array([features], dtype="float32")

    import tensorflow as tf

    model = tf.keras.models.load_model(model_path)
    probs = model.predict(X, verbose=0)[0]
    top_indices = np.argsort(probs)[::-1][:top_n]
    return [_coerce_product_id(product_classes[idx]) for idx in top_indices]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train LSTM model and run predict_topn.")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_PATH), help="CSV dataset path")
    parser.add_argument("--model-path", type=str, default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--encoder-path", type=str, default=str(DEFAULT_ENCODER_PATH))
    parser.add_argument("--seq-len", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--generate-fake", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    data_path = Path(args.data)
    if args.generate_fake:
        data_path = _ensure_dataset(data_path)

    if args.validate_only:
        df = _load_dataset(data_path)
        print(f"Loaded rows: {len(df)}")
        print(f"Users: {df['user_id'].nunique()}")
        return

    train_lstm(
        data_path=data_path,
        model_path=Path(args.model_path),
        encoder_path=Path(args.encoder_path),
        seq_len=args.seq_len,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )

    topn = predict_topn(
        user_id=args.user_id,
        top_n=args.top_n,
        data_path=data_path,
        model_path=Path(args.model_path),
        encoder_path=Path(args.encoder_path),
    )
    print(f"predict_topn(user_id={args.user_id}) => {topn}")


if __name__ == "__main__":
    main()
