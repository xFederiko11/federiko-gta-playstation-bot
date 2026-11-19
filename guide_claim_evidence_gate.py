"""Strict evidence dossier gate for GTA VI guide corrections.

Editorial dossiers must name a specific claim and independently reviewed source
evidence. Feed titles never count as evidence. This tool only emits review
decisions; it cannot publish, alter articles or post to Buffer.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "gta6-claim-dossiers-v1"
ALLOWED = {
    "PowerPyx": ("powerpyx.com", "www.powerpyx.com"),
    "GTA Series Videos": ("youtube.com", "www.youtube.com"),
    "GTABase": ("gtabase.com", "www.gtabase.com"),
    "Rockstar Games": ("rockstargames.com", "www.rockstargames.com"),
}
VERDICTS = {"confirmed", "contradicted", "uncertain"}
TARGETS = {"guide-e-tutorial/", "trofei/", "trucchi/", "hdr-oled/"}


def url_host(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError("Unsafe evidence URL")
    return p.hostname.lower()


def review(dossier):
    if not isinstance(dossier, dict) or dossier.get("schema") != SCHEMA:
        raise ValueError("Invalid dossier schema")
    claims = dossier.get("claims")
    if not isinstance(claims, list) or len(claims) > 30:
        raise ValueError("Invalid claim list")
    decisions = []
    ids = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Invalid claim")
        cid = claim.get("id")
        if not isinstance(cid, str) or not 3 <= len(cid) <= 90 or cid in ids:
            raise ValueError("Invalid or duplicate claim ID")
        ids.add(cid)
        target = claim.get("target_page")
        if not isinstance(target, str) or not (
            target in TARGETS or target.startswith("guide-e-tutorial/") and
            target.endswith("/") and ".." not in target and
            all(x.isalnum() or x in "-/" for x in target)):
            raise ValueError("Invalid target page")
        statement = claim.get("statement")
        if not isinstance(statement, str) or not 20 <= len(statement) <= 600:
            raise ValueError("Missing specific claim")
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > 12:
            raise ValueError("Invalid evidence")
        accepted, rejected = [], []
        for item in evidence:
            if not isinstance(item, dict):
                rejected.append("invalid_entry")
                continue
            source = item.get("source")
            if source not in ALLOWED:
                rejected.append("unknown_source")
                continue
            try:
                host = url_host(item.get("url", ""))
            except (ValueError, TypeError):
                rejected.append("invalid_url")
                continue
            if host not in ALLOWED[source]:
                rejected.append("host_mismatch")
                continue
            if item.get("assessment") not in VERDICTS:
                rejected.append("missing_assessment")
                continue
            # Evidence must be read by a reviewer; metadata-only leads do not qualify.
            if item.get("reviewed_original") is not True or not isinstance(item.get("observed"), str) or len(item["observed"].strip()) < 35:
                rejected.append("not_reviewed")
                continue
            if not isinstance(item.get("reviewed_utc"), str):
                rejected.append("missing_review_time")
                continue
            try:
                stamp = datetime.fromisoformat(item["reviewed_utc"].replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("No timezone")
            except ValueError:
                rejected.append("invalid_review_time")
                continue
            accepted.append(item)
        confirmed = {x["source"] for x in accepted if x["assessment"] == "confirmed"}
        contradicted = {x["source"] for x in accepted if x["assessment"] == "contradicted"}
        platform = claim.get("platform") == "PS5"
        patch = isinstance(claim.get("patch"), str) and len(claim["patch"].strip()) >= 2
        # Explicit per-platform trophy evidence is required even for ordinary guides.
        trophy = claim.get("trophy_evidence")
        trophy_ok = isinstance(trophy, dict) and trophy.get("platform") == "PS5" and (
            trophy.get("status") == "safe" and trophy.get("reviewed_original") is True
            and isinstance(trophy.get("observed"), str) and len(trophy["observed"].strip()) >= 35
            and trophy.get("source") in ALLOWED
            and isinstance(trophy.get("url"), str)
            and url_host(trophy["url"]) in ALLOWED[trophy["source"]]
        ) if isinstance(trophy, dict) else False
        # Safety must be corroborated by an explicit source, not an editorial checkbox.
        if trophy_ok:
            trophy_ok = any(x["url"] == trophy["url"] and x["source"] == trophy["source"]
                            for x in accepted)
        independent = len(confirmed) >= 2
        ready = independent and not contradicted and platform and patch and trophy_ok
        decisions.append({
            "id": cid, "target_page": target, "claim": statement,
            "independent_confirmations": len(confirmed),
            "contradictions": len(contradicted),
            "platform_checked": platform, "patch_documented": patch,
            "trophy_safe_documented": trophy_ok,
            "editorially_reviewable": ready,
            "auto_publish": False,
            "rejected_evidence": rejected,
            "action": "human_review_for_possible_manual_update" if ready else "collect_more_evidence",
        })
    return {"schema": "gta6-claim-review-v1", "decisions": decisions,
            "publication": "review_only__never_auto_publish"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = review(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print("CLAIMS", len(result["decisions"]), "READY_FOR_MANUAL_REVIEW",
          sum(x["editorially_reviewable"] for x in result["decisions"]), "AUTO_PUBLISH=false")


if __name__ == "__main__":
    main()
