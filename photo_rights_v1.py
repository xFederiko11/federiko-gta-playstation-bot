"""Independent, fail-closed reuse review for owned editorial covers.

A hash, Rockstar credit, a feed item or an author claim alone is not a license.
Only an explicitly reviewed record for the exact published bytes can authorize
the owned editorial publication path. This file does not establish legal rights;
reviewers must check the actual evidence before adding a record.
"""
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date
import json,re
from social_media_gate_v2 import canonical_page_path,cover_for

FILE=Path(__file__).with_name("photo-rights-review-v1.json")
KINDS={"official_game_photo","approved_gameplay"}
KEYS={"url","sha256","kind","scope","evidence_url","reviewed_on","review_status"}

def load(path=FILE):
    try:
        doc=json.loads(path.read_text(encoding="utf-8"))
        if set(doc)!={"schema","records"} or doc["schema"]!="gta6-photo-rights-review-v1" or not isinstance(doc["records"],list):
            return {}
        found={}
        for r in doc["records"]:
            if not isinstance(r,dict) or set(r)!=KEYS or not all(isinstance(v,str) for v in r.values()):
                return {}
            if not canonical_page_path(r["url"]) or r["kind"] not in KINDS or not re.fullmatch(r"[a-f0-9]{64}",r["sha256"]):
                return {}
            evidence=urlsplit(r["evidence_url"])
            if (evidence.scheme!="https" or not evidence.hostname or evidence.username or evidence.password or evidence.fragment or len(r["evidence_url"])>500
                or r["scope"]!="site_and_social" or r["review_status"]!="documented_reuse_reviewed"):
                return {}
            # A generic policy page, archive index, or project-owned assertion
            # is not accepted as the evidence of a specific reuse grant.
            if evidence.hostname in {"xfederiko11.github.io","github.com","raw.githubusercontent.com"} or "policy-on-posting-copyrighted-rockstar-games-material" in r["evidence_url"] or evidence.path.rstrip("/").lower()=="/vi/media":
                return {}
            date.fromisoformat(r["reviewed_on"])
            key=(r["url"],r["kind"],r["sha256"])
            if key in found:return {}
            found[key]=r
        return found
    except (OSError,ValueError,TypeError,KeyError):
        return {}

def reuse_documented(url,kind,digest):
    return (url,kind,digest) in load()

if __name__=="__main__":
    print("PHOTO_RIGHTS_REVIEW_RECORDS",len(load()),"records; no inferred rights")
