# start_system.py
from pathlib import Path
import subprocess, time, os, sys, signal
import requests

BASE = Path(__file__).resolve().parent
PYTHON = sys.executable  # use the Python running this script (i.e. the active venv)
RUN_DIR = BASE / ".run"
LOG_DIR = RUN_DIR / "logs"
RUN_DIR.mkdir(exist_ok=True, parents=True)
LOG_DIR.mkdir(exist_ok=True, parents=True)

MODEL_PORT = "8000"
SOAR_PORT  = "7000"

ENV = os.environ.copy()
ENV.setdefault("SOAR_DRY_RUN", "true")  # change to "false" for real blocking (run as Admin)

def start(name, args, logfile):
    print(f"▶ Starting {name}…")
    f = open(LOG_DIR / logfile, "w", buffering=1, encoding="utf-8", errors="replace")
    p = subprocess.Popen([PYTHON, *args], cwd=BASE, env=ENV,
                         stdout=f, stderr=subprocess.STDOUT)
    return p, f

def wait_health(url, name, timeout=30):
    print(f"⏳ Waiting for {name} health at {url} …")
    t0 = time.time()
    last_error = None
    while time.time() - t0 < timeout:
        try:
            r = requests.get(url, timeout=3)
            if r.ok: 
                print(f"✅ {name} is up.")
                return True
        except Exception as e:
            last_error = e
        time.sleep(1)
    print(f"❌ {name} did not become healthy: {last_error}")
    return False

def terminate(name, proc, file):
    if proc and proc.poll() is None:
        print(f"⏹ Stopping {name} …")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
    try:
        file.close()
    except Exception:
        pass

if __name__ == "__main__":
    model = soar = replay = None
    model_log = soar_log = replay_log = None
    try:
        # 1) Model API
        model, model_log = start(
            "Model API",
            ["-m", "uvicorn", "ml-ids.score_api:app", "--reload", "--port", MODEL_PORT],
            "model_api.log"
        )
        wait_health(f"http://127.0.0.1:{MODEL_PORT}/health", "Model API")

        # 2) SOAR API
        soar, soar_log = start(
            "SOAR API",
            ["-m", "uvicorn", "soar.soar_api:app", "--reload", "--port", SOAR_PORT],
            "soar_api.log"
        )
        wait_health(f"http://127.0.0.1:{SOAR_PORT}/health", "SOAR API")

        # 3) Traffic replay (non-blocking)
        replay, replay_log = start(
            "Traffic Replay",
            ["scripts/replay_from_parquet.py"],
            "replay.log"
        )

        print("\n🖥️  Launching Streamlit dashboard (Ctrl+C here to stop all)…\n")
        # 4) Streamlit (blocking in foreground)
        subprocess.call([PYTHON, "-m", "streamlit", "run", "app.py"], cwd=BASE, env=ENV)

    except KeyboardInterrupt:
        print("\n🔻 Ctrl+C pressed — shutting down…")
    finally:
        terminate("Traffic Replay", replay, replay_log)
        terminate("SOAR API",      soar,   soar_log)
        terminate("Model API",     model,  model_log)
        print("✅ All processes stopped. Logs in ./.run/logs")
