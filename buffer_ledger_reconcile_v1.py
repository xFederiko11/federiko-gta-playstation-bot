"""Reconcile the OWN editorial ledger with independently retrieved Buffer sent receipts.

This does not publish, edit Buffer posts, infer replies/thread completion or
modify unrelated ledgers. Scheduled -> sent only when exact Buffer ID, owned
article URL, verified X status URL and authenticated Buffer sent receipt agree.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import argparse,json,re
from urllib.parse import urlsplit

DEFAULT_LEDGER=Path(".state/editorial-autopilot-v137.json")
DEFAULT_RECEIPTS=Path("data/x-permalinks-v1.json")
SCHEMA="verified-buffer-x-permalinks-v1"
ORIGIN="Buffer sent Post.externalLink on verified @xFederiko11 channel"
STATUS=re.compile(r"^https://x.com/xFederiko11/status/[0-9]{8,25}$")
ARTICLE=re.compile(r"^https://xfederiko11\.github\.io/gta-6/(?:[a-z0-9-]+/)*$")

def canonical_receipt(item):
    if not isinstance(item,dict) or item.get("verified_by")!=ORIGIN:return None
    bid,url,link=item.get("buffer_id"),item.get("article_url"),item.get("x_url")
    if not isinstance(bid,str) or not re.fullmatch(r"[a-z0-9]{15,40}",bid):return None
    if not isinstance(url,str) or not ARTICLE.fullmatch(url):return None
    if not isinstance(link,str) or not STATUS.fullmatch(link):return None
    try:
        stamp=datetime.fromisoformat(str(item.get("sent_at","")).replace("Z","+00:00"))
        if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>datetime.now(timezone.utc):return None
    except (TypeError,ValueError,OverflowError):return None
    return bid,url,link,stamp.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def reconcile(ledger,feed):
    if not isinstance(ledger,dict) or not isinstance(ledger.get("entries"),dict):
        raise ValueError("Malformed editorial ledger")
    if not isinstance(feed,dict) or feed.get("schema")!=SCHEMA or not isinstance(feed.get("posts"),list):
        raise ValueError("Malformed verified Buffer receipt feed")
    found={}
    for item in feed["posts"]:
        receipt=canonical_receipt(item)
        if not receipt:continue
        bid,url,link,sent=receipt
        if bid in found and found[bid]!=(url,link,sent):
            raise ValueError("Conflicting Buffer post receipt")
        found[bid]=(url,link,sent)
    # Work on a complete copy; failure must never corrupt .state.
    out=json.loads(json.dumps(ledger,ensure_ascii=False))
    count=0
    for entry in out["entries"].values():
        if not isinstance(entry,dict) or entry.get("status")!="scheduled":continue
        # A Buffer id alone cannot prove this was a genuine scheduled editorial thread.
        # Require a real reservation and first message, as present in our ledger.
        if not isinstance(entry.get("reserved_utc"),str) or not isinstance(entry.get("thread"),list) or not entry["thread"]:
            continue
        receipt=found.get(entry.get("buffer_id"))
        if not receipt or entry.get("url")!=receipt[0]:continue
        article,xurl,sent=receipt
        entry["status"]="sent"
        entry["completed_utc"]=sent
        entry["x_permalink"]=xurl
        entry["buffer_receipt_verified"]=True
        entry["thread_reply_verified"]=False
        entry["delivery_source"]="Buffer sent Post.externalLink"
        count+=1
    return out,count

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",type=Path,default=DEFAULT_LEDGER)
    p.add_argument("--receipts",type=Path,default=DEFAULT_RECEIPTS)
    args=p.parse_args()
    if not args.ledger.exists() or not args.receipts.exists():
        raise SystemExit("RECONCILE_SKIPPED: missing ledger or verified receipts")
    ledger=json.loads(args.ledger.read_text(encoding="utf-8"))
    feed=json.loads(args.receipts.read_text(encoding="utf-8"))
    updated,n=reconcile(ledger,feed)
    print("BUFFER_LEDGER_RECONCILED",n,"verified_sent_receipts_only=true",
          "thread_reply_verified=false","no_posts_created=true")
    if n:
        args.ledger.write_text(json.dumps(updated,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                               encoding="utf-8")

if __name__=="__main__":main()
