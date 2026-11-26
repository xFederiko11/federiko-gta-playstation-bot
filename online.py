"""Runner online gratuito: fonti primarie -> schede locali -> Buffer Free."""

import argparse
import csv
import hashlib
import json
import logging
import os
from pathlib import Path
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import sqlite3
import subprocess
import time

import sources
import history
from free_editor import article_events, catalog_event
from presentation import group_platform_events, render_card, format_post, demo_events
from editorial_language_it import contains_english_prose, italian_title, TranslationUnavailable
from buffer_publisher import BufferClient, BufferAPIError, BufferPending, BufferDeliveryFailed
from editorial_policy import approved_source, event_allowed, history_record_allowed
from news_center import thread_for_event, news_center_preview
from official_media import official_image_for_event, official_media_for_event, OfficialMediaUnavailable

LOG = logging.getLogger("gta.online")
ROOT = Path(__file__).resolve().parent


class FreeQuotaExceeded(RuntimeError):
    pass


def essentials_window_active():
    """Explicit temporary plan, with an automatic conservative safety sunset.

    Never presume the Buffer subscription renewed. After the indicated day the
    bot reverts to Free local guards even if the repository variable is stale.
    """
    if os.getenv('BUFFER_PLAN', 'free').casefold() != 'essentials':
        return False
    try:
        return date.today() <= date.fromisoformat(os.getenv('BUFFER_PAID_THROUGH', '2026-12-15'))
    except ValueError:
        return False


class FreeRequestBudget:
    """Conservative request quotas for the active Buffer plan."""
    def __init__(self, db):
        self.db = db
        db.execute("CREATE TABLE IF NOT EXISTS buffer_requests (at REAL NOT NULL)")

    def __call__(self):
        stamp = time.time()
        quotas = ((900, 100), (86400, 170), (30 * 86400, 2600)) if essentials_window_active() \
                 else ((900, 100), (86400, 40), (30 * 86400, 900))
        for seconds, maximum in quotas:
            count = self.db.execute("SELECT count(*) FROM buffer_requests WHERE at>?", (stamp - seconds,)).fetchone()[0]
            if count >= maximum:
                raise FreeQuotaExceeded("Quota locale gratuita raggiunta: gli invii restano in attesa")
        with self.db:
            self.db.execute("INSERT INTO buffer_requests VALUES (?)", (stamp,))
            self.db.execute("DELETE FROM buffer_requests WHERE at<?", (stamp - 31 * 86400,))


def open_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
      CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS posts (
        key TEXT PRIMARY KEY, source_id TEXT NOT NULL, source_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued', text TEXT, evidence_json TEXT,
        published_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS publish_jobs (
        key TEXT PRIMARY KEY, event_json TEXT NOT NULL, status TEXT NOT NULL,
        text TEXT NOT NULL, buffer_id TEXT, external_url TEXT, last_error TEXT,
        created_at REAL NOT NULL, next_attempt REAL NOT NULL DEFAULT 0,
        attempted_at REAL NOT NULL DEFAULT 0
      );
    """)
    if "attempted_at" not in {row[1] for row in db.execute("PRAGMA table_info(publish_jobs)")}:
        db.execute("ALTER TABLE publish_jobs ADD COLUMN attempted_at REAL NOT NULL DEFAULT 0")
    sources.init(db)
    history.init_history(db)
    return db


def set_meta(db, key, value):
    db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, str(value)))


def get_meta(db, key):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def prioritize_ps5_and_launch_sources(config, today=None):
    """PS5/PS5 Pro news only; faster primary-source polling during launch."""
    today = today or datetime.now(ZoneInfo('Europe/Berlin')).date()
    firmware = config.get('system_software', {})
    if firmware.get('enabled'):
        # PS5 system software also covers PS5 Pro. Exclude separate PS4 reports.
        firmware['platforms'] = ['PS5']
    if date(2026, 11, 18) <= today <= date(2026, 11, 22):
        if firmware.get('enabled'):
            firmware['interval'] = 300
        for source in config.get('sources', []):
            if source.get('id') == 'newswire':
                source['interval'] = 300
            elif source.get('id') == 'youtube':
                source['interval'] = 300
            elif source.get('id') == 'support-gta':
                source['interval'] = 900
    config['ps5_focus'] = True
    return config


def source_is_ps5_relevant(event):
    """Ignore PS4-only items; retain PS5/Pro and truly cross-platform GTA news."""
    platforms = event.get('platforms') or []
    if isinstance(platforms, str):
        platforms = [platforms]
    if not platforms:
        return True
    labels = [str(x).strip().casefold().replace(' ', '') for x in platforms]
    return any(x.startswith('ps5') or x.startswith('playstation5') or
               x in {'common', 'all', 'comune', 'tutte'} for x in labels)


def refresh_launch_poll_deadlines(db, config, today=None):
    """Honor faster new intervals without overriding provider failure backoff."""
    today = today or datetime.now(ZoneInfo('Europe/Berlin')).date()
    if not (date(2026, 11, 18) <= today <= date(2026, 11, 22)):
        return
    candidates = [(s['id'], int(s.get('interval', 900))) for s in config.get('sources', [])
                  if s.get('enabled', True)]
    if config.get('system_software', {}).get('enabled'):
        candidates.append(('system:PS5', int(config['system_software'].get('interval', 300))))
    with db:
        for identifier, delay in candidates:
            db.execute("""UPDATE monitors SET next_due=last_success+?
                         WHERE id=? AND last_error IS NULL AND last_success IS NOT NULL
                         AND next_due>last_success+?""", (delay, identifier, delay))


def source_policy(config):
    # Nessuna via indiretta verso API a pagamento, nemmeno con vecchie chiavi presenti.
    if any(s.get("enabled", True) and s["type"] == "x" for s in config["sources"]):
        raise ValueError("La modalità gratuita non usa le API X: disattiva le fonti type=x")
    if config.get("allow_community_fallback"):
        LOG.warning("Fallback community abilitato: le segnalazioni restano attribuite")
    if config.get("publication_policy", {}).get("official_only"):
        if any(not approved_source(source) for source in config["sources"] if source.get("enabled", True)):
            raise ValueError("La configurazione ammette soltanto fonti ufficiali Sony/Rockstar verificate")


def collect_system_updates(db, config, fetcher=None):
    from playstation_system import fetch_system_update
    fetcher = fetcher or fetch_system_update
    settings = config.get("system_software", {})
    if not settings.get("enabled"):
        return 0
    errors = 0
    for platform in settings.get("platforms", ["PS5"]):
        identifier = "system:" + platform
        row = db.execute("SELECT * FROM monitors WHERE id=?", (identifier,)).fetchone()
        stamp = time.time()
        if row and row["next_due"] > stamp:
            continue
        interval = max(300, int(settings.get("interval", 3600)))
        previous = json.loads(row["state_json"]) if row and row["state_json"] else {}
        try:
            event = fetcher(platform)
            if not event_allowed(event, config.get("publication_policy", {})):
                raise ValueError("Fonte software di sistema esclusa dalla policy")
            version = event["version"].replace("-", ".")
            changed = bool(previous) and previous.get("version") != version
            sequence = previous.get("sequence", 0) + int(changed)
            event["event_key"] += ":transition:" + str(sequence)
            # Data osservata e disponibilità non vengono convertite in data di rilascio.
            history.import_history(db, [{"game": "PlayStation", "platform": platform, "region": "not_specified",
                "version": event["version"], "event_type": "system_software_available", "metric_kind": "availability",
                "observed_at": event["observed_at"], "source_url": event["source_url"], "source_tier": "primary",
                "verification": "verified", "notes": "Versione corrente dichiarata da Sony; data di rilascio non specificata."}])
            with db:
                if changed or (not previous and settings.get("announce_current", True)):
                    key = event["event_key"]
                    item = {"id": key, "key": key, "presentation": event, "trust": "official", "text": json.dumps(event, ensure_ascii=False)}
                    db.execute("INSERT OR IGNORE INTO posts(key,source_id,source_json) VALUES (?,?,?)",
                               (key, key, json.dumps(item, ensure_ascii=False)))
                state = {"version": version, "raw_version": event["version"], "sequence": sequence}
                db.execute("INSERT OR REPLACE INTO monitors VALUES (?,?,?,?,?)",
                           (identifier, json.dumps(state), stamp, None, stamp + interval))
            LOG.info("Software %s: %s", platform, event["version"])
        except Exception as error:
            errors += 1
            with db:
                db.execute("INSERT OR REPLACE INTO monitors VALUES (?,?,?,?,?)",
                           (identifier, json.dumps(previous) if previous else None, row["last_success"] if row else None,
                            type(error).__name__, stamp + interval))
            LOG.warning("Software %s non aggiornato (%s)", platform, type(error).__name__)
    return errors


def collect_catalog(db, config, fetcher=None):
    fetcher = fetcher or history.fetch_xbox_catalog
    stamp = time.time()
    last = float(get_meta(db, "xbox_checked") or 0)
    if stamp - last < int(config.get("catalog_interval", 3600)):
        return
    payload = fetcher(market="US", language="en-us")
    history.import_history(db, payload)
    # Una prima lettura diventa baseline, non una patch appena rilasciata.
    previous = get_meta(db, "xbox_signature")
    current = sources.digest([{key: signal.get(key) for key in
                               ("game", "platforms", "region", "metric_kind", "value_bytes", "version")}
                              for signal in payload["signals"]])
    sequence = int(get_meta(db, "xbox_sequence") or 0)
    with db:
        if previous is not None and previous != current:
            sequence += 1
            for signal in payload["signals"]:
                event = catalog_event(signal)
                event["event_key"] += ":transition:" + str(sequence)
                key = "catalog:" + str(sequence) + ":" + current + ":" + signal["id"]
                item = {"id": key, "key": key, "presentation": event,
                        "text": json.dumps(event, ensure_ascii=False), "trust": "observation"}
                db.execute("INSERT OR IGNORE INTO posts(key,source_id,source_json) VALUES (?,?,?)",
                           (key, key, json.dumps(item, ensure_ascii=False)))
        set_meta(db, "xbox_signature", current)
        set_meta(db, "xbox_sequence", sequence)
        set_meta(db, "xbox_checked", stamp)


def prepare_jobs(db, config):
    enforce_job_policy(db, config.get("publication_policy", {}))
    events, processed = [], []
    rows = db.execute("SELECT * FROM posts WHERE status='queued' ORDER BY created_at,rowid").fetchall()
    for row in rows:
        item = json.loads(row["source_json"])
        processed.append(row["key"])
        events.extend(event for event in article_events(item, config.get("allow_community_fallback", False))
                      if event_allowed(event, config.get("publication_policy", {})))
    grouped = group_platform_events(events)
    if config.get('ps5_focus'):
        grouped = [event for event in grouped if source_is_ps5_relevant(event)]
    with db:
        for event in grouped:
            # Fonte e orario di lettura non rendono diversa la stessa notizia.
            stable = {key: event.get(key) for key in ("event_key", "game", "category", "data_kind", "region",
                                                     "platforms", "facts", "version_namespace", "trust", "spoiler")}
            key = sources.digest(stable)
            db.execute("INSERT OR IGNORE INTO publish_jobs(key,event_json,status,text,created_at) VALUES (?,?,?,?,?)",
                       (key, json.dumps(event, ensure_ascii=False), "draft", format_post(event), time.time()))
        for key in processed:
            db.execute("UPDATE posts SET status='processed' WHERE key=?", (key,))
    return len(grouped)


def suppress_unpublished(db, reason="publishing_disabled", *, initialize=False):
    """Exclude *only* unsent drafts from future deliveries, without deleting history.

    The original job keys stay in the ledger so prepare_jobs() cannot regenerate
    them, and delivered/accepted/uncertain attempts are never altered. The first
    launch marker and suppression commit in ONE atomic transaction.
    """
    with db:
        result = db.execute(
            "UPDATE publish_jobs SET status='suppressed',last_error=? WHERE status='draft'",
            (reason,),
        )
        if initialize:
            set_meta(db, "publication_guard_initialized_v1", str(time.time()))
    return result.rowcount


def needs_first_publication_baseline(db):
    """First run after installing this safety guard cannot publish any backlog."""
    return get_meta(db, "publication_guard_initialized_v1") is None


def enforce_job_policy(db, policy):
    if not policy:
        return
    with db:
        for row in db.execute("SELECT key,event_json FROM publish_jobs WHERE status='draft'").fetchall():
            if not event_allowed(json.loads(row["event_json"]), policy):
                db.execute("UPDATE publish_jobs SET status='filtered',last_error='publication_policy' WHERE key=?", (row["key"],))


def reconcile(db, client):
    """Controlla solo ID Buffer già accettati; non ricrea mai il post."""
    for row in db.execute("SELECT * FROM publish_jobs WHERE status='accepted' AND next_attempt<=?", (time.time(),)).fetchall():
        try:
            delivery = client.delivery_status(row["buffer_id"])
        except BufferAPIError as error:
            with db:
                db.execute("UPDATE publish_jobs SET last_error=?,next_attempt=? WHERE key=?",
                           (type(error).__name__, time.time() + max(error.retry_after, 3600), row["key"]))
            continue
        status = "posted" if delivery.status == "sent" else "review" if delivery.status == "error" else "accepted"
        with db:
            db.execute("UPDATE publish_jobs SET status=?,external_url=?,next_attempt=? WHERE key=?",
                       (status, delivery.external_url, time.time() + 3600, row["key"]))


def deliver(db, client, upload, directory, render=render_card, checkpoint=None, policy=None,
            news_center_threads=False, require_official_media=False, media_resolver=official_image_for_event):
    if os.getenv('GTA6_REQUIRE_ALL_POST_PHOTOS') == 'true':
        # Production: one illustrated message; never generated cards or logo fallback.
        news_center_threads = False
        require_official_media = True
        media_resolver = lambda event: official_media_for_event(event, allow_logo=False).url
    enforce_job_policy(db, policy or {})
    reconcile(db, client)
    from editorial_director_v142 import allowed as director_allowed
    from quality_publish_policy_v1 import verified_urgent
    # The shared budget is checked per verified candidate, not once before
    # discovery; only confirmed official emergencies use the separate budget.
    # Un'interruzione durante la richiesta non deve causare un nuovo invio cieco.
    with db:
        db.execute("UPDATE publish_jobs SET status='uncertain' WHERE status='sending'")
    sent = db.execute("SELECT count(*) FROM publish_jobs WHERE status IN ('posted','accepted','uncertain','sending') AND attempted_at>?",
                      (time.time() - 86400,)).fetchone()[0]
    for row in db.execute("SELECT * FROM publish_jobs WHERE status='draft' AND next_attempt<=? ORDER BY created_at,key",
                          (time.time(),)).fetchall():
        daily_limit = 40 if essentials_window_active() else 20
        if sent >= daily_limit:
            LOG.warning("Limite prudenziale di %s invii/giorno: altre bozze conservate", daily_limit)
            break
        event = json.loads(row["event_json"])
        publication_kind="official_breaking" if verified_urgent(event) else "ordinary"
        if os.getenv('EDITORIAL_DIRECTOR_V142_ENABLED','false').lower() == 'true':
            ok,reason=director_allowed(datetime.now(timezone.utc),kind=publication_kind)
            if not ok:
                LOG.info("DIRECTOR_HOLD: %s (%s)",reason,publication_kind)
                continue
        if event.get("demo"):
            with db:
                db.execute("UPDATE publish_jobs SET status='review',last_error='demo_not_publishable' WHERE key=?", (row["key"],))
            continue
        if client.destination is None:
            # Il controllo del canale non è una richiesta di pubblicazione.
            # Una configurazione errata lascia la bozza pronta per la correzione.
            client.verify_destination()
        # Free official YouTube link shares use a fixed, fully Italian template.
        # Avoid paid X read APIs and avoid requesting translations for these
        # source-verified videos. A URL share is NOT a native repost.
        free_video_enabled = (os.getenv('VIDEO_LINK_CARDS_V12', 'false').strip().lower() == 'true' or
                              os.getenv('OFFICIAL_LINKS_FREE_ENABLED', 'false').strip().lower() == 'true')
        video_text = None
        if free_video_enabled:
            from video_cards_v12 import video_link_post
            video_text = video_link_post(event)
        # All other posts still need the mandatory Italian translation gate.
        if not video_text and contains_english_prose(str(event.get('title') or '')):
            try:
                event = {**event, 'title': italian_title(str(event['title']), 'en')}
            except TranslationUnavailable:
                with db:
                    db.execute("UPDATE publish_jobs SET status='review',last_error='italian_translation_unavailable' WHERE key=?", (row["key"],))
                LOG.warning('Notizia non pubblicata: traduzione italiana non disponibile')
                continue
        thread = None if video_text else (thread_for_event(event) if news_center_threads else None)
        media_url = None
        if video_text:
            # An X link preview is not an attached image.  Use only the
            # verifiable thumbnail of the exact Rockstar-channel YouTube video.
            # Resolve BEFORE reserving a delivery or contacting Buffer.
            try:
                selected_video_media = official_media_for_event(event)
                if selected_video_media.kind != 'video_thumbnail':
                    raise OfficialMediaUnavailable('video_thumbnail_unavailable')
                media_url = selected_video_media.url
            except OfficialMediaUnavailable as error:
                with db:
                    db.execute("UPDATE publish_jobs SET status='review',last_error=? WHERE key=?",
                               (str(error), row["key"]))
                LOG.warning("Video ufficiale trattenuto: manca la miniatura verificata (%s)", str(error))
                continue
        elif require_official_media:
            try:
                media_url = media_resolver(event)
            except OfficialMediaUnavailable as error:
                # No official relevant image -> no generated card and NO text-only publication.
                # Human can review the event; retaining this key prevents duplicate retries.
                with db:
                    db.execute("UPDATE publish_jobs SET status='review',last_error=? WHERE key=?",
                               (str(error), row["key"]))
                LOG.warning("Notizia in revisione: manca un'immagine ufficiale verificata (%s)", str(error))
                continue
        else:
            # The locally rendered editorial card is required for BOTH
            # standalone posts and threads in this non-official-only mode.
            card = Path(directory) / (row["key"] + ".png")
            render(event, card)
            media_url = upload(card)
        if not isinstance(media_url, str) or not media_url.startswith('https://'):
            # Never write 'sending' and never reserve a director slot for a
            # post that the Buffer client will reject without a photo.
            with db:
                db.execute("UPDATE publish_jobs SET status='review',last_error='image_missing_before_buffer' WHERE key=?",
                           (row["key"],))
            LOG.warning('Invio trattenuto: nessuna immagine HTTPS prima di Buffer')
            continue
        if os.getenv('GTA6_REQUIRE_ALL_POST_PHOTOS') == 'true':
            from photo_rights_v1 import attachment_allowed
            if not attachment_allowed(media_url,event.get('source_url')):
                with db:
                    db.execute("UPDATE publish_jobs SET status='review',last_error='photo_rights_unverified' WHERE key=?",
                               (row["key"],))
                LOG.warning('PHOTO_RIGHTS_HOLD: fonte ufficiale non equivale a permesso di riutilizzo')
                continue
        # V12: optional persistent image uniqueness, including archived bootstrap
        # images. Never republish a used thumbnail; hold the event for review.
        # Default OFF so deploying v12 cannot interfere with today's live v11.
        if require_official_media and os.getenv('V12_UNIQUE_IMAGES', 'false').lower() == 'true':
            from image_registry_v12 import reserve_image
            journal = ROOT / 'bootstrap-gta6-v3-state.json'
            if not reserve_image(db, media_url, row['key'], archive_path=journal):
                with db:
                    db.execute("UPDATE publish_jobs SET status='review',last_error='image_already_used_v12' WHERE key=?",
                               (row['key'],))
                LOG.warning('V12: official image already used or not verifiable; hold for review')
                continue
        # Ricalcola il testo per applicare il SEO editoriale anche alle bozze
        # create prima dell'aggiornamento (mai ai post gia' spediti).
        single_text = video_text or (format_post(event) if thread is None else row["text"])
        # Fail closed at delivery: no English paragraph can escape via a
        # pre-existing draft, thread facts or YouTube card.
        outgoing = list(thread) if thread is not None else [single_text]
        if any(contains_english_prose(message) for message in outgoing):
            with db:
                db.execute("UPDATE publish_jobs SET status='review',last_error='english_text_not_publishable' WHERE key=?", (row["key"],))
            LOG.warning('Invio trattenuto: testo non completamente italiano')
            continue
        if os.getenv('EDITORIAL_DIRECTOR_V142_ENABLED','false').lower() == 'true':
            from editorial_director_v142 import note_monitor_attempt
            now_policy=datetime.now(timezone.utc)
            units=len(thread) if thread is not None else 1
            # Count two thread messages as TWO X posts before writing to Buffer.
            ok,reason=director_allowed(now_policy,kind=publication_kind,units=units)
            if not ok:
                LOG.info("DIRECTOR_HOLD: %s (%s, %s messages)",reason,publication_kind,units)
                continue
        with db:
            db.execute("UPDATE publish_jobs SET status='sending',text=?,attempted_at=? WHERE key=?",
                       (single_text, time.time(), row["key"]))
        if os.getenv('EDITORIAL_DIRECTOR_V142_ENABLED','false').lower() == 'true':
            note_monitor_attempt(event,now_policy,kind=publication_kind,units=units)
        if checkpoint:
            # Il journal remoto precede l'invio: un runner interrotto non lo ripete alla cieca.
            checkpoint()
        stop = False
        try:
            identifier = (client.publish_thread(thread, media_url=media_url) if thread is not None
                          else client.publish(single_text, media_url=media_url))
        except BufferPending as error:
            with db:
                db.execute("UPDATE publish_jobs SET status='accepted',buffer_id=?,next_attempt=? WHERE key=?",
                           (error.post_id, time.time() + 3600, row["key"]))
            sent += 1
        except BufferDeliveryFailed as error:
            with db:
                db.execute("UPDATE publish_jobs SET status='review',buffer_id=?,last_error=? WHERE key=?",
                           (error.post_id, type(error).__name__, row["key"]))
        except FreeQuotaExceeded:
            with db:
                db.execute("UPDATE publish_jobs SET status='draft' WHERE key=?", (row["key"],))
            raise
        except BufferAPIError as error:
            status = "uncertain" if error.outcome_unknown else "draft" if error.status == 429 else "review"
            with db:
                db.execute("UPDATE publish_jobs SET status=?,last_error=?,next_attempt=? WHERE key=?",
                           (status, type(error).__name__, time.time() + max(error.retry_after, 3600), row["key"]))
            if error.outcome_unknown:
                sent += 1
            stop = error.status == 429 or error.outcome_unknown
        except Exception:
            with db:
                db.execute("UPDATE publish_jobs SET status='uncertain',last_error='unexpected_delivery_error' WHERE key=?", (row["key"],))
            raise
        else:
            with db:
                db.execute("UPDATE publish_jobs SET status='posted',buffer_id=?,external_url=? WHERE key=?",
                           (identifier, getattr(client.last_delivery, "external_url", None), row["key"]))
            sent += 1
        if checkpoint:
            checkpoint()
        if stop or os.getenv('EDITORIAL_DIRECTOR_V142_ENABLED','false').lower() == 'true':
            break  # One publication per scheduled monitor run while the global director is on.



def export_csv(payload, destination):
    columns = [("Gioco", "game"), ("Console", "platform"), ("Regione", "region"),
               ("Tipo misura", "metric_kind"), ("Versione", "version"), ("Tipo evento", "event_type"),
               ("Data evento o resoconto", "occurred_at"), ("Precisione data", "date_precision"),
               ("Prima osservazione", "first_observed_at"), ("Byte esatti", "size_bytes"),
               ("Valore originale", "value"), ("Unità originale", "unit_original"),
               ("Qualificatore", "qualifier"), ("Livello fonte", "source_tier"),
               ("Verifica", "verification"), ("Fonte", "source_url")]
    with Path(destination).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[label for label, _ in columns])
        writer.writeheader()
        for record in payload["records"]:
            values = {label: record.get(key) for label, key in columns}
            values["Versione"] = values["Versione"] or "NON VERIFICATA"
            writer.writerow(values)


def export_public_history(db, destination, policy):
    # Le righe precedenti restano nell'archivio interno; l'esportazione corrente
    # rispetta lo stesso filtro dei nuovi post, anche dopo un cambio configurazione.
    private = ROOT / ".runtime" / "history-all.json"
    payload = history.export_history(db, private)
    if policy:
        payload["records"] = [row for row in payload["records"] if history_record_allowed(row, policy)]
        payload["gaps"] = [gap for gap in payload.get("gaps", [])
                           if gap.get("platform", "").startswith("PS") and gap.get("source_url", "").startswith("https://store.playstation.com/")]
        payload.pop("research_candidates", None)
        payload["coverage"] = {"scope": "GTA e PlayStation; software di sistema PS5 e PS5 Pro", "official_only": True,
                               "starts_with_official_preload": "2026-11-10", "complete": False,
                               "first_downloadable_build_verified": False,
                               "notes": "Sono inclusi soltanto dati di fonti ufficiali. Le build iniziali non verificabili restano mancanti."}
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def checkpoint_state(db, db_path, encrypted, password):
    from cloud_state import save_state
    db.commit()
    save_state(db_path, encrypted, password)
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    commands = [
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        ["git", "add", "--", str(encrypted)],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, capture_output=True)
    if changed.returncode == 0:
        return
    if changed.returncode != 1:
        raise RuntimeError("Impossibile verificare il checkpoint Git")
    for command in (["git", "commit", "-m", "Persist automated delivery journal"],
                    ["git", "pull", "--rebase", "--autostash", "origin", os.getenv("GITHUB_BRANCH", "main")],
                    ["git", "push", "origin", "HEAD:" + os.getenv("GITHUB_BRANCH", "main")]):
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True)


def main():
    from cloud_state import restore_state, save_state
    from github_assets import GitHubAssetHost
    from state_health import meaningful_fingerprint, load_health, save_health
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Un controllo: GitHub gestisce la ricorrenza")
    parser.add_argument("--config", default=str(ROOT / "sources.free.json"))
    parser.add_argument("--demo", action="store_true", help="Solo card dimostrative, senza rete né credenziali")
    args = parser.parse_args()
    if args.demo:
        for name, event in zip(("shared-demo", "ps5-demo"), demo_events()):
            render_card(event, ROOT / "previews" / (name + ".png"))
        return
    password = os.getenv("STATE_PASSWORD", "")
    if len(password) < 16:
        raise ValueError("Configura STATE_PASSWORD con almeno 16 caratteri nei Secrets GitHub")
    db_path = Path(os.getenv("DATABASE", str(ROOT / ".runtime" / "bot.sqlite3")))
    encrypted = Path(os.getenv("ENCRYPTED_STATE", str(ROOT / ".state" / "bot.enc")))
    restore_state(encrypted, db_path, password)
    db = open_db(db_path)
    health_path = ROOT / "monitor-health.json"
    load_health(db, health_path)
    original_fingerprint = meaningful_fingerprint(db)
    config = prioritize_ps5_and_launch_sources(sources.load_config(args.config))
    source_policy(config)
    mode = os.getenv("RUN_MODE", "check")
    publishing_enabled = os.getenv("AUTO_PUBLISH", "false").strip().lower() == "true"
    # The first deployment of the guard establishes a no-backfill baseline.
    # Setup only lists Buffer channels and never changes publication state.
    first_baseline = mode in {"check", "collect", "run"} and needs_first_publication_baseline(db)
    errors = 0
    try:
        seed = json.loads((ROOT / config.get("history_seed", "history-seed.json")).read_text())
        history.import_history(db, seed)
        reported_path = ROOT / "history-reported.json"
        if reported_path.exists() and not config.get("publication_policy", {}).get("official_only"):
            # Arricchisce solo il ledger con qualità 'reported', mai una coda di notizie appena uscite.
            history.import_history(db, json.loads(reported_path.read_text()))
        if mode == "setup":
            client = BufferClient(request_guard=FreeRequestBudget(db))
            for channel in client.list_channels():
                if channel.get("service") in {"twitter", "x"}:
                    print(json.dumps({key: channel.get(key) for key in ("id", "name", "service", "externalLink")}, ensure_ascii=False))
            return
        # Le fonti dirette sono controllate prima di qualsiasi fallback.
        refresh_launch_poll_deadlines(db, config)
        errors += sources.poll(db, config, client=None)
        if config.get("collect_xbox_catalog", False):
            try:
                collect_catalog(db, config)
            except Exception as error:
                errors += 1
                LOG.warning("Catalogo non aggiornato (%s), dati precedenti conservati", type(error).__name__)
        errors += collect_system_updates(db, config)
        prepare_jobs(db, config)
        draft_rows = db.execute("SELECT * FROM publish_jobs WHERE status='draft' ORDER BY created_at LIMIT 3").fetchall()
        if mode == "check":
            for row in draft_rows:
                event = json.loads(row["event_json"])
                if config.get("official_images_only", False):
                    try:
                        selection = official_media_for_event(event)
                        from urllib.parse import urlsplit
                        description = "LOGO UFFICIALE (ultima opzione)" if selection.kind == "official_logo" else "IMMAGINE UFFICIALE"
                        print(description + " — " + urlsplit(selection.url).hostname + " | Credito: " + selection.credit_url)
                    except OfficialMediaUnavailable as error:
                        print("FOTO UFFICIALE NON DISPONIBILE — invio automatico bloccato (" + str(error) + ")")
                else:
                    card = ROOT / ".runtime" / "previews" / (row["key"] + ".png")
                    render_card(event, card)
                if config.get("news_center_threads", False):
                    parts = news_center_preview(event)
                    print(f"ANTEPRIMA — {len(parts)} post; nessun invio")
                    for part in parts:
                        print("BOZZA — " + part)
                else:
                    print("BOZZA — " + row["text"])
            print(f"Controllo terminato: {len(draft_rows)} bozze visibili, {errors} fonti con errori; nessun invio")

        # IMPORTANT: previews made while automatic posting is disabled are not a
        # backlog. The first run after this upgrade also quarantines all prior
        # drafts, even if someone enabled AUTO_PUBLISH prematurely.
        if mode in {"check", "collect", "run"}:
            if first_baseline or not publishing_enabled:
                reason = "pre_launch_baseline" if first_baseline else "publishing_disabled"
                suppressed = suppress_unpublished(db, reason, initialize=first_baseline)
                print(f"Filtro anti-arretrati: {suppressed} bozze archiviate "+
                      "senza invio; storico e chiavi anti-duplicato conservati")
        if mode == "run":
            if publishing_enabled:
                # Nessun client Buffer su cicli vuoti: niente query sprecate.
                waiting = db.execute("SELECT count(*) FROM publish_jobs WHERE status IN ('draft','accepted')").fetchone()[0]
                if waiting:
                    host = GitHubAssetHost()
                    client = BufferClient(request_guard=FreeRequestBudget(db))
                    try:
                        deliver(db, client, host.upload, ROOT / ".runtime" / "cards",
                                checkpoint=lambda: checkpoint_state(db, db_path, encrypted, password),
                                policy=config.get("publication_policy", {}),
                                news_center_threads=config.get("news_center_threads", False),
                                require_official_media=config.get("official_images_only", False))
                    except FreeQuotaExceeded:
                        LOG.warning("Quota gratuita locale esaurita: bozze conservate, nessun acquisto")
            else:
                LOG.info("AUTO_PUBLISH=false: raccolta e anteprime senza coda pubblicabile; nessun invio")
        elif mode == "collect":
            print(f"MONITOR_RELEASE_COLLECTION_OK errors={errors}; no Buffer calls or preview text")
        elif mode != "check":
            raise ValueError("RUN_MODE deve essere setup, check, collect o run")
        # Research RSS is strictly lower priority than official breaking news.
        # Do NOT delay the normal v11 publisher to wait for secondary sources.
        # V12 intelligence is separately switchable, fully READ-ONLY toward
        # Buffer/X, and its press items NEVER enter v11 publish_jobs.
        if mode != 'collect' and os.getenv('INTELLIGENCE_V12_ENABLED', 'false').strip().lower() == 'true':
            try:
                from intelligence_v12 import poll as poll_intelligence, report as report_intelligence
                result = poll_intelligence(db, ROOT / 'intelligence-sources-v12.json')
                LOG.info('V12 RSS: checked=%s baseline=%s new=%s errors=%s',
                         result['checked'], result['baseline'], result['new'], result['errors'])
                report_intelligence(db, max_display=30, output_path=ROOT / '.runtime' / 'intelligence-v12-report.json')
                errors += result['errors']
            except Exception as error:
                errors += 1
                LOG.warning('V12 RSS unavailable (%s); original official pipeline remains active', type(error).__name__)
        # V12.1: weekly GTAV Online and VI launch radar. Research-only, independently
        # switchable from the official publishing engine and from RSS research.
        if mode != 'collect' and os.getenv('WEEKLY_RADAR_V12_ENABLED', 'false').strip().lower() == 'true':
            try:
                from weekly_radar_v12 import poll as weekly_poll, report as weekly_report
                weekly_status = weekly_poll(db)
                LOG.info('V12.1 WEEKLY RADAR: checked=%s baseline=%s new=%s errors=%s deferred=%s',
                         weekly_status['checked'], weekly_status['baseline'],
                         weekly_status['candidates'], weekly_status['errors'], weekly_status['deferred'])
                weekly_report(db, ROOT / '.runtime' / 'weekly-radar-v12.json')
                errors += weekly_status['errors']
            except Exception as error:
                errors += 1
                LOG.warning('Weekly research unavailable (%s); official pipeline unaffected', type(error).__name__)
        # V13: official Rockstar GTA Online editorial digest (source-grounded).
        # No media reuploads or press autoposts; no historical backfill.
        if mode != 'collect' and os.getenv('EDITORIAL_V13_ENABLED', 'false').strip().lower() == 'true':
            try:
                from editorial_v13 import research as v13_research, report as v13_report, deliver_ready as v13_deliver
                v13_status = v13_research(db)
                LOG.info('V13 OFFICIAL EDITORIAL: checked=%s baseline=%s new=%s eligible=%s errors=%s',
                         v13_status['checked'],v13_status['baseline'],v13_status['new'],
                         v13_status['eligible'],v13_status['errors'])
                v13_report(db, ROOT / '.runtime' / 'editorial-v13-report.json')
                errors += v13_status['errors']
                v13_auto = os.getenv('EDITORIAL_V13_AUTOPUBLISH','false').strip().lower() == 'true'
                if mode == 'run' and publishing_enabled and v13_auto:
                    pending = db.execute("SELECT COUNT(*) FROM editorial_v13_articles WHERE status IN ('ready','accepted')").fetchone()[0]
                    if pending:
                        v13_client = BufferClient(request_guard=FreeRequestBudget(db))
                        try:
                            dispatched = v13_deliver(db,client=v13_client,
                                 checkpoint=lambda: checkpoint_state(db, db_path, encrypted, password))
                            LOG.info('V13 delivery: sent=%s accepted=%s review=%s deferred=%s',
                                     dispatched['sent'],dispatched['accepted'],
                                     dispatched['review'],dispatched['deferred'])
                        except FreeQuotaExceeded:
                            LOG.warning('V13: local Buffer request guard reached; no editorial post')
            except Exception as error:
                errors += 1
                LOG.warning('V13 editorial radar unavailable (%s); v11 and v12 unaffected',type(error).__name__)
    finally:
        exported = export_public_history(db, ROOT / "history-public.json", config.get("publication_policy", {}))
        export_csv(exported, ROOT / "history-public.csv")
        save_health(db, health_path)
        changed = original_fingerprint != meaningful_fingerprint(db)
        db.commit()
        db.close()
        if changed or not encrypted.exists():
            save_state(db_path, encrypted, password)
    print("Stato e storico salvati")
    if errors:
        print("Alcune fonti non sono state aggiornate; consulta i log. Nessuna novità è stata inventata.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
