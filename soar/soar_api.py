from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid, yaml

from .storage import add_incident, list_incidents, add_action, update_status, list_actions
from . import actions as act

app = FastAPI(title="SOAR-lite")
PLAYBOOKS = yaml.safe_load(open("soar/playbooks.yml", "r"))

class IncidentIn(BaseModel):
    id: Optional[str] = None
    time_utc: str
    label: str
    severity: str
    probability: float
    source: str
    destination: str
    meta: Dict[str, Any] = {}

class ActionIn(BaseModel):
    incident_id: str
    source: Optional[str] = ""
    destination: Optional[str] = ""
    note: Optional[str] = None

@app.get("/health")
def health():
    return {"ok": True, "dry_run": act.DRY_RUN}

@app.get("/incidents/recent")
def recent(limit: int = 50):
    return list_incidents(limit)

@app.get("/incidents/{incident_id}/actions")
def get_actions(incident_id: str):
    return list_actions(incident_id)

@app.post("/incidents")
def ingest(inc: IncidentIn):
    inc_id = inc.id or str(uuid.uuid4())[:8]
    payload = inc.dict(); payload["id"] = inc_id
    add_incident(payload)

    rules = PLAYBOOKS.get("rules", {}); defaults = PLAYBOOKS.get("defaults", {})
    actions = rules.get(inc.label, {}).get(inc.severity, defaults.get(inc.severity, []))

    results = []
    for a in actions:
        if a == "block_ip":             res = act.block_ip(inc.source)
        elif a == "quarantine_host":    res = act.quarantine_host(inc.source)
        elif a == "notify":
            msg = f"[{inc.severity}] {inc.label} from {inc.source} → {inc.destination}, p={inc.probability:.2f}"
            res = act.notify(msg)
        elif a == "escalate":           res = act.escalate(inc_id)
        else:                           res = {"action": a, "skipped": True}
        results.append(res); add_action(inc_id, a, res)

    if actions: update_status(inc_id, "Auto-Handled")
    return {"incident_id": inc_id, "auto_actions": actions, "results": results}

@app.post("/actions/block_ip")
def manual_block(inp: ActionIn):
    res = act.block_ip(inp.source); add_action(inp.incident_id, "block_ip", res); update_status(inp.incident_id, "Blocked"); return res

@app.post("/actions/quarantine")
def manual_quarantine(inp: ActionIn):
    res = act.quarantine_host(inp.source); add_action(inp.incident_id, "quarantine_host", res); update_status(inp.incident_id, "Quarantined"); return res

@app.post("/actions/allow_false_positive")
def manual_allow(inp: ActionIn):
    res = {"action":"allow_false_positive","note": inp.note or ""}; add_action(inp.incident_id, "allow_false_positive", res); update_status(inp.incident_id, "Allowed (false alarm)"); return res

@app.post("/actions/escalate")
def manual_escalate(inp: ActionIn):
    res = act.escalate(inp.incident_id); add_action(inp.incident_id, "escalate", res); update_status(inp.incident_id, "Escalated"); return res
