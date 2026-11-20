"""One-time real Buffer scheduling of the missing 20 Nov 2026 launch threads.

Never call createPost for a slot without a persisted 'attempted' record.
Buffer's customScheduled + dueAt is required; planned JSON is not a queue.
No repeated mutations for unknown outcomes, no fabricated coordinates, no
unsafe links, no after-hours scheduling.
"""
from __future__ import annotations
import argparse
from datetime import datetime, date, time, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from buffer_publisher import (BufferClient, CREATE_MUTATION, BufferAPIError,
                              BufferConfigurationError, BufferMediaError)
from buffer_queue_health_v1 import snapshot
from editorial_seo_v135 import x_weight
from editorial_director_v142 import read_reservations
from launch_cadence_v1 import local, TARGET_MAX, MAX_BUFFER_X_MESSAGES_24H

CAMPAIGN=Path("catchup-20261120.json")
LEDGER=Path(".state/editorial-autopilot-v137.json")
ZONE=ZoneInfo("Europe/Rome")
DATE=date(2026,11,20)
GAP=timedelta(minutes=50)
CHECK_AHEAD=timedelta(minutes=20)
MAX_SLOTS=10


def planned_threads(data:dict)->list[dict]:
    if data.get("schema")!="gta6-buffer-catchup-v1" or data.get("date")!=DATE.isoformat():
        raise ValueError("Unexpected catchup campaign")
    result=[]
    seen=set()
    for slot in data.get("slots",[]):
        token=str(slot["id"])
        if token in seen:raise ValueError("Duplicate campaign ID")
        seen.add(token)
        target=str(slot["link"])
        url=urlsplit(target)
        if (url.scheme!="https" or url.hostname!="xfederiko11.github.io"
            or not url.path.startswith("/gta-6/") or url.username or url.password
            or url.query or url.fragment):
            raise ValueError("Noncanonical target")
        main=str(slot["main"]).strip()
        second="📖 Guida italiana passo per passo, con fonti e spoiler a scelta:\n"+target+"\n\n#GTAVI"
        if not main or max(x_weight(main),x_weight(second))>280:
            raise ValueError("X text over limit")
        hour,minute=map(int,slot["time"].split(":"))
        if not time(8,0)<=time(hour,minute)<time(21,0):
            raise ValueError("Slot outside editorial hours")
        result.append({**slot,"main":main,"thread":[main,second],
                       "original_due":datetime.combine(DATE,time(hour,minute),ZONE).astimezone(timezone.utc),
                       "key":hashlib.sha256(("gta6-catchup-20261120:"+token).encode()).hexdigest()[:24]})
    if len(result)!=MAX_SLOTS: raise ValueError("Expected exactly 10 unique catchup threads")
    return result


def same_link(entry:dict,target:str)->bool:
    return str(entry.get("url","")).rstrip("/") == target.rstrip("/")


def make_plan(data:dict, state:dict, now:datetime, other:list[dict])->list[dict]:
    now=now.astimezone(timezone.utc)
    if local(now).date()!=DATE or local(now).hour>=21:
        return []
    entries=state["entries"]
    existing=[x for x in other if x["at"]<=now and x.get("status")!="rejected"]
    scheduled=[x for x in other if x["at"]>now and x.get("status")!="rejected"]
    all_events=sorted(existing+scheduled,key=lambda x:x["at"])
    total_local=sum(local(x["at"]).date()==DATE for x in all_events)
    latest=max((x["at"] for x in all_events),default=now-GAP)
    candidate=[]
    for row in planned_threads(data):
        if row["key"] in entries or any(same_link(e,row["link"]) for e in entries.values()):
            continue
        if total_local+len(candidate)>=TARGET_MAX:
            break
        requested=max(row["original_due"],now+CHECK_AHEAD,latest+GAP)
        # Round to the next five minutes to avoid odd times after a late run.
        minutes=requested.minute
        if requested.second or requested.microsecond or minutes%5:
            requested=requested.replace(second=0,microsecond=0)+timedelta(minutes=(5-minutes%5))
        if local(requested).date()!=DATE or not time(8,0)<=local(requested).time().replace(tzinfo=None)<time(21,0):
            break
        if sum(x.get("units",1) for x in all_events
               if requested-timedelta(hours=24)<=x["at"]<=requested) + 2*(len(candidate)+1)>MAX_BUFFER_X_MESSAGES_24H:
            break
        candidate.append({**row,"due":requested})
        latest=requested
    return candidate


def persist(state, data, description):
    """Commit and push a batch; reserve all slots before ANY mutation."""
    LEDGER.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    CAMPAIGN.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    subprocess.run(["git","add","-f",str(LEDGER),str(CAMPAIGN)],check=True)
    diff=subprocess.run(["git","diff","--cached","--quiet"],check=False)
    if diff.returncode not in (0,1):raise RuntimeError("Cannot check staged journal")
    if diff.returncode:
        subprocess.run(["git","-c","user.name=github-actions[bot]",
                        "-c","user.email=41898282+github-actions[bot]@users.noreply.github.com",
                        "commit","-m",description],check=True)
        subprocess.run(["git","push","origin","HEAD:main"],check=True)


def schedule_one(client,row):
    """One atomic two-message customScheduled Buffer mutation."""
    items=[{"text":t,"assets":[]} for t in row["thread"]]
    input_value={"text":items[0]["text"],"channelId":client.channel_id,
                 "schedulingType":"automatic","mode":"customScheduled",
                 "dueAt":row["due"].isoformat().replace("+00:00","Z"),
                 "assets":[],"metadata":{"twitter":{"thread":items}}}
    result=client._graphql(CREATE_MUTATION,{"input":input_value},mutation=True).get("createPost")
    if not isinstance(result,dict) or not result.get("post"):
        if isinstance(result,dict) and result.get("message"):
            raise BufferAPIError("Buffer rejected scheduled thread",outcome_unknown=False)
        raise BufferAPIError("Buffer schedule result incomplete",outcome_unknown=True)
    delivery=client._delivery(result["post"])
    if delivery.status!="scheduled":
        raise BufferAPIError("Unexpected Buffer scheduled status",post_id=delivery.post_id,
                             outcome_unknown=True)
    return delivery.post_id


def run(*,dry_run=False,now=None):
    now=now or datetime.now(timezone.utc)
    data=json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    state=json.loads(LEDGER.read_text(encoding="utf-8"))
    rows=planned_threads(data)
    other=read_reservations()
    plan=make_plan(data,state,now,other)
    print("CATCHUP_PLAN",len(plan),"of",len(rows),"existing_slots",len(other),
          "at",now.isoformat(),flush=True)
    for row in plan:
        print("CATCHUP_TARGET",row["id"],local(row["due"]).strftime("%H:%M"),flush=True)
    if dry_run:return plan
    if not os.getenv("GITHUB_RUN_ID"):
        raise RuntimeError("Only authorized Actions runs may schedule Buffer posts")
    if not plan:
        print("CATCHUP_NO_ELIGIBLE_FUTURE_SLOTS")
        return []
    client=BufferClient(expected_username="xFederiko11")
    dest=client.verify_destination()
    if dest.get("isQueuePaused"):raise RuntimeError("Buffer channel is paused")
    current=snapshot(client=client)
    if current["status"]!="ok" or current["is_queue_paused"] or current["error"]:
        raise RuntimeError("Buffer queue unavailable/paused/errored; manual reconciliation needed")
    # Previously confirmed Buffer scheduling must be retained, not treated as
    # an unknown foreign queue. Unrecognized times fail closed.
    prior_dates=set()
    for original in data["slots"]:
        if original.get("status")=="scheduled" and original.get("buffer_id"):
            due=original.get("scheduled_for_rome")
            if due:
                prior_dates.add(datetime.fromisoformat(due).astimezone(timezone.utc))
    for scheduled in current["scheduled"]:
        stamp=scheduled.get("dueAt")
        try:
            at=datetime.fromisoformat(stamp.replace("Z","+00:00")).astimezone(timezone.utc)
        except (ValueError,AttributeError):
            raise RuntimeError("Scheduled Buffer queue contains an unknown date")
        if at not in prior_dates:
            raise RuntimeError("Foreign Buffer queue slot detected: reconcile before writes")
    print("BUFFER_SCHEDULED_RECONCILED",len(current["scheduled"]),flush=True)
    from portal_links_v148 import page_live
    for row in plan:
        if not page_live(row["link"]):
            raise RuntimeError("Source guide not publicly verified: "+row["id"])

    # One durable Git commit reserves ALL seven remaining mutations ahead of
    # time; one final commit records results. This avoids GitHub burst limits.
    for row in plan:
        if row["key"] in state["entries"]:continue
        state["entries"][row["key"]]={
            "status":"attempted","run_id":os.environ["GITHUB_RUN_ID"],
            "reserved_utc":row["due"].isoformat(),"due_at":row["due"].isoformat(),
            "source":"Guide GTA VI Italia","title":row["title"],
            "url":row["link"],"thread":row["thread"],"tip_id":"catchup-"+row["id"],
            "attempted_utc":datetime.now(timezone.utc).isoformat()}
        slot=next(x for x in data["slots"] if x["id"]==row["id"])
        slot.update(status="attempted",scheduled_for_rome=local(row["due"]).isoformat())
    data["state"]="batch_attempted_before_buffer"
    persist(state,data,"Reserve remaining GTA VI Buffer catchup slots before mutations")

    ids=[]
    try:
        for row in plan:
            entry=state["entries"][row["key"]]
            slot=next(x for x in data["slots"] if x["id"]==row["id"])
            try:
                buffer_id=schedule_one(client,row)
            except BufferAPIError as exc:
                entry["status"]="uncertain" if exc.outcome_unknown else "rejected"
                entry["buffer_id"]=exc.post_id
                slot["status"]=entry["status"]
                print("CATCHUP_STOP",row["id"],entry["status"],type(exc).__name__,flush=True)
                break
            entry.update(status="scheduled",buffer_id=buffer_id)
            slot.update(status="scheduled",buffer_id=buffer_id)
            ids.append(buffer_id)
            print("BUFFER_SCHEDULED",row["id"],local(row["due"]).strftime("%H:%M"),
                  "buffer_id",buffer_id,flush=True)
    finally:
        statuses=[x["status"] for x in data["slots"]]
        data["state"]="all_10_buffer_scheduled" if all(x=="scheduled" for x in statuses) else "partially_scheduled_reconciliation_needed"
        persist(state,data,"Confirm Buffer scheduled GTA VI catchup batch receipts")
    print("CATCHUP_SCHEDULED_TOTAL",len(ids),flush=True)
    return ids


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("preview","schedule"),default="preview")
    args=parser.parse_args()
    run(dry_run=args.mode=="preview")
