"""One-shot, official GTA VI editorial catch-up for Federiko X via Buffer.

Only queues verified historical summaries; never invokes shareNow. The durable
journal is committed BEFORE each API mutation, preventing blind retries.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

from buffer_publisher import BufferClient, BufferAPIError, CREATE_MUTATION
from official_media import official_media_for_event, OfficialMediaUnavailable
from presentation import _post_weight

ROOT = Path(__file__).resolve().parent
JOURNAL = ROOT / "bootstrap-gta6-v1-state.json"
EXPECTED_USERNAME = "xFederiko11"
MAX_INITIAL_THREADS = 8
SPACING_MINUTES = 110
START_DELAY_MINUTES = 30


@dataclass(frozen=True)
class Topic:
    key: str
    heading: str
    summary: str
    detail: str
    source_url: str
    official_image_url: str | None = None


# Editorial summaries based exclusively on dated official Rockstar announcements.
# An archive is not breaking news. Topic keys remain stable across reruns.
TOPICS = (
    Topic("gta6-overview", "GTA VI: IL PUNTO UFFICIALE",
          "Vice City torna al centro della scena. Jason e Lucia sono i protagonisti "
          "di una storia ambientata nello stato di Leonida.",
          "Rockstar indica il 19 novembre 2026 come data di uscita per PS5 e Xbox Series X|S.",
          "https://www.rockstargames.com/VI",
          "https://www.rockstargames.com/VI/_next/static/media/"
          "Jason_Lucia_Rooftop_landscape.0c6p5do~-8~7..jpg"),
    Topic("gta6-characters", "JASON E LUCIA",
          "Due protagonisti, una rapina che va storta e una cospirazione che "
          "attraversa Leonida: questa è la premessa ufficiale di GTA VI.",
          "Rockstar descrive la coppia come costretta a fidarsi l'uno dell'altra "
          "per uscire viva da un mondo criminale sempre più pericoloso.",
          "https://www.rockstargames.com/VI"),
    Topic("gta6-trailer", "TRAILER DI LANCIO",
          "Il trailer di lancio di GTA VI è online dal 15 ottobre 2026. "
          "Mostra nuovi scorci di Vice City e della storia di Jason e Lucia.",
          "La musica del trailer include 'Flower in a Hurricane' dei Justice. "
          "Guarda il filmato completo sul sito Rockstar.",
          "https://www.rockstargames.com/newswire/article/517572321a549a/"
          "watch-the-grand-theft-auto-vi-launch-trailer"),
    Topic("gta6-extended", "ANTEPRIMA IN GAME",
          "L'anteprima estesa ufficiale di GTA VI è stata acquisita "
          "interamente con sequenze di gioco su PlayStation 5.",
          "Rockstar l'ha pubblicata il 27 agosto 2026. "
          "È disponibile anche sul sito ufficiale del gioco.",
          "https://www.rockstargames.com/VI/an-extended-look"),
    Topic("gta6-ps5pro", "PS5 PRO E PRESTAZIONI",
          "GTA VI punta a 30 FPS sulle console supportate. "
          "Su PS5 Pro Rockstar segnala maggiore nitidezza con PSSR "
          "e ombre ray tracing esclusive.",
          "Il supporto a 60 FPS non è confermato in questo annuncio. "
          "Il preload digitale è partito il 10 novembre.",
          "https://www.rockstargames.com/newswire/article/89834o94713o21/"
          "pre-load-grand-theft-auto-vi-now"),
    Topic("gta6-gallery", "GALLERIA DI LANCIO",
          "Rockstar ha pubblicato il 5 novembre 2026 "
          "una nuova galleria ufficiale di GTA VI: Vice City e altri scorci di Leonida.",
          "Gli screenshot sono accessibili nella Launch Gallery ufficiale, "
          "senza immagini create da IA.",
          "https://www.rockstargames.com/newswire/article/39ak81277255o9/"
          "explore-the-grand-theft-auto-vi-launch-gallery"),
    Topic("gta6-radio", "RADIO E PODCAST",
          "GTA VI include nuove radio e podcast on demand. "
          "Rockstar conferma l'ascolto anche a piedi con cuffie collegate allo smartphone.",
          "Tra le stazioni presentate: Flash FM, Cocoteo FM, AfroBank FM "
          "e The Chamber 106.6.",
          "https://www.rockstargames.com/newswire/article/o3982oa93a23k4/"
          "the-music-of-grand-theft-auto-vi-in-game-radio-stations"),
    Topic("gta6-score", "COLONNA SONORA",
          "La colonna sonora originale di GTA VI è firmata Justice. "
          "Rockstar la descrive come una partitura adattiva.",
          "L'album Original Score, con 30 brani, è annunciato per l'11 dicembre 2026. "
          "È distinto da GTA VI: The Album, previsto per il 19 novembre.",
          "https://www.rockstargames.com/newswire/article/39ak8a12395591/"
          "grand-theft-auto-vi-original-score-by-justice"),
)


def make_thread(topic):
    first = f"1/2 \U0001f3ae GTA VI | {topic.heading}\n\n{topic.summary}\n\nARCHIVIO UFFICIALE #GTAVI"
    second = f"2/2 \U0001f4f0 {topic.detail}\n\nFonte Rockstar: {topic.source_url}\n#GTA6"
    for text in (first, second):
        if _post_weight(text) > 280:
            raise ValueError(f"Post troppo lungo per X: {topic.key} ({_post_weight(text)})")
    return [first, second]


def load_journal(path=JOURNAL):
    if not Path(path).exists():
        return {"version": 1, "items": {}}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("items"), dict):
        raise RuntimeError("Journal bootstrap non valido; stop senza invio")
    return data


def write_journal(state, path=JOURNAL):
    path = Path(path)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def git_checkpoint(path=JOURNAL):
    """Push the journal before a network mutation; failures abort sending."""
    path = Path(path)
    commands = [
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        ["git", "add", "--", str(path.relative_to(ROOT))],
    ]
    for cmd in commands:
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if changed.returncode == 0:
        return
    if changed.returncode != 1:
        raise RuntimeError("Journal non verificabile")
    for cmd in (["git", "commit", "-m", "Checkpoint GTA VI bootstrap"],
                ["git", "pull", "--rebase", "origin", "main"],
                ["git", "push", "origin", "HEAD:main"]):
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)


def schedule_thread(client, parts, image, due_at):
    items = [{"text": t, "assets": []} for t in parts]
    items[0]["assets"] = [{"image": {"url": client._media_url(image)}}]
    post_input = {
        "channelId": client.channel_id,
        "text": parts[0],
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": due_at.isoformat().replace("+00:00", "Z"),
        "saveToDraft": False,
        "assets": [],
        "metadata": {"twitter": {"thread": items}},
    }
    result = client._graphql(CREATE_MUTATION, {"input": post_input}, mutation=True).get("createPost")
    if not isinstance(result, dict):
        raise BufferAPIError("Risposta creazione Buffer incompleta", outcome_unknown=True)
    if not result.get("post"):
        raise BufferAPIError("Creazione pianificata rifiutata; verificare Buffer", outcome_unknown=not bool(result.get("message")))
    delivery = client._delivery(result["post"])
    if delivery.status not in {"buffer", "scheduled"}:
        raise BufferAPIError("Stato Buffer inatteso: verificare prima di riprovare", outcome_unknown=True, post_id=delivery.post_id)
    return delivery


def run(*, client=None, media_resolver=official_media_for_event, now=None,
        state_path=JOURNAL, checkpoint=git_checkpoint, environ=None, max_threads=MAX_INITIAL_THREADS):
    env = os.environ if environ is None else environ
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("GTA6_BOOTSTRAP_QUEUE") != "YES_QUEUE":
        raise RuntimeError("Solo avvio manuale esplicito del workflow bootstrap")
    if env.get("GITHUB_REF") not in {"refs/heads/main", None}:
        raise RuntimeError("Il bootstrap deve essere eseguito sul branch main")
    state = load_journal(state_path)
    if any(rec.get("status") in {"sending", "review"} for rec in state["items"].values()):
        raise RuntimeError("Invio precedente incerto: controllare Buffer prima di un nuovo avvio")
    topics = list(TOPICS)[:max_threads]
    for topic in topics:
        make_thread(topic)
    if client is None:
        client = BufferClient(expected_username=EXPECTED_USERNAME)
    client.verify_destination()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Orario senza fuso non consentito")
    now = now.astimezone(timezone.utc)
    already_scheduled = sum(1 for rec in state["items"].values() if rec.get("status") == "scheduled")
    created = 0
    for topic in topics:
        if topic.key in state["items"]:
            print(f"SKIP {topic.key}: gia' registrato")
            continue
        event = {"source_url": topic.source_url, "trust": "official", "title": "GTA VI " + topic.heading,
                 "game": "GTA VI"}
        if topic.official_image_url:
            event["official_image_url"] = topic.official_image_url
        try:
            photo = media_resolver(event)
        except OfficialMediaUnavailable as exc:
            print(f"SKIP {topic.key}: immagine ufficiale assente ({str(exc)})")
            continue
        parts = make_thread(topic)
        due = now + timedelta(minutes=START_DELAY_MINUTES + (already_scheduled + created) * SPACING_MINUTES)
        # If created at night, still spread across the day. No shareNow mode exists.
        state["items"][topic.key] = {"status": "sending", "source": topic.source_url,
                                      "image_kind": photo.kind, "due_at": due.isoformat()}
        write_journal(state, state_path)
        checkpoint(state_path)   # Durable BEFORE the API call.
        try:
            delivery = schedule_thread(client, parts, photo.url, due)
        except Exception:
            # sending remains in the committed journal. No blind retry.
            state["items"][topic.key]["status"] = "review"
            write_journal(state, state_path)
            checkpoint(state_path)
            raise
        state["items"][topic.key].update(status="scheduled", buffer_id=delivery.post_id)
        write_journal(state, state_path)
        checkpoint(state_path)
        created += 1
        local_time = due.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d/%m/%Y %H:%M %Z")
        print(f"SCHEDULED {topic.key}: Buffer id={delivery.post_id}; media={photo.kind}; time={local_time}")
    print(f"Bootstrap completed: {created} threads scheduled, {already_scheduled} previously scheduled")
    return created


if __name__ == "__main__":
    run()
