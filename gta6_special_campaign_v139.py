"""Time-limited GTA VI launch: confirmed GTA+ notice and 3 themed Rockstar galleries.

Only documented Rockstar download/share images, one post per run, no retries after
an attempted Buffer mutation. Reposts are NOT emulated with a copied image/link.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import requests

from editorial_seo_v135 import x_weight

STATE = Path(".state/special-campaign-v139.json")
START = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
EXPIRY = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
MIN_GAP = timedelta(minutes=35)
OFFICIAL_MEDIA = "https://www.rockstargames.com/VI/media/screenshots"
LEGAL = "https://www.rockstargames.com/gta-plus/legal"
PLAYSTATION = "https://www.playstation.com/en-us/support/games/gta-vi-offer-terms/"

# Direct, uniquely named images from Rockstar's download/share page.
# Images are not copied to GitHub or taken from third-party fan feeds.
POSTS = [
    {
        "id": "gta-plus-gtavi-20261118",
        "earliest": "2026-11-18T12:00:00+00:00",
        "kind": "article",
        "text": (
            "🚨 GTA VI | GTA+ arriva anche in GTA VI\n\n"
            "✅ Rockstar prevede vantaggi in-game su PS5.\n"
            "🎁 Acquisto digitale entro il 19/11: 1 mese GTA+ incluso.\n"
            "⚠️ Rinnovo mensile automatico; riscatto PS entro 31/03/27.\n\n"
            "Fonti:\n" + LEGAL + "\n" + PLAYSTATION + "\n\n"
            "#GTAVI #GTAPlus"
        ),
        "sources": [LEGAL, PLAYSTATION],
    },
    {
        "id": "rockstar-vice-city-4",
        "earliest": "2026-11-18T15:20:00+00:00",
        "kind": "gallery",
        "text": "📸 GTA VI | Vice City 🌴\n\nScreenshot ufficiali Rockstar Games.\n\n#GTAVI #GTA6",
        "source": OFFICIAL_MEDIA,
        "images": [
            "https://www.rockstargames.com/VI/_next/static/media/Vice_City_01.135x56yoeu.6t.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Vice_City_02.0c5.7qx17u9kl.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Vice_City_03.0nqz~lrqdmlze.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Vice_City_04.06evqutgh7624.jpg?akim=1&imdensity=1&imwidth=3840",
        ],
    },
    {
        "id": "rockstar-lucia-4",
        "earliest": "2026-11-18T17:00:00+00:00",
        "kind": "gallery",
        "text": "📸 GTA VI | Lucia Caminos\n\nQuattro screenshot ufficiali Rockstar Games.\n\n#GTAVI #GTA6",
        "source": OFFICIAL_MEDIA,
        "images": [
            "https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_01.0a7yqvewctkfp.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_02.16n.5umvlu_48.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_03.14xgd2y_ymmeg.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_04.04kb_~4ubn3wn.jpg?akim=1&imdensity=1&imwidth=3840",
        ],
    },
    {
        "id": "rockstar-leonida-keys-4",
        "earliest": "2026-11-18T19:00:00+00:00",
        "kind": "gallery",
        "text": "📸 GTA VI | Leonida Keys 🏝️\n\nQuattro immagini ufficiali Rockstar Games.\n\n#GTAVI #GTA6",
        "source": OFFICIAL_MEDIA,
        "images": [
            "https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_01.0zgz7tveur6y8.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_02.0~ptk-53gl0lq.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_03.0v_3~-9ceyixc.jpg?akim=1&imdensity=1&imwidth=3840",
            "https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_04.0hce1rw1s8pd9.jpg?akim=1&imdensity=1&imwidth=3840",
        ],
    },
]


def check_config() -> None:
    ids, seen_images = set(), set()
    for post in POSTS:
        if post["id"] in ids:
            raise ValueError("Duplicated editorial identifier")
        ids.add(post["id"])
        if x_weight(post["text"]) > 280:
            raise ValueError("X weighted text too long: " + post["id"])
        if not post["text"].startswith(("📸", "🚨")):
            raise ValueError("Unexpected campaign category")
        if post["kind"] == "gallery":
            images = post["images"]
            if len(images) != 4 or len(set(images)) != 4:
                raise ValueError("Expected four unique themed images")
            for url in images:
                u = urlsplit(url)
                if (u.scheme != "https" or u.hostname != "www.rockstargames.com"
                        or not u.path.startswith("/VI/_next/static/media/")
                        or not u.path.endswith(".jpg") or url in seen_images):
                    raise ValueError("Invalid, unrelated, or reused Rockstar image")
                seen_images.add(url)


def probe_image(url: str, session=None) -> bool:
    """Check public image bytes before reserving a permanent no-retry entry."""
    http = session or requests
    try:
        with http.get(url, timeout=(4, 12), stream=True,
                      headers={"Range": "bytes=0-31", "Accept": "image/jpeg",
                               "User-Agent": "Federiko-GTA-VI-gallery/1.0"},
                      allow_redirects=True) as response:
            if response.status_code not in (200, 206):
                return False
            host = urlsplit(response.url).hostname
            if host not in {"www.rockstargames.com", "media.rockstargames.com",
                            "media-rockstargames-com.akamaized.net"}:
                return False
            if response.headers.get("Content-Type", "").split(";")[0].strip().lower() != "image/jpeg":
                return False
            content_len = response.headers.get("Content-Length", "")
            if content_len.isdigit() and int(content_len) > 13_000_000:
                return False
            header = next(response.iter_content(32), b"")
            return header.startswith(b"\xff\xd8\xff")
    except (requests.RequestException, OSError, StopIteration):
        return False


def load() -> dict:
    if not STATE.exists():
        return {"schema": "special-campaign-v139", "entries": {}}
    data = json.loads(STATE.read_text(encoding="utf-8"))
    if data.get("schema") != "special-campaign-v139" or not isinstance(data.get("entries"), dict):
        raise ValueError("Unknown campaign ledger; fail closed")
    return data


def save(data) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")
    temp.replace(STATE)


def select(data: dict, now: datetime):
    check_config()
    if now < START or now >= EXPIRY:
        return None, "outside_window"
    latest = [datetime.fromisoformat(x["reserved_utc"]) for x in data["entries"].values()
              if x.get("reserved_utc")]
    if latest and now - max(latest) < MIN_GAP:
        return None, "minimum_spacing"
    for post in POSTS:
        if post["id"] not in data["entries"] and now >= datetime.fromisoformat(post["earliest"]):
            return post, "eligible"
    return None, "no_eligible_item"


def preview() -> None:
    check_config()
    ledger = load()
    now = datetime.now(timezone.utc)
    next_post, reason = select(ledger, now)
    print("PREVIEW", now.isoformat(), "reason=", reason)
    print("NEXT", next_post["id"] if next_post else "none")
    for p in POSTS:
        print("POST", p["id"], "kind=", p["kind"],
              "status=", ledger["entries"].get(p["id"], {}).get("status", "new"),
              "images=", len(p.get("images", [])),
              "weighted=", x_weight(p["text"]))
        print("COPY", p["text"])
    print("READ ONLY: no Buffer mutations")


def reserve():
    run = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not run:
        raise RuntimeError("Expected GitHub Actions context")
    data = load()
    selected, reason = select(data, datetime.now(timezone.utc))
    if not selected:
        print("NO_POST", reason)
        return
    if selected["kind"] == "gallery":
        for url in selected["images"]:
            if not probe_image(url):
                print("HOLD_MEDIA_UNAVAILABLE", selected["id"], urlsplit(url).path.split("/")[-1])
                return
    data["entries"][selected["id"]] = {
        "status": "reserved",
        "run_id": run,
        "reserved_utc": datetime.now(timezone.utc).isoformat(),
        "digest": hashlib.sha256(selected["text"].encode()).hexdigest(),
        "kind": selected["kind"],
    }
    save(data)
    print("RESERVED", selected["id"], "images=", len(selected.get("images", [])))


def deliver():
    from buffer_publisher import BufferClient, BufferAPIError, BufferPending
    run = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not run:
        raise RuntimeError("Expected GitHub Actions context")
    data = load()
    mine = [p for p in POSTS if
            data["entries"].get(p["id"], {}).get("run_id") == run and
            data["entries"][p["id"]].get("status") == "reserved"]
    if not mine:
        print("DELIVERY_NOT_ATTEMPTED: no campaign reservation")
        return
    if len(mine) != 1:
        raise RuntimeError("More than one reservation for current run")
    post = mine[0]
    entry = data["entries"][post["id"]]
    client = BufferClient(expected_username="xFederiko11")
    client.verify_destination()
    # No automatic retry after this stage, even if Buffer times out.
    entry["status"] = "attempted"
    entry["attempted_utc"] = datetime.now(timezone.utc).isoformat()
    save(data)
    try:
        if post["kind"] == "gallery":
            post_id = client.publish_gallery(post["text"], post["images"])
        else:
            post_id = client.publish(post["text"])
    except BufferPending as e:
        entry["status"] = "accepted_pending"
        entry["buffer_id"] = e.post_id
        print("BUFFER_PENDING", post["id"], e.post_id)
    except BufferAPIError as e:
        entry["status"] = "uncertain" if e.outcome_unknown else "rejected"
        entry["buffer_id"] = e.post_id
        print("BUFFER_ERROR", post["id"], entry["status"], type(e).__name__)
    else:
        entry["status"] = "sent"
        entry["buffer_id"] = post_id
        print("BUFFER_SENT", post["id"], post_id)
    finally:
        entry["completed_utc"] = datetime.now(timezone.utc).isoformat()
        save(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preview", "reserve", "deliver"], required=True)
    mode = parser.parse_args().mode
    {"preview": preview, "reserve": reserve, "deliver": deliver}[mode]()


if __name__ == "__main__":
    main()
