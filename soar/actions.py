import os, platform, subprocess, datetime
DRY_RUN = os.getenv("SOAR_DRY_RUN", "true").lower() == "true"

def _run(cmd):
    if DRY_RUN:
        return {"ok": True, "dry_run": True, "cmd": cmd}
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=8)
        return {"ok": True, "dry_run": False, "output": out}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "dry_run": False, "error": e.output}

def block_ip(ip: str):
    osname = platform.system().lower()
    if "windows" in osname:
        cmd_in  = f'netsh advfirewall firewall add rule name="SOAR Block IN {ip}" dir=in action=block remoteip={ip}'
        cmd_out = f'netsh advfirewall firewall add rule name="SOAR Block OUT {ip}" dir=out action=block remoteip={ip}'
        r1 = _run(cmd_in); r2 = _run(cmd_out)
        return {"action":"block_ip","ip":ip,"results":[r1,r2]}
    else:
        cmd1 = f"sudo iptables -I INPUT -s {ip} -j DROP"
        cmd2 = f"sudo iptables -I OUTPUT -d {ip} -j DROP"
        r1 = _run(cmd1); r2 = _run(cmd2)
        return {"action":"block_ip","ip":ip,"results":[r1,r2]}

def quarantine_host(ip: str):  return block_ip(ip)
def notify(message: str):      return {"action":"notify","message":message,"when":datetime.datetime.utcnow().isoformat()+"Z"}
def escalate(incident_id: str):return {"action":"escalate","incident_id":incident_id,"when":datetime.datetime.utcnow().isoformat()+"Z"}
