"""Read-only fail-closed audit of all current automated X publication workflows.

Checks *project invariants*, not account reputation. Cannot guarantee no ban;
does not call any X/Buffer API and never edits user settings.
"""
from __future__ import annotations
from pathlib import Path
import argparse

POSTING = (
    ".github/workflows/gta-monitor.yml",
    ".github/workflows/gta6-editorial-autopilot-v137.yml",
    ".github/workflows/gta6-special-campaign-v139.yml",
    ".github/workflows/launch-watch-v134.yml",
)
ORGANIC = ".github/workflows/gta6-organic-growth-v1.yml"
SAFETY_SWITCH = "EDITORIAL_DIRECTOR_V142_ENABLED: 'true'"
COMMON_CONCURRENCY = "gta-v142-publication-global"


def audit(root=Path(".")) -> dict:
    root=Path(root)
    errors=[]
    found=[]
    for name in POSTING:
        text=(root/name).read_text(encoding="utf-8")
        found.append(name)
        if SAFETY_SWITCH not in text:
            errors.append(name+": no guaranteed director safety switch")
        if COMMON_CONCURRENCY not in text:
            errors.append(name+": cannot guarantee serialized X publication")
        if "cancel-in-progress: false" not in text:
            errors.append(name+": publisher jobs could be cancelled during Buffer mutation")
    growth=(root/ORGANIC).read_text(encoding="utf-8")
    for token in ("BUFFER_API_KEY","BUFFER_CHANNEL_ID","secrets.BUFFER","publish_thread","createPost"):
        if token in growth:
            errors.append("Manual conversation workflow gained a publishing capability: "+token)
    source=(root/"x_community_review_v1.py").read_text(encoding="utf-8")
    for token in ("BufferClient", "requests.get(", "requests.post(", "urlopen(",
                  "x_client.post(", "tweepy.", "selenium.", "playwright."):
        if token in source:
            errors.append("Conversation queue must not access or mutate external X: "+token)
    if "data/x-conversation-candidates-v1.json" not in growth:
        errors.append("Growth workflow does not revalidate human review candidates")
    director=(root/"editorial_director_v142.py").read_text(encoding="utf-8")
    if "MAX_AUTOMATED_DELIVERIES_24H=8" not in director:
        errors.append("Global publication limit was changed without safety review")
    if "MIN_GAP=timedelta(minutes=90)" not in director:
        errors.append("Global minimum posting gap was changed without safety review")
    if "STEADY_MAX_AUTOMATED_DELIVERIES_24H=6" not in director or "STEADY_MIN_GAP=timedelta(minutes=120)" not in director:
        errors.append("Post-launch conservative pace was changed without safety review")
    if "BOOST_UNTIL=datetime(2026,11,30" not in director:
        errors.append("Temporary boost expiration was removed without safety review")
    if "RECOVERY_START=datetime(2026,11,19,20,45" not in director or "RECOVERY_END=RECOVERY_START+timedelta(hours=24)" not in director or "RECOVERY_MAX_AUTOMATED_DELIVERIES=5" not in director:
        errors.append("One-time, time-bounded launch recovery needs safety review")
    result={
        "publisher_workflows_audited":found,
        "organic_workflow":ORGANIC,
        "posting_workflows_have_guards":not errors,
        "conversation_workflow_manual_only":not errors,
        "errors":errors,
        "scope":"static_GitHub_workflow_audit_only_not_X_account_assessment",
    }
    if errors:
        raise RuntimeError("X_SAFETY_AUDIT_FAILED: "+"; ".join(errors))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    args=p.parse_args()
    x=audit(args.root)
    print("X_SAFETY_AUDIT_OK posting_workflows="+str(len(x["publisher_workflows_audited"]))+
          " manual_only=true no_X_API=true")


if __name__=="__main__":
    main()
