# AI-Driven IDS with SOAR-lite Integration

An AI-driven Intrusion Detection System (IDS) integrated with a lightweight SOAR backend, designed to improve financial-sector cybersecurity.  
This system uses a RandomForest model trained on the CICIDS2017 dataset, with FastAPI services for scoring and SOAR orchestration, and a Streamlit analyst console for interactive triage.

---

## 📌 Features

- **Machine Learning IDS**: RandomForest classifier trained on CICIDS2017.
- **SOAR-lite backend**: FastAPI service with YAML playbooks for automated responses.
- **Analyst Console**: Streamlit dashboard for monitoring incidents and applying manual/auto actions.
- **One-click startup**: `start_system.py` launches all components.
- **Reproducibility**:
  - Fixed seeds, pinned dependencies.
  - Persisted model artifacts (`.joblib`, `.json`).
  - Action history stored in `.run/solved_archive.csv`.

---

## 🏗️ Architecture

```
[Replay Harness] → [Model API (FastAPI)] → [SOAR-lite Backend] → [Streamlit Console]
```

- **Replay Harness** (`replay_from_parquet.py`): Feeds CICIDS2017 events for demo.
- **Model API** (`score_api.py`): Exposes `/score` endpoint for predictions.
- **SOAR-lite API** (`soar_api.py`): Executes or simulates response playbooks.
- **Streamlit Console** (`app.py`): UI for analysts with incident triage tools.

---

## 📂 Project Structure

```
ai-ids-soar/
│
├── app.py                  # Streamlit analyst console
├── score_api.py            # FastAPI scoring service
├── soar_api.py             # SOAR-lite backend
├── actions.py              # SOAR actions (block_ip, quarantine, escalate)
├── replay_from_parquet.py  # Data replay harness
├── start_system.py         # One-click launcher
│
├── models/                 # ML artifacts
│   ├── rf_model.joblib
│   ├── scaler.joblib
│   ├── label_encoder.joblib
│   └── feature_list.json
│
├── reports/                # Confusion matrix, ROC, evaluation plots
├── .run/                   # Solved incidents archive
│
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
└── LICENSE                 # (optional)
```

---

## ⚙️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/ai-ids-soar.git
cd ai-ids-soar
```

### 2. Create Virtual Environment
> ⚠️ Use **Python 3.11 (x64 venv)**, since this system was built on Windows ARM using an x64 emulation environment.

```bash
python -m venv venv_x64
venv_x64\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the System
```bash
python start_system.py
```

This launches:
- Model API on **http://localhost:8000**
- SOAR-lite API on **http://localhost:7000**
- Analyst Console on **http://localhost:8501**

---

## 🎛️ Usage

1. Open the **Streamlit Console** in your browser: `http://localhost:8501`
2. Replay dataset events using:
   ```bash
   python replay_from_parquet.py
   ```
3. Monitor alerts in the console:
   - View **All Incidents**  
   - Mark incidents as **Solved** (persistent archive in `.run/solved_archive.csv`)  
   - Apply SOAR actions: `block_ip`, `quarantine_host`, `allow_false_positive`, `escalate`.

---

## 📊 Evaluation

Evaluation utilities (`evaluate_and_plots.py`) generate:
- Confusion Matrix
- Per-class Precision/Recall bars
- ROC Curves
- Accuracy/F1 charts

All results are saved in `/reports`.

---

## 🚨 SOAR-lite Actions

Implemented in `actions.py`:
- **block_ip** → Blocks traffic (Windows: `netsh`, Linux: `iptables` fallback).
- **quarantine_host** → Isolates machine (dry-run mode).
- **notify** → Logs alert/escalation.
- **escalate** → Flags for higher-level review.

> Dry-run is enabled by default (`SOAR_DRY_RUN=true`).

---

## 📜 Limitations

- Runs on **Windows only** (tested on Windows 11 ARM laptop).
- Dataset limited to **CICIDS2017** (no live traffic or UNSW-NB15).
- SOAR-lite is **not full StackStorm**, but extendable.
- Suricata integration left as **future work**.

---

## 🧑‍🎓 Academic Citation

This repository supports the Master of Applied IT thesis:

> *Ravin Ghimire (2025). "AI-Driven IDS and SOAR Integration for Financial Cybersecurity" — Victoria University, Sydney.*

If citing in academic work, please reference this repository link:  
👉 [https://github.com/ravin9860/ai-ids-soar](https://github.com/ravin9860/ai-ids-soar)

---

## 📄 License

MIT License – Free to use for research and education.
