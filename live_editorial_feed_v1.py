"""Consume the reader-facing site feed; never execute remote code or mutate X.

Only the fixed HTTPS endpoint is queried. A feed row is a candidate, not
authorization to publish. The public article must independently agree with the
summary and photo hash, before reservation and again before delivery.
"""
from datetime import date
import json,re,hashlib
import requests
from functools import lru_cache
from social_media_gate_v2 import cover_for
from editorial_seo_v135 import x_weight

BASE="https://xfederiko11.github.io/gta-6/"
URL=BASE+"articoli/feed.json"
SCHEMA="gta6-editorial-feed-v1"
FIELDS={"url","title","summary","published","image","sha256","kind"}
KINDS={"official_game_photo","approved_gameplay"}

def validate(doc):
    if not isinstance(doc,dict) or set(doc)!={"schema","items"} or doc["schema"]!=SCHEMA:
        raise ValueError("Unexpected editorial feed")
    rows=doc["items"]
    if not isinstance(rows,list) or len(rows)>100:raise ValueError("Invalid reader inventory")
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!=FIELDS or not all(isinstance(v,str) for v in row.values()):
            raise ValueError("Unexpected public feed fields")
        if not re.fullmatch(re.escape(BASE)+r"articoli/[a-z0-9-]+/",row["url"]) or row["url"] in seen:
            raise ValueError("Invalid or duplicate URL")
        seen.add(row["url"])
        if (not 8<=len(row["title"])<=140 or not 40<=len(row["summary"])<=150
                or any(x in row["title"]+row["summary"] for x in ("<",">","@","http:","https:"))
                or any(ord(x)<32 for x in row["title"]+row["summary"])):
            raise ValueError("Invalid reader summary")
        date.fromisoformat(row["published"])
        if row["image"]!=cover_for(row["url"]) or row["kind"] not in KINDS or not re.fullmatch(r"[a-f0-9]{64}",row["sha256"]):
            raise ValueError("Invalid photo metadata")
    return rows

def fetch(session=None):
    with (session or requests).get(URL,stream=True,allow_redirects=False,timeout=(3,7),
                     headers={"User-Agent":"GTA6Italia-ReaderFeed/1.0","Cache-Control":"no-cache","Accept":"application/json"}) as r:
        if r.status_code!=200 or r.url!=URL or r.headers.get("Content-Type","").split(";")[0].strip() not in ("application/json","text/plain","application/octet-stream"):
            raise ValueError("Reader feed unavailable")
        data=bytearray()
        for part in r.iter_content(8192):
            data.extend(part)
            if len(data)>160000:raise ValueError("Oversized public feed")
        return validate(json.loads(data))

@lru_cache(maxsize=1)
def candidates():
    try:
        rows=fetch()
    except (requests.RequestException,OSError,ValueError,TypeError,KeyError) as exc:
        print("READER_FEED_HOLD",type(exc).__name__)
        return ()
    result=[]
    for row in rows:
        copy="📖 GTA VI | "+row["summary"]+"\n\n"+row["url"]
        if x_weight(copy+"\n\nFoto promozionale: Rockstar Games.")>235:
            continue
        result.append({"id":"public-feed:"+hashlib.sha256(row["url"].encode()).hexdigest()[:24],
                       "path":"/"+row["url"].removeprefix(BASE),"title":row["title"],
                       "text":"📖 GTA VI | "+row["summary"],"feed_summary":row["summary"],
                       "feed_kind":row["kind"],"feed_digest":row["sha256"]})
    print("READER_FEED_AVAILABLE",len(result))
    return tuple(result)

def matching(entry,reader=None):
    from game_photo_policy_v1 import owned_photo_contract
    expected=(entry.get("feed_kind"),entry.get("feed_digest"),entry.get("feed_summary"))
    if not all(isinstance(v,str) and v for v in expected):return False
    return (reader or owned_photo_contract)(entry.get("url"))==expected

def main():
    # Read-only smoke test, no Buffer credentials or publication.
    from game_photo_policy_v1 import probe_cover_digest
    rows=candidates()
    if not rows:raise SystemExit("READER_FEED_UNAVAILABLE_OR_EMPTY")
    checked=0
    for row in rows:
        item=dict(row,url=BASE+row["path"].lstrip("/"))
        if not matching(item) or not probe_cover_digest(cover_for(item["url"]),item["feed_digest"]):
            raise SystemExit("READER_FEED_CONTRACT_MISMATCH")
        checked+=1
    print("READER_FEED_LIVE_OK",checked,"articles; no posts created")

if __name__=="__main__":main()
