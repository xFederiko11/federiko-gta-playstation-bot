"""Read-only forensic lookup for a failed Buffer X thread; no retries/writes."""
import json
from pathlib import Path
import re

from buffer_publisher import BufferClient

QUERY = """query RejectedPostDetails($id: PostId!) {
  post(input: {id: $id}) {
    id
    status
    error { message supportUrl }
  }
}"""

def category(message:str)->str:
    terms=[
        ("media",r"image|photo|media|asset|upload|dimension|download|attachment|size|file"),
        ("thread",r"thread|reply|replies|conversation"),
        ("duplicate",r"duplicate|similar|recently|already\s+(posted|shared)"),
        ("limit",r"limit|quota|too\s+many|rate|over.*characters|length"),
        ("authorization",r"auth|token|permission|disconnect|account"),
        ("url",r"link|url|domain|unsafe"),
    ]
    for name,pattern in terms:
        if re.search(pattern,message,re.I):return name
    return "other" if message else "not_reported"

def summary(post:dict)->dict:
    error=post.get("error") or {}
    raw=str(error.get("message") or "")
    safe=re.sub(r"https?://\S+","[URL]",raw)
    safe=re.sub(r"\b[A-Za-z0-9_-]{32,}\b","[ID]",safe)
    safe=re.sub(r"[\r\n\t]+"," ",safe)[:160]
    return {"post_id":str(post.get("id") or "")[:40],
            "status":str(post.get("status") or "unknown"),
            "category":category(raw),"error_short":safe or "(nessun dettaglio disponibile)"}

def inspect():
    ledger=Path(".state/editorial-autopilot-v137.json")
    if not ledger.exists():
        print("BUFFER_READONLY_DIAGNOSTIC ledger_missing");return
    entries=json.loads(ledger.read_text("utf-8")).get("entries",{})
    failed=[x for x in entries.values() if x.get("source")=="PowerPyx Tips"
            and x.get("status")=="rejected" and x.get("buffer_id")]
    if not failed:
        print("BUFFER_READONLY_DIAGNOSTIC no_failed_tips");return
    last=max(failed,key=lambda x:x.get("reserved_utc") or "")
    client=BufferClient(expected_username="xFederiko11")
    client.verify_destination()
    data=client._graphql(QUERY,{"id":str(last["buffer_id"])})
    print("BUFFER_READONLY_DIAGNOSTIC",json.dumps(summary(data.get("post") or {}),
         ensure_ascii=False))
    print("BUFFER_DIAGNOSTIC_NO_MUTATION")

if __name__=="__main__":
    inspect()
