# app.py — AI-IDS + SOAR Dashboard (All/Solved views only, Streamlit 1.48+)

import os
import json
import requests
import pandas as pd
import streamlit as st

# -------------------- CONFIG --------------------
SOAR = "http://127.0.0.1:7000"

# Which statuses count as "solved"
SOLVED_STATUSES = {"Blocked", "Quarantined", "Allowed (false alarm)", "Auto-Handled"}

# Where we persist solved tickets so they don't disappear on refresh
ARCHIVE_DIR = ".run"
ARCHIVE_PATH = os.path.join(ARCHIVE_DIR, "solved_archive.csv")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

st.set_page_config(page_title="Cyber Safety Dashboard", page_icon="🛡️", layout="wide")
st.title("🛡️ AI-IDS + SOAR Dashboard")

# -------------------- HELPERS --------------------
def fetch_incidents(limit: int = 500) -> pd.DataFrame:
    """Fetch recent incidents from SOAR API."""
    try:
        data = requests.get(f"{SOAR}/incidents/recent?limit={limit}", timeout=5).json()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame(columns=["id","time_utc","label","severity","src_ip","dst_ip","score","status"])
        df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce")
        df = df.sort_values("time_utc", ascending=False)
        return df
    except Exception:
        return pd.DataFrame(columns=["id","time_utc","label","severity","src_ip","dst_ip","score","status"])

def fetch_actions(incident_id: str) -> pd.DataFrame:
    """Get action history for an incident and normalize fields."""
    try:
        raw = requests.get(f"{SOAR}/incidents/{incident_id}/actions", timeout=5).json()
    except Exception:
        raw = []
    rows = []
    for a in raw:
        res = a.get("result_json")
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except Exception:
                res = {"raw": res}
        if not isinstance(res, dict):
            res = {}
        rows.append({
            "time_utc": a.get("time_utc"),
            "action": a.get("action"),
            "ok": res.get("ok", ""),
            "dry_run": res.get("dry_run", ""),
            "details": res.get("message") or res.get("output") or res.get("cmd") or res.get("note") or "",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce")
        df = df.sort_values("time_utc", ascending=True)
    return df

def post_json(url: str, payload: dict):
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.ok, (r.json() if r.headers.get("content-type","").startswith("application/json") else r.text)
    except Exception as e:
        return False, str(e)

# ---- archive helpers (persist solved so it never disappears) ----
def load_archive() -> pd.DataFrame:
    if os.path.exists(ARCHIVE_PATH):
        try:
            df = pd.read_csv(ARCHIVE_PATH)
            if "time_utc" in df.columns:
                df["time_utc"] = pd.to_datetime(df["time_utc"], errors="coerce")
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["id","time_utc","label","severity","src_ip","dst_ip","score","status"])

def save_archive(df: pd.DataFrame):
    df.to_csv(ARCHIVE_PATH, index=False)

def merge_into_archive(archive_df: pd.DataFrame, latest_df: pd.DataFrame) -> pd.DataFrame:
    """Add newly-solved items to archive; never remove existing ones."""
    if latest_df.empty:
        return archive_df
    solved_now = latest_df[latest_df["status"].isin(SOLVED_STATUSES)].copy()
    if solved_now.empty:
        return archive_df
    combined = pd.concat([archive_df, solved_now], ignore_index=True)
    return combined.drop_duplicates(subset=["id"], keep="last")

# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.header("Controls")

    # Remember the fetch limit across reruns
    if "fetch_limit" not in st.session_state:
        st.session_state["fetch_limit"] = 500
    st.session_state["fetch_limit"] = st.slider(
        "Fetch last N incidents from API",
        min_value=100, max_value=5000, value=st.session_state["fetch_limit"], step=100
    )

    if st.button("Refresh"):
        # refresh incidents and silently update the archive
        st.session_state["incidents_df"] = fetch_incidents(st.session_state["fetch_limit"])
        st.session_state["solved_archive"] = merge_into_archive(
            st.session_state["solved_archive"], st.session_state["incidents_df"]
        )
        save_archive(st.session_state["solved_archive"])

    st.divider()
    mode = st.radio("Quick View", ["All", "Solved"], index=0)
    st.caption("Solved view is permanent (stored in .run/solved_archive.csv).")

# -------------------- FIRST LOAD --------------------
if "incidents_df" not in st.session_state:
    st.session_state["incidents_df"] = fetch_incidents(st.session_state["fetch_limit"])
if "solved_archive" not in st.session_state:
    st.session_state["solved_archive"] = load_archive()

df_all = st.session_state["incidents_df"].copy()
archive = st.session_state["solved_archive"].copy()

# -------------------- VIEW FILTER --------------------
df_view = archive.copy() if mode == "Solved" else df_all.copy()

st.caption(f"View: **{mode}** | Showing {len(df_view)} items.")
st.dataframe(
    df_view[["id","time_utc","severity","label","src_ip","dst_ip","score","status"]],
    use_container_width=True,
    hide_index=True,
)

# -------------------- SELECTION & ACTIONS --------------------
if not df_view.empty:
    ids = df_view["id"].astype(str).tolist()
    default_id = st.session_state.get("selected_id", ids[0])
    if default_id not in ids:
        default_id = ids[0]

    selected_id = st.selectbox("Pick an incident", ids, index=ids.index(default_id), key="selected_id")
    row = df_view[df_view["id"].astype(str) == selected_id].iloc[0].to_dict()

    st.subheader(f"Incident {selected_id}")
    current_status = str(row.get("status", "")).strip()

    # Disable manual actions for these statuses
    DISABLE_STATUSES = {"Auto-Handled","Blocked","Quarantined","Escalated","Allowed (false alarm)"}
    disable_actions = current_status in DISABLE_STATUSES
    if disable_actions:
        st.info(f"🔒 Manual actions are disabled because this incident status is **{current_status}**.")
    else:
        st.caption("You can take one of the actions below. (Dry-run unless SOAR_DRY_RUN=false)")

    def do_and_refresh(endpoint: str, payload: dict, success_msg="Done."):
        ok, res = post_json(f"{SOAR}{endpoint}", payload)
        if ok:
            # After actions, refresh & merge so Solved archive stays current
            st.session_state["incidents_df"] = fetch_incidents(st.session_state["fetch_limit"])
            st.session_state["solved_archive"] = merge_into_archive(
                st.session_state["solved_archive"], st.session_state["incidents_df"]
            )
            save_archive(st.session_state["solved_archive"])
            st.success(success_msg)
            st.rerun()  # Streamlit 1.48+
        else:
            st.error(f"Action failed: {res}")

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("🚫 Block source IP", disabled=disable_actions):
        do_and_refresh("/actions/block_ip", {"incident_id": selected_id, "source": row.get("src_ip","")}, "Block command sent.")
    if c2.button("🖥️ Quarantine device", disabled=disable_actions):
        do_and_refresh("/actions/quarantine", {"incident_id": selected_id, "source": row.get("src_ip","")}, "Quarantine sent.")
    if c3.button("✅ Allow (false alarm)", disabled=disable_actions):
        do_and_refresh("/actions/allow_false_positive", {"incident_id": selected_id, "note": "User marked safe"}, "Marked as allowed.")
    if c4.button("📣 Escalate", disabled=disable_actions):
        do_and_refresh("/actions/escalate", {"incident_id": selected_id}, "Escalated.")

    st.markdown("**Details**")
    st.json(row)

    st.markdown("**Action History**")
    actions_df = fetch_actions(selected_id)
    if actions_df.empty:
        st.info("No actions recorded yet for this incident.")
    else:
        st.dataframe(actions_df, use_container_width=True, hide_index=True)

else:
    st.info("No incidents in this view. Click 'Refresh' or switch Quick View.")

# -------------------- SIDEBAR EXPORT (Solved only) --------------------
with st.sidebar:
    st.divider()
    if mode == "Solved":
        solved_df = df_view.copy()
        st.subheader("Solved IDs")
        ids_list = solved_df["id"].astype(str).tolist()
        st.code("\n".join(ids_list) or "(none)", language="text")
        solved_csv = solved_df[["id","time_utc","label","severity","src_ip","dst_ip","score","status"]].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export Solved CSV", solved_csv, file_name="solved_incidents.csv", mime="text/csv")
