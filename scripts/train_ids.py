import os, glob, json, warnings
import numpy as np, pandas as pd
from pandas.api.types import is_numeric_dtype, is_categorical_dtype
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight
import joblib

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

DATA_DIR   = os.path.join("data", "cicids2017_csv")
MODEL_DIR  = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

# ---- find files (csv or parquet, including subfolders) ----
csv_files = glob.glob(os.path.join(DATA_DIR, "**", "*.csv"), recursive=True)
pq_files  = glob.glob(os.path.join(DATA_DIR, "**", "*.parquet"), recursive=True)
files = csv_files + pq_files
assert files, f"No CSV/Parquet found under {DATA_DIR}"

print(f"Found {len(files)} files")
for f in files:
    print(" -", os.path.relpath(f, DATA_DIR))

# label hints from filenames when a label column is missing
file_label_map = {
    "Benign": "Benign",
    "Botnet": "Bot",
    "Bruteforce": "Brute Force",
    "DDoS": "DoS/DDoS",
    "DoS": "DoS/DDoS",
    "Infiltration": "Infiltration",
    "Portscan": "PortScan",
    "WebAttacks": "Web Attack",
}

normalize_label_map = {
    "BENIGN": "Benign",
    "Benign": "Benign",
    "PortScan": "PortScan", "Portscan": "PortScan",
    "Botnet": "Bot", "Bot": "Bot",
    "Infiltration": "Infiltration",
    "Heartbleed": "Heartbleed",
    "DDoS": "DoS/DDoS",
    "DoS Hulk": "DoS/DDoS", "DoS GoldenEye": "DoS/DDoS",
    "DoS slowloris": "DoS/DDoS", "DoS Slowhttptest": "DoS/DDoS",
    "FTP-Patator": "Brute Force", "SSH-Patator": "Brute Force",
    "Web Attack - Brute Force": "Web Attack", "Web Attack - XSS": "Web Attack",
    "Web Attack - Sql Injection": "Web Attack",
    "WebAttacks": "Web Attack",
    "Bruteforce": "Brute Force",
}

def infer_label_from_filename(path):
    token = os.path.basename(path).split("-")[0]
    return file_label_map.get(token, token)

def to_numeric_safe(series: pd.Series) -> pd.Series:
    # convert categorical/object to string first, then to numeric
    if is_categorical_dtype(series) or series.dtype == object:
        series = series.astype(str)
    return pd.to_numeric(series, errors="coerce")

def load_one(path):
    # read
    if path.lower().endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, low_memory=False)

    # unify/make label
    label_candidates = [c for c in df.columns if c.lower() in ("label","class","attack","category","target")]
    if label_candidates:
        lbl = label_candidates[0]
        df.rename(columns={lbl: "Label"}, inplace=True)
        df["Label"] = df["Label"].map(lambda x: normalize_label_map.get(str(x), str(x)))
    else:
        df["Label"] = infer_label_from_filename(path)

    # drop obvious IDs / text cols if present
    drop_candidates = [c for c in ["Flow ID","Source IP","Destination IP","Timestamp","Src IP","Dst IP"] if c in df.columns]
    df = df.drop(columns=drop_candidates, errors="ignore")

    # make every non-Label column numeric safely
    for c in df.columns:
        if c == "Label":
            continue
        if not is_numeric_dtype(df[c]):
            df[c] = to_numeric_safe(df[c])

    # clean up
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df = df.fillna(0.0)

    return df

# ---- load all files ----
dfs = []
for i, f in enumerate(files, 1):
    print(f"[{i}/{len(files)}] loading:", os.path.relpath(f, DATA_DIR))
    try:
        df = load_one(f)
        dfs.append(df)
    except Exception as e:
        print("  !! Skipped due to error:", e)

raw = pd.concat(dfs, ignore_index=True)
print("Combined shape:", raw.shape)
assert "Label" in raw.columns, "Label column missing after load"

# keep only numeric features + label
feature_cols = [c for c in raw.columns if c != "Label" and is_numeric_dtype(raw[c])]
df = raw[feature_cols + ["Label"]].copy()

# ---- encode labels ----
y_text = df["Label"].astype(str).values
le = LabelEncoder()
y = le.fit_transform(y_text)
X = df[feature_cols].values.astype(np.float32)

# ---- splits ----
X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.4, random_state=42, stratify=y)
X_val, X_test, y_val, y_test    = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp)

# ---- scale & weight ----
scaler = StandardScaler(with_mean=False)
X_train_s = scaler.fit_transform(X_train)
X_val_s   = scaler.transform(X_val)
X_test_s  = scaler.transform(X_test)
w_train = compute_sample_weight(class_weight="balanced", y=y_train)

# ---- train ----
clf = RandomForestClassifier(
    n_estimators=400,
    max_depth=None,
    n_jobs=-1,
    class_weight="balanced_subsample",
    random_state=42
)
clf.fit(X_train_s, y_train, sample_weight=w_train)

def report(split, Xs, ys):
    yp = clf.predict(Xs)
    print(f"\n=== {split} report ===")
    print(classification_report(ys, yp, target_names=le.classes_, digits=4))
    print("Confusion matrix:\n", confusion_matrix(ys, yp))

report("VAL", X_val_s, y_val)
report("TEST", X_test_s, y_test)

# ---- save artifacts ----
joblib.dump(clf, os.path.join(MODEL_DIR, "rf_model.joblib"))
joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.joblib"))
joblib.dump(le, os.path.join(MODEL_DIR, "label_encoder.joblib"))
with open(os.path.join(MODEL_DIR, "feature_list.json"), "w") as f:
    json.dump(feature_cols, f)

print("\nSaved artifacts in ./models : rf_model.joblib, scaler.joblib, label_encoder.joblib, feature_list.json")
