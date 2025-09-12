import json, joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List

app = FastAPI(title="AI-IDS Scoring API")

MODEL_PATH = "models/rf_model.joblib"
SCALER_PATH = "models/scaler.joblib"
ENC_PATH   = "models/label_encoder.joblib"
FEAT_PATH  = "models/feature_list.json"

model  = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
le     = joblib.load(ENC_PATH)
feature_list: List[str] = json.load(open(FEAT_PATH))

SEVERITY_RULES = {
    "DoS/DDoS":  {"crit":0.90, "high":0.75, "med":0.60},
    "Bot":       {"crit":0.90, "high":0.75, "med":0.60},
    "Infiltration":{"crit":0.85, "high":0.70, "med":0.60},
    "Brute Force":{"crit":0.90, "high":0.75, "med":0.60},
    "Web Attack":{"crit":0.85, "high":0.70, "med":0.60},
    "Heartbleed":{"crit":0.85, "high":0.70, "med":0.60},
    "PortScan":  {"crit":0.85, "high":0.70, "med":0.60},
    "Benign":    {"crit":1.01, "high":1.01, "med":1.01}
}

class Flow(BaseModel):
    features: Dict[str, float]
    meta: Dict[str, Any] = {}

def severity(label: str, prob: float) -> str:
    r = SEVERITY_RULES.get(label, {"crit":0.90,"high":0.75,"med":0.60})
    if prob >= r["crit"]: return "Critical"
    if prob >= r["high"]: return "High"
    if prob >= r["med"]:  return "Medium"
    return "Low"

@app.get("/health")
def health():
    return {"ok": True, "n_features": len(feature_list)}

@app.post("/score")
def score(flow: Flow):
    x = np.array([flow.features.get(k, 0.0) for k in feature_list], dtype=np.float32).reshape(1, -1)
    xs = scaler.transform(x)
    proba = model.predict_proba(xs)[0]
    idx = int(np.argmax(proba))
    label = le.inverse_transform([idx])[0]
    p = float(proba[idx])

    importances = getattr(model, "feature_importances_", None)
    why = []
    if importances is not None:
        arr = xs.toarray() if hasattr(xs, "toarray") else xs
        weights = np.abs(arr)[0] * importances
        topk = np.argsort(weights)[-3:][::-1]
        why = [feature_list[i] for i in topk]

    return {
        "label": label,
        "probability": round(p, 4),
        "severity": severity(label, p),
        "explain_top_features": why,
        "meta": flow.meta
    }
