import argparse 
import os 
import random 
from pathlib import Path 
 
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2" 
 
try: 
    import matplotlib 
except ModuleNotFoundError as exc: 
    raise SystemExit( 
        "Missing dependency: matplotlib. Run: pip install -r requirements_assignment.txt" 
    ) from exc 
 
matplotlib.use("Agg") 
import matplotlib.pyplot as plt 
import numpy as np 
import pandas as pd 
try: 
    import tensorflow as tf 
except ModuleNotFoundError as exc: 
    raise SystemExit( 
        "Missing dependency: tensorflow. Run: pip install -r requirements_assignment.txt" 
    ) from exc 
from sklearn.model_selection import train_test_split 
from sklearn.metrics import ( 
    accuracy_score, 
    classification_report, 
    confusion_matrix, 
    precision_recall_fscore_support, 
) 
 
from sklearn.preprocessing import LabelEncoder 
from tensorflow.keras.layers import Bidirectional, Dense, LSTM, SimpleRNN 
from tensorflow.keras.models import Sequential 
 
def set_seed(seed: int = 42) -> None: 
    random.seed(seed) 
    np.random.seed(seed) 
    tf.random.set_seed(seed) 
 
def make_sequences(
    df: pd.DataFrame,
    seq_len: int = 5,
    feature_cols: list[str] | None = None,
    target_col: str = "action_enc",
) -> tuple[np.ndarray, np.ndarray]:
    if feature_cols is None:
        feature_cols = ["action_enc", "product_enc"]

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
 
def build_model(model_type: str, seq_len: int, num_classes: int, num_features: int) -> Sequential: 
    model = Sequential(name=f"{model_type}_classifier") 
 
    if model_type == "RNN": 
        model.add(SimpleRNN(64, input_shape=(seq_len, num_features))) 
    elif model_type == "LSTM": 
        model.add(LSTM(64, input_shape=(seq_len, num_features))) 
    elif model_type == "biLSTM": 
        model.add(Bidirectional(LSTM(64), input_shape=(seq_len, num_features))) 
    else: 
        raise ValueError(f"Unsupported model type: {model_type}") 
 
    model.add(Dense(32, activation="relu")) 
    model.add(Dense(num_classes, activation="softmax")) 
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"]) 
    return model


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> dict: 
    precision, recall, f1, _ = precision_recall_fscore_support( 
        y_true, 
        y_pred, 
        average="macro", 
        zero_division=0, 
    ) 
    return { 
        "accuracy": float(accuracy_score(y_true, y_pred)), 
        "precision_macro": float(precision), 
        "recall_macro": float(recall), 
        "f1_macro": float(f1), 
    } 


def plot_training_curves(histories: dict, output_path: Path) -> None: 
    plt.figure(figsize=(10, 6)) 
    for name, history in histories.items(): 
        plt.plot(history.history.get("val_accuracy", []), label=f"{name} val_acc") 
    plt.title("Validation Accuracy Comparison") 
    plt.xlabel("Epoch") 
    plt.ylabel("Accuracy") 
    plt.legend() 
    plt.tight_layout() 
    plt.savefig(output_path) 
    plt.close() 


def plot_confusion_matrix(cm: np.ndarray, class_names: list[str], output_path: Path) -> None: 
    plt.figure(figsize=(8, 6)) 
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues) 
    plt.title("Confusion Matrix") 
    plt.colorbar() 
    tick_marks = np.arange(len(class_names)) 
    plt.xticks(tick_marks, class_names, rotation=45, ha="right") 
    plt.yticks(tick_marks, class_names) 
    plt.tight_layout() 
    plt.ylabel("True label") 
    plt.xlabel("Predicted label") 
    plt.savefig(output_path) 
    plt.close() 


def select_best_model(metrics_df: pd.DataFrame, metric: str) -> pd.Series: 
    return metrics_df.sort_values(metric, ascending=False).iloc[0] 


def build_verbal_assessment( 
    metrics_df: pd.DataFrame, 
    best_row: pd.Series, 
    primary_metric: str, 
) -> str: 
    lines = [
        "Model comparison summary:", 
        metrics_df.to_string(index=False), 
        "", 
        f"Best model by {primary_metric}: {best_row['model']}", 
        f"{primary_metric}: {best_row[primary_metric]:.4f}", 
        f"Accuracy: {best_row['accuracy']:.4f}", 
    ] 
    return "\n".join(lines) 


def main() -> None: 
    parser = argparse.ArgumentParser(description="Train RNN/LSTM/biLSTM for next-action prediction") 
    parser.add_argument("--data", type=str, default="data_user500.csv", help="Input CSV file") 
    parser.add_argument("--seq-len", type=int, default=5, help="Sequence length") 
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs") 
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size") 
    parser.add_argument("--seed", type=int, default=42, help="Random seed") 
    parser.add_argument( 
        "--output-dir", 
        type=str, 
        default=".", 
 
        help="Directory to save chart and metrics", 
    ) 
    parser.add_argument( 
        "--primary-metric", 
        type=str, 
        default="f1_macro", 
        choices=["f1_macro", "accuracy", "precision_macro", "recall_macro"], 
        help="Metric used to select model_best", 
    ) 
    args = parser.parse_args() 
 
    set_seed(args.seed) 
 
    data_path = Path(args.data) 
    output_dir = Path(args.output_dir) 
    output_dir.mkdir(parents=True, exist_ok=True) 
 
    df = pd.read_csv(data_path) 
    required_cols = {"user_id", "product_id", "action", "timestamp"} 
    if not required_cols.issubset(df.columns): 
        raise ValueError(f"CSV must contain columns: {required_cols}") 
 
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce") 
    df = df.dropna(subset=["user_id", "action", "timestamp"]).copy() 
 
    le_action = LabelEncoder() 
    df["action_enc"] = le_action.fit_transform(df["action"]) 

    le_product = LabelEncoder() 
    df["product_enc"] = le_product.fit_transform(df["product_id"].astype(str)) 
 
    sort_cols = ["user_id", "timestamp"]
    if "session_id" in df.columns:
        sort_cols = ["user_id", "session_id", "timestamp"]
    df = df.sort_values(sort_cols).reset_index(drop=True) 
 
    X, y = make_sequences(df, args.seq_len) 
    if len(X) == 0: 
        raise ValueError("No sequences created. Increase data size or reduce --seq-len.") 
 
    X = X.astype("float32") 
    num_classes = len(le_action.classes_) 
    y_cat = tf.keras.utils.to_categorical(y, num_classes=num_classes) 
    num_features = X.shape[2]

    weight_map = {
        "buy": 3.0,
        "add_to_cart": 2.0,
        "view": 1.0,
        "click": 1.0,
    }
    action_to_weight = {
        int(le_action.transform([action])[0]): float(weight)
        for action, weight in weight_map.items()
        if action in le_action.classes_
    }
    sample_weights = np.array([action_to_weight.get(int(label), 1.0) for label in y])
 
    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split( 
        X, 
        y_cat, 
        sample_weights,
        test_size=0.2, 
        random_state=args.seed, 
        shuffle=True, 
    ) 
 
    histories = {} 
    trained_models = {} 
    predictions = {} 
    metrics_rows = [] 
 
    y_true = np.argmax(y_test, axis=1) 
 
    for name in ["RNN", "LSTM", "biLSTM"]: 
        print(f"\nTraining {name}...") 
 
        model = build_model(name, args.seq_len, num_classes, num_features) 
        history = model.fit( 
            X_train, 
            y_train, 
            sample_weight=w_train,
            epochs=args.epochs, 
            batch_size=args.batch_size, 
            validation_data=(X_test, y_test), 
            verbose=0, 
        ) 
        histories[name] = history 
        trained_models[name] = model 
 
        loss, acc = model.evaluate(X_test, y_test, verbose=0) 
 
        y_prob = model.predict(X_test, verbose=0) 
        y_pred = np.argmax(y_prob, axis=1) 
        predictions[name] = y_pred 
        cls_scores = evaluate_predictions(y_true, y_pred) 
 
        print( 
            f"{name} - Acc: {cls_scores['accuracy']:.4f}, " 
            f"F1_macro: {cls_scores['f1_macro']:.4f}, " 
            f"Loss: {loss:.4f}" 
        ) 
        metrics_rows.append( 
            { 
                "model": name, 
                "test_loss": float(loss), 
                "accuracy": float(acc), 
                "precision_macro": cls_scores["precision_macro"], 
                "recall_macro": cls_scores["recall_macro"], 
                "f1_macro": cls_scores["f1_macro"], 
                "num_samples": int(len(X)), 
                "seq_len": int(args.seq_len), 
                "num_classes": int(num_classes), 
            } 
        ) 
 
    chart_path = output_dir / "model_comparison.png" 
    plot_training_curves(histories, chart_path) 
    print(f"Saved chart to: {chart_path.resolve()}") 
 
    metrics_df = pd.DataFrame(metrics_rows) 
    metrics_path = output_dir / "model_metrics.csv" 
    metrics_df.to_csv(metrics_path, index=False) 
    print(f"Saved metrics to: {metrics_path.resolve()}") 
 
    best_row = select_best_model(metrics_df, args.primary_metric) 
    best_model_name = str(best_row["model"]) 
    best_model = trained_models[best_model_name] 
    best_pred = predictions[best_model_name] 
 
    best_model_path = output_dir / "model_best.keras" 
    best_model.save(best_model_path) 
    print(f"Saved model_best to: {best_model_path.resolve()}") 
 
 
    class_names = [str(x) for x in le_action.classes_.tolist()] 
    cm = confusion_matrix(y_true, best_pred, labels=np.arange(num_classes)) 
    cm_path = output_dir / "model_best_confusion_matrix.png" 
    plot_confusion_matrix(cm, class_names, cm_path) 
    print(f"Saved confusion matrix to: {cm_path.resolve()}") 
 
    cls_report = classification_report( 
        y_true, 
        best_pred, 
        target_names=class_names, 
        digits=4, 
        zero_division=0, 
    ) 
    cls_report_path = output_dir / "model_best_classification_report.txt" 
    cls_report_path.write_text(cls_report, encoding="utf-8") 
    print(f"Saved classification report to: {cls_report_path.resolve()}") 
 
    verbal = build_verbal_assessment(metrics_df, best_row, args.primary_metric) 
    verbal_path = output_dir / "model_best_report.txt" 
    verbal_path.write_text(verbal, encoding="utf-8") 
    print(f"Saved verbal evaluation to: {verbal_path.resolve()}") 
 
    print("\n===== MODEL_BEST SELECTION =====") 
    print( 
        f"model_best: {best_model_name} | " 
        f"{args.primary_metric}: {best_row[args.primary_metric]:.4f} | " 
        f"accuracy: {best_row['accuracy']:.4f}" 
    )


if __name__ == "__main__":
    main()