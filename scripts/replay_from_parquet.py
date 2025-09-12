import os, glob, json, time, random
import pandas as pd
import requests
from datetime import datetime

DATA_DIR = os.path.join("data","cicids2017_csv")
FEATURES = json.load(open("models/feature_list.json"))
SCORE = "http://127.0.0.1:8000/score"
SOAR  = "http://127.0.0.1:7000/incidents"

def iter_rows(limit_per_file=200):
    files = glob.glob(os.path.join(DATA_DIR, "**", "*.parquet"), recursive=True)
    for path in files:
        try:
            df = pd.read_parquet(path)
            cols = [c for c in FEATURES if c in df.columns]
            if not cols:
                continue
            take = min(limit_per_file, len(df))
            sample = df.sample(take, random_state=42)
            for _, row in sample.iterrows():
                feats = {k: float(row.get(k, 0.0)) for k in FEATURES}
                meta = {
                    "time_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": f"192.168.1.{random.randint(2,254)}",
                    "destination": f"10.0.0.{random.randint(2,254)}"
                }
                yield {"features": feats, "meta": meta}
        except Exception as e:
            print("skip", path, e)

if __name__ == "__main__":
    sent = 0
    for payload in iter_rows(limit_per_file=200):
        try:
            s = requests.post(SCORE, json=payload, timeout=5).json()
            inc = {
                "time_utc": payload["meta"]["time_utc"],
                "label": s["label"],
                "severity": s["severity"],
                "probability": s["probability"],
                "source": payload["meta"]["source"],
                "destination": payload["meta"]["destination"],
                "meta": payload["meta"]
            }
            r = requests.post(SOAR, json=inc, timeout=5)
            sent += 1
            if sent % 50 == 0:
                print("sent", sent, "incidents; last", s["label"], s["severity"], "status", r.status_code)
            time.sleep(0.02)
        except Exception as e:
            print("error:", e)
    print("done. total sent:", sent)
