"""GTA VI chronological launch archive v11 for Federiko X via Buffer.

Preview is network-free. Explicit schedule creates timed posts, not shareNow.
The v3 journal is checkpointed BEFORE each mutation; no blind retries.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

from buffer_publisher import BufferClient, BufferAPIError, CREATE_MUTATION
from official_media import (official_media_for_event, OfficialMediaUnavailable,
                            OfficialMediaChoice, _probe_image, approved_image_url,
                            source_family, PLAYSTATION_LOGO)
from presentation import _post_weight

ROOT = Path(__file__).resolve().parent
JOURNAL = ROOT / "bootstrap-gta6-v3-state.json"
EXPECTED_USERNAME = "xFederiko11"
MAX_INITIAL_THREADS = None  # Essentials supports a large queue; editorial quality decides volume.
SPACING_MINUTES = 12  # Nominal pace: 25 distinct threads across about five hours.
MIN_SPACING_MINUTES = 8  # Do not squeeze more tightly if installed late.
START_DELAY_MINUTES = 12
ARCHIVE_DAY_UTC = "2026-11-18"
# Absolute deadline requested by the user: 18 Nov 2026, 07:50 GMT == UTC.
X_PUBLICATION_DEADLINE_UTC = datetime(2026, 11, 18, 7, 50, tzinfo=timezone.utc)
# Buffer is scheduled EARLIER: 80-minute delivery margin, never at the X deadline.
BUFFER_LAST_SCHEDULED_UTC = datetime(2026, 11, 18, 6, 30, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Topic:
    key: str
    heading: str
    summary: str
    detail: str
    source_url: str
    official_image_url: str | None = None


# Curated and dated Rockstar-only editorial archive for 18-19 Nov 2026.
# Media URLs originate from official Rockstar media gallery. No AI images.
# Do not remove stable topic IDs once scheduled.
MEDIA_ROOT = 'https://www.rockstargames.com/VI/_next/static/media/'
USER_LOGO_FALLBACKS = (
    "https://media-rockstargames-com.akamaized.net/tina-uploads/posts/258aa538o412ok/5690872e70df76d5d63638c12e7eb5b746f83c3a.jpg",
    "https://www.rockstargames.com/VI/_next/static/media/meta.0t8ty~nlmxq2s.jpg",
)
TOPICS = (
    Topic('gta6-overview', 'IL PUNTO UFFICIALE', 'Data annunciata: 19 novembre 2026. GTA VI arriva su PlayStation 5 e Xbox Series X|S. La storia segue Jason e Lucia nello stato di Leonida.', 'Un nuovo viaggio a Vice City e oltre. Questa scheda riassume informazioni gi\u00e0 pubblicate da Rockstar: non \u00e8 una breaking news.', 'https://www.rockstargames.com/VI', 'https://www.rockstargames.com/VI/_next/static/media/Official_Cover_Art_landscape.12.uu2irr.2_a.jpg'),
    Topic('gta6-jason', 'CHI E JASON DUVAL', 'Jason Duval \u00e8 uno dei due protagonisti di GTA VI. Rockstar lo presenta come un uomo che cerca una vita pi\u00f9 semplice ma incrocia ancora il crimine.', 'La sua storia \u00e8 legata a Lucia Caminos e alla rete criminale di Leonida. Personaggi e biografie sono disponibili sul sito ufficiale.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Jason_Duval_01.07m377xeb6jhq.jpg'),
    Topic('gta6-lucia', 'CHI E LUCIA CAMINOS', 'Lucia Caminos \u00e8 coprotagonista di GTA VI. Dopo il carcere, vuole cambiare le proprie possibilit\u00e0 e costruirsi un futuro diverso.', 'La sua relazione con Jason e al centro della trama raccontata da Rockstar. La presentazione ufficiale descrive ambizioni e rischi.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_01.0a7yqvewctkfp.jpg'),
    Topic('gta6-pair', 'JASON + LUCIA', 'Una rapina andata male porta Jason e Lucia in una cospirazione criminale che attraversa Leonida: questa \u00e8 la premessa narrativa ufficiale.', 'Rockstar sottolinea che i due devono affidarsi l\u2019uno all\u2019altra per sopravvivere. Qui niente teorie sulla trama: solo annunci confermati.', 'https://www.rockstargames.com/VI', 'https://www.rockstargames.com/VI/_next/static/media/Jason_and_Lucia_Robbery_landscape.09c8a~do21h4p.jpg'),
    Topic('gta6-vice', 'VICE CITY', 'Vice City torna in GTA VI: luci al neon, spiagge e quartieri urbani sono al centro della presentazione di Rockstar.', 'La metropoli \u00e8 solo una parte dello stato di Leonida. Consulta la sezione People & Places per esplorare le ambientazioni ufficiali.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Vice_City_Postcard_landscape.0v2njmlk2n-qm.jpg'),
    Topic('gta6-keys', 'LEONIDA KEYS', 'Le Leonida Keys sono tra le aree mostrate da Rockstar: isole, ponti e paesaggi costieri oltre Vice City.', 'L artwork ufficiale mostra la geografia dell arcipelago. E una presentazione delle ambientazioni, non una conferma su missioni o meccaniche.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_Postcard_landscape.05oezf2h--~ed.jpg'),
    Topic('gta6-port', 'PORT GELLHORN', 'Port Gellhorn \u00e8 una delle localit\u00e0 confermate di GTA VI. Rockstar l ha presentata tra le tappe del viaggio a Leonida.', 'La cartolina ufficiale ne mostra il paesaggio urbano e ferroviario. Per altri dettagli visita la pagina People & Places.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Port_Gellhorn_Postcard_landscape.176c2o75nmcr8.jpg'),
    Topic('gta6-grass', 'GRASSRIVERS', 'Grassrivers amplia la geografia di GTA VI con vaste aree umide e panorami naturali mostrati nei materiali ufficiali.', 'Rockstar ha pubblicato immagini dedicate a questa regione. Non deduciamo da una foto sistemi di caccia o fisica non confermati.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Grassrivers_Postcard_landscape.15-10i39nhex2.jpg'),
    Topic('gta6-ambrosia', 'AMBROSIA', 'Ambrosia e una localit\u00e0 ufficiale di Leonida: l immagine Rockstar evidenzia un paesaggio industriale al tramonto.', 'GTA VI non si limita alle strade di Vice City. Questa scheda mostra una delle tante ambientazioni gi\u00e0 presentate dallo studio.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Ambrosia_Postcard_landscape.0gd~9a41ia-rt.jpg'),
    Topic('gta6-mount', 'MOUNT KALAGA', 'Mount Kalaga National Park \u00e8 tra le aree pubblicate da Rockstar, con boschi, rilievi e corsi d acqua.', 'Un altra faccia di Leonida, lontana dai grattacieli. Restiamo alle localit\u00e0 confermate, senza inventare attivita o equipaggiamento.', 'https://www.rockstargames.com/VI/only-in-leonida', 'https://www.rockstargames.com/VI/_next/static/media/Mount_Kalaga_National_Park_Postcard_landscape.0c1cb4ocq16n3.jpg'),
    Topic('gta6-trailer', 'IL LAUNCH TRAILER', 'Rockstar ha pubblicato il Launch Trailer di GTA VI il 15 ottobre 2026. Contiene nuove scene della storia e della citt\u00e0.', 'La musica e legata a Justice e al brano Flower in a Hurricane. Il video completo e disponibile dalla fonte ufficiale.', 'https://www.rockstargames.com/newswire/article/517572321a549a/watch-the-grand-theft-auto-vi-launch-trailer', 'https://www.rockstargames.com/VI/_next/static/media/GTAVI_Launch_Trailer_poster.0_q-sdrgufc.s.jpg'),
    Topic('gta6-extended', 'AN EXTENDED LOOK', 'L anteprima ufficiale An Extended Look \u00e8 stata pubblicata il 27 agosto 2026 ed \u00e8 composta da filmati catturati in gioco su PS5.', 'Un approfondimento da guardare per ambientazioni e presentazione visiva. Evitiamo di scambiare ogni scena per una funzione confermata.', 'https://www.rockstargames.com/VI/an-extended-look', 'https://www.rockstargames.com/VI/_next/static/media/GTAVI_An_Extended_Look_poster.0ijbsha5fo1te.jpg'),
    Topic('gta6-gallery', 'LAUNCH GALLERY', 'Il 5 novembre Rockstar ha aggiunto nuovi screenshot alla Launch Gallery ufficiale di GTA VI, dedicata a Vice City e Leonida.', 'Screenshot autentici, non ricostruzioni IA. La galleria ufficiale raccoglie immagini di personaggi, citt\u00e0 e paesaggi.', 'https://www.rockstargames.com/newswire/article/39ak81277255o9/explore-the-grand-theft-auto-vi-launch-gallery', 'https://www.rockstargames.com/VI/_next/static/media/Jason_and_Lucia_14.10e7v.06pcm_t.jpg'),
    Topic('gta6-pro', 'GTA VI SU PS5 PRO', 'Rockstar ha presentato il supporto PS5 Pro con miglioramenti di nitidezza tramite PSSR e ombre ray-traced dedicate.', 'Il materiale pubblicato indica un target di 30 FPS: non considerare confermata una modalita 60 FPS in assenza di nuove note ufficiali.', 'https://www.rockstargames.com/newswire/article/89834o94713o21/pre-load-grand-theft-auto-vi-now', 'https://www.rockstargames.com/VI/_next/static/media/Vice_City_27.0d2e~w_r93hmh.jpg'),
    Topic('gta6-radio', 'RADIO E PODCAST', 'Rockstar conferma per GTA VI nuove radio e podcast on demand. E possibile ascoltarli anche a piedi con cuffie connesse allo smartphone.', 'Le emittenti annunciate includono Flash FM e Cocoteo FM. Il sito ufficiale ne presenta musica, stile e programmi.', 'https://www.rockstargames.com/newswire/article/o3982oa93a23k4/the-music-of-grand-theft-auto-vi-in-game-radio-stations', 'https://www.rockstargames.com/VI/_next/static/media/Real_Dimez_landscape.0637akp_a5a_q.jpg'),
    Topic('gta6-album', 'GTA VI: THE ALBUM', 'Rockstar ha annunciato GTA VI: The Album per il 19 novembre 2026: 34 brani originali realizzati con Atlantic Records.', 'La colonna sonora pubblicata come album e distinta dalla partitura originale firmata Justice. Ascolti e dettagli sul Newswire.', 'https://www.rockstargames.com/newswire/article/7599a881942544/announcing-grand-theft-auto-vi-the-album-coming-november-19', 'https://www.rockstargames.com/VI/_next/static/media/The_Album_Cover_Art_landscape.000ifb9a.j-gp.jpg'),
    Topic('gta6-score', 'ORIGINAL SCORE DI JUSTICE', 'La partitura originale di GTA VI \u00e8 composta dal duo Justice. Rockstar la descrive come adattiva alle situazioni di gioco.', 'L album con 30 brani \u00e8 annunciato per l 11 dicembre 2026. E distinto da GTA VI: The Album in arrivo al lancio.', 'https://www.rockstargames.com/newswire/article/39ak8a12395591/grand-theft-auto-vi-original-score-by-justice', 'https://www.rockstargames.com/VI/_next/static/media/Score_CoverArt_1014_1600x1600.0.5dr9slukqhb.jpg'),
    Topic('gta6-editions', 'STANDARD E ULTIMATE', 'Rockstar presenta GTA VI in edizione Standard e Ultimate. Quest ultima include contenuti aggiuntivi dedicati a veicoli, armi e stile.', 'Confronta le dotazioni direttamente sul sito ufficiale prima di acquistare. I contenuti e i bonus variano secondo l edizione.', 'https://www.rockstargames.com/VI/editions', 'https://www.rockstargames.com/VI/_next/static/media/ULTIMATE_EDITION_02.0q-6.nrtf~jj0.jpg'),
    Topic('gta6-vintage', 'BONUS VINTAGE VICE CITY', 'Rockstar indica il Vintage Vice City Pack tra i bonus per gli acquisti idonei effettuati prima del 20 novembre 2026.', 'La raccolta comprende tra l altro una Vapid Stanier del 1955, abiti, acconciature e una decorazione arma esclusiva.', 'https://www.rockstargames.com/newswire/article/5171972o3ak5oa/pre-order-grand-theft-auto-vi-on-june-25', 'https://www.rockstargames.com/VI/_next/static/media/VINTAGE_VICE_CITY_PACK_01.05zaof7o1uz.3.jpg'),
    Topic('gta6-preload', 'PRECARICAMENTO', 'Rockstar ha comunicato l avvio del pre-load digitale di GTA VI nel novembre 2026, in preparazione al lancio del 19 novembre.', 'Per verificare versione e download consulta la console e le comunicazioni ufficiali: non interpretare aggiornamenti PS5 come patch GTA VI.', 'https://www.rockstargames.com/newswire/article/89834o94713o21/pre-load-grand-theft-auto-vi-now', 'https://www.rockstargames.com/VI/_next/static/media/GTAVI_Pre_Load.0h87nx-881hca.jpg'),
)

# Chronology of OFFICIAL source publications, not when the bot discovered them.
# The "people & places" portraits are evergreen editorial cards: grouped with
# Rockstar's Trailer 2 reveal, but their tweets do NOT claim a precise article date.
SOURCE_DATES = {
    'gta6-overview': '2025-11-06',
    'gta6-jason': '2025-05-06', 'gta6-lucia': '2025-05-06',
    'gta6-pair': '2025-05-06', 'gta6-vice': '2025-05-06',
    'gta6-keys': '2025-05-06', 'gta6-port': '2025-05-06',
    'gta6-grass': '2025-05-06', 'gta6-ambrosia': '2025-05-06',
    'gta6-mount': '2025-05-06',
    'gta6-editions': '2026-06-18',
    'gta6-vintage': '2026-06-24',
    'gta6-extended': '2026-08-27',
    'gta6-album': '2026-09-17',
    'gta6-radio': '2026-10-08',
    'gta6-trailer': '2026-10-15',
    'gta6-score': '2026-10-29',
    'gta6-gallery': '2026-11-05',
    'gta6-pro': '2026-11-10',
    'gta6-preload': '2026-11-10',
    'gta6-trailer1': '2023-12-05',
    'gta6-trailer2': '2025-05-06',
    'gta6-preload-faq': '2026-11-03',
    'gta6-festival': '2026-11-09',
    'ps5-firmware-1423': '2026-11-17',
}
EVERGREEN_TOPICS = {
    'gta6-jason', 'gta6-lucia', 'gta6-pair', 'gta6-vice',
    'gta6-keys', 'gta6-port', 'gta6-grass', 'gta6-ambrosia',
    'gta6-mount',
}
ADDITIONAL_TOPICS = (
    Topic('gta6-trailer1', 'PRIMO TRAILER 2023',
          'Il 5 dicembre 2023 Rockstar pubblicò il primo trailer di GTA VI e presentò Vice City nello stato di Leonida.',
          'Questa è la prima tappa della nostra cronologia ufficiale. La data di lancio mostrata allora è storica: oggi Rockstar conferma il 19 novembre 2026.',
          'https://www.rockstargames.com/newswire/article/8978kok9385a82/grand-theft-auto-vi-watch-trailer-1-now'),
    Topic('gta6-trailer2', 'TRAILER 2 DEL 2025',
          'Il 6 maggio 2025 Rockstar pubblicò il trailer 2: Jason e Lucia, nuovi scorci di Vice City e la premessa della storia.',
          'Il filmato fu catturato nel gioco su PS5. Il sito Rockstar raccoglie il trailer, le biografie e i luoghi ufficialmente presentati.',
          'https://www.rockstargames.com/newswire/article/3928aaa9471o3a/grand-theft-auto-vi-watch-trailer-2-now'),
    Topic('gta6-preload-faq', 'PRELOAD ANNUNCIATO',
          'Il 3 novembre 2026 Rockstar confermò che il pre-load digitale di GTA VI sarebbe iniziato il 10 novembre su PS5.',
          'La FAQ distingue il pre-load su PS5 e Xbox. Non confondiamo la dimensione del download con patch o aggiornamenti di sistema.',
          'https://support.rockstargames.com/articles/7nPqOA2uCbpEQHXx7KVrYd/grand-theft-auto-vi-pre-load-faq'),
    Topic('gta6-festival', 'GTA VI: THE FESTIVAL',
          'Il 9 novembre 2026 Rockstar annunciò il festival dedicato alla musica di GTA VI, previsto a Miami il 21 novembre.',
          'È un evento celebrativo, non un annuncio di DLC o di GTA Online. Dettagli e ospiti sono riportati da Rockstar nel Newswire.',
          'https://www.rockstargames.com/newswire/article/o39o87a435a25a/grand-theft-auto-vi-the-festival'),
    Topic('ps5-firmware-1423', 'FIRMWARE PS5 E PS5 PRO 14.23',
          'Il 17 novembre 2026 e stato distribuito il software di sistema 26.07-14.23.00 per PS5 e PS5 Pro: note di rilascio focalizzate sulla sicurezza.',
          'Non e una patch di GTA VI: non sono annunciati FPS maggiori, miglioramenti PSSR o nuove funzioni di gioco. Controlla Impostazioni > Sistema > Software di sistema.',
          'https://www.playstation.com/en-us/support/hardware/ps5/system-software-info/'),
)

# Keep a stable order for equally dated evergreen cards, and never fabricate
# their individual first publication date.
TOPICS = tuple(sorted((*TOPICS, *ADDITIONAL_TOPICS),
                      key=lambda t: (SOURCE_DATES[t.key],
                                     0 if t.key in {'gta6-trailer1', 'gta6-trailer2'} else 1)))


def chronology_label(topic):
    if topic.key in EVERGREEN_TOPICS:
        return 'ARCHIVIO | Scheda Rockstar'
    stamp = datetime.strptime(SOURCE_DATES[topic.key], '%Y-%m-%d')
    return 'ANNUNCIO DEL ' + stamp.strftime('%d/%m/%Y')


def prepare_slots(now, count):
    """Schedule in UTC on 18 Nov 2026, with 80 min margin before X deadline.

    These are Buffer dueAt timestamps, not proof of X publication.
    A late workflow fails closed instead of scheduling posts past the cutoff.
    """
    if now.tzinfo is None:
        raise ValueError('Datetime must have an explicit timezone')
    now_utc = now.astimezone(timezone.utc)
    if now_utc.date().isoformat() != ARCHIVE_DAY_UTC:
        raise RuntimeError('Scadenza: archivio consentito soltanto il 18/11/2026 UTC')
    if count < 1:
        return []
    first = first_slot(now_utc)
    if first >= BUFFER_LAST_SCHEDULED_UTC:
        raise RuntimeError('Scadenza: ultima programmazione Buffer gia superata')
    if count == 1:
        return [first]
    available_minutes = int((BUFFER_LAST_SCHEDULED_UTC - first).total_seconds() // 60)
    spacing = min(SPACING_MINUTES, available_minutes // (count - 1))
    if spacing < MIN_SPACING_MINUTES:
        raise RuntimeError('Poche ore residue: impossibile finire prima del limite senza raffiche')
    slots = [first + timedelta(minutes=i * spacing) for i in range(count)]
    if slots[-1] > BUFFER_LAST_SCHEDULED_UTC:
        raise RuntimeError('Scadenza: calendario oltre le 06:30 GMT, lotto bloccato')
    return slots


def make_thread(topic):
    sony = source_family(topic.source_url) == 'sony'
    brand = 'PS5 / PS5 Pro' if sony else 'GTA VI'
    hashtag = '#PS5 #PS5Pro' if sony else '#GTAVI'
    credit = 'Sony' if sony else 'Rockstar'
    tail_tag = '#PlayStation' if sony else '#GTA6'
    first = f"1/2 \U0001f3ae {brand} | {topic.heading}\n{chronology_label(topic)}\n\n{topic.summary}\n\n{hashtag}"
    second = f"2/2 \U0001f4f0 {topic.detail}\n\nFonte {credit}: {topic.source_url}\n{tail_tag}"
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


def media_identity(url):
    """Ignore image-delivery query strings, avoiding size-variant duplicates."""
    from urllib.parse import urlsplit, unquote
    parsed = urlsplit(str(url))
    return (parsed.hostname or '').lower() + unquote(parsed.path).lower()


def unique_media(topic, used, resolver=official_media_for_event, probe=_probe_image):
    """Only approved publisher media; no duplicate visuals in archive batch."""
    family = source_family(topic.source_url)
    if family not in {'rockstar', 'sony'}:
        raise OfficialMediaUnavailable('non_official_source')
    event = {'source_url': topic.source_url, 'trust': 'official',
             'title': ('PS5 update ' if family == 'sony' else 'GTA VI ') + topic.heading,
             'game': 'PlayStation' if family == 'sony' else 'GTA VI'}
    if topic.official_image_url and media_identity(topic.official_image_url) not in used:
        event['official_image_url'] = topic.official_image_url
        try:
            photo = resolver(event)
            if (photo.kind == 'editorial_image' and
                    approved_image_url(photo.url, family) and
                    media_identity(photo.url) == media_identity(topic.official_image_url)):
                return photo
        except OfficialMediaUnavailable:
            pass
    event.pop('official_image_url', None)
    try:
        photo = resolver(event)
        if (photo.kind != 'official_logo' and media_identity(photo.url) not in used
                and approved_image_url(photo.url, family)):
            return photo
    except OfficialMediaUnavailable:
        pass
    if family == 'sony':
        if (media_identity(PLAYSTATION_LOGO) not in used and
                probe(PLAYSTATION_LOGO, 'sony', logo=True)):
            return OfficialMediaChoice(PLAYSTATION_LOGO, 'official_logo', topic.source_url)
        raise OfficialMediaUnavailable('no_unused_verified_sony_photo_or_logo')
    for logo in USER_LOGO_FALLBACKS:
        if (media_identity(logo) not in used and approved_image_url(logo, 'rockstar')
                and probe(logo, 'rockstar')):
            return OfficialMediaChoice(logo, 'official_logo', topic.source_url)
    raise OfficialMediaUnavailable('no_unused_verified_rockstar_image')


def first_slot(now):
    """12-minute preparation, aligned to the next five-minute Europe/Berlin slot."""
    local = (now + timedelta(minutes=START_DELAY_MINUTES)).astimezone(ZoneInfo('Europe/Berlin'))
    offset = (5 - (local.minute % 5)) % 5
    if local.second or local.microsecond:
        offset = offset or 5
    first = (local + timedelta(minutes=offset)).replace(second=0, microsecond=0)
    return first.astimezone(timezone.utc)


def audit_delivery(*, client=None, state_path=JOURNAL, now=None):
    """Read-only Buffer delivery audit. Does NOT republish or change queue.

    Buffer status=sent is stronger than scheduled, but the final source of truth
    remains the actual thread visible on X. A sent status with no X link is
    reported for manual verification, rather than falsely claiming success.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Audit datetime must have timezone')
    state = load_journal(state_path)
    if client is None:
        client = BufferClient(expected_username=EXPECTED_USERNAME)
    client.verify_destination()
    errors, sent, x_links = [], 0, 0
    for topic in TOPICS:
        item = state['items'].get(topic.key)
        if not item or item.get('status') != 'scheduled' or not item.get('buffer_id'):
            errors.append(f"{topic.key}: missing_or_unscheduled")
            print(f"NOT_SENT {topic.key}: missing_or_unscheduled")
            continue
        try:
            delivery = client.delivery_status(item['buffer_id'])
        except Exception as exc:
            errors.append(f"{topic.key}: Buffer status unavailable ({type(exc).__name__})")
            print(f"UNVERIFIED {topic.key}: {type(exc).__name__}")
            continue
        if delivery.status != 'sent':
            errors.append(f"{topic.key}: status={delivery.status}")
            print(f"NOT_SENT {topic.key}: {delivery.status} | BufferID={item['buffer_id']}")
            continue
        sent += 1
        url = str(delivery.external_url or '')
        valid_x = url.startswith(('https://x.com/', 'https://twitter.com/'))
        x_links += int(valid_x)
        print(f"BUFFER_SENT {topic.key}: {url if valid_x else 'no X permalink; verify on X'}")
    print(f"DELIVERY AUDIT: sent_by_Buffer={sent}/{len(TOPICS)}; X_links={x_links}/{len(TOPICS)}; "
          f"asof_UTC={now.astimezone(timezone.utc).isoformat()}")
    if errors:
        raise RuntimeError(f"Buffer has not confirmed all historical threads delivered: {len(errors)} unresolved; see logs")
    if now.astimezone(timezone.utc) >= X_PUBLICATION_DEADLINE_UTC:
        print('X DEADLINE REACHED: verify real post URLs on X, since Buffer sent alone is not conclusive.')
    return sent


def run(*, mode="preview", client=None, media_resolver=official_media_for_event,
        now=None, state_path=JOURNAL, checkpoint=git_checkpoint, environ=None,
        max_threads=MAX_INITIAL_THREADS, probe=_probe_image):
    env = os.environ if environ is None else environ
    if mode not in {"preview", "schedule", "audit"}:
        raise ValueError("Mode must be preview, schedule or audit")
    if mode == "audit":
        return audit_delivery(client=client, state_path=state_path, now=now)
    state = load_journal(state_path)
    topics = list(TOPICS) if max_threads is None else list(TOPICS)[:max_threads]
    if len({t.key for t in topics}) != len(topics):
        raise RuntimeError("Duplicate topic IDs")
    if any(t.key not in SOURCE_DATES for t in topics):
        raise RuntimeError('Topic missing chronology source date')
    if [SOURCE_DATES[t.key] for t in topics] != sorted(SOURCE_DATES[t.key] for t in topics):
        raise RuntimeError('Editorial topics out of chronological order')
    for topic in topics:
        make_thread(topic)
    if mode == "preview":
        print("PREVIEW v11 ONLY: 0 Buffer requests, 0 posts, 0 journal changes")
        test_now = now or datetime.now(timezone.utc)
        try:
            slots = prepare_slots(test_now, len(topics))
            print("Finestra simulata: " + slots[0].astimezone(ZoneInfo("Europe/Berlin")).isoformat() + " -> " + slots[-1].astimezone(ZoneInfo("Europe/Berlin")).isoformat())
        except RuntimeError as exc:
            print("Finestra non disponibile: " + str(exc))
        print("25 schede cronologiche (incl. Sony 17/11): Buffer massimo 18/11 06:30 GMT (07:30 CET); X deadline 18/11 07:50 GMT (08:50 CET).")
        for i, topic in enumerate(topics, 1):
            status = state["items"].get(topic.key, {}).get("status", "new")
            print(f"{i:02d} [{status}] {SOURCE_DATES[topic.key]} {topic.heading} | {chronology_label(topic)} | URL: {topic.source_url}")
        return 0
    if (env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or
            env.get("GITHUB_REF") != "refs/heads/main" or
            env.get("GTA6_BOOTSTRAP_QUEUE") != "YES_QUEUE" or
            env.get("CONFIRM_BUFFER_QUEUE_RESET") != "CONFIRMED_EMPTY_AND_PAUSED"):
        raise RuntimeError("Scheduling requires explicit manual confirmation on main")
    if str(env.get("AUTO_PUBLISH", "false")).lower() != "false":
        raise RuntimeError("Set AUTO_PUBLISH=false before bootstrap scheduling")
    if any(rec.get("status") in {"sending", "review"} for rec in state["items"].values()):
        raise RuntimeError("Previous Buffer outcome uncertain; review before retry")
    if client is None:
        client = BufferClient(expected_username=EXPECTED_USERNAME)
    channel = client.verify_destination()
    if channel.get("isQueuePaused") is not True:
        raise RuntimeError("Buffer Queue is not paused; refuse to schedule")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware datetime required")
    now = now.astimezone(timezone.utc)
    used = {media_identity(rec["image_url"]) for rec in state["items"].values()
            if rec.get("image_url") and rec.get("status") in {"scheduled", "sending", "review"}}
    # On partial re-runs retain the original chronological schedule where possible.
    # Previously skipped topics are closed out, not placed after a later story.
    pending_topics = [t for t in topics if t.key not in state['items']]
    if pending_topics and any(rec.get('status') == 'scheduled' for rec in state['items'].values()):
        raise RuntimeError('Lotto parziale: verifica gli orari gia programmati prima di completare l archivio')
    planned_slots = prepare_slots(now, len(pending_topics)) if pending_topics else []
    scheduled = 0
    next_slot = 0
    for topic in topics:
        if topic.key in state["items"]:
            print(f"SKIP {topic.key}: journal entry exists")
            continue
        try:
            photo = unique_media(topic, used, resolver=media_resolver, probe=probe)
        except OfficialMediaUnavailable as exc:
            print(f"SKIP {topic.key}: {exc}")
            state['items'][topic.key] = {'status': 'skipped_missing_image', 'source': topic.source_url}
            write_journal(state, state_path)
            checkpoint(state_path)
            continue
        ident = media_identity(photo.url)
        if ident in used:
            raise RuntimeError("Image uniqueness failure")
        # Occupy the next slot only on success. Every request has its own checkpoint.
        due = planned_slots[next_slot]
        next_slot += 1
        state["items"][topic.key] = {"status": "sending", "source": topic.source_url,
                  "image_kind": photo.kind, "image_url": photo.url, "due_at": due.isoformat()}
        write_journal(state, state_path)
        checkpoint(state_path)
        try:
            delivery = schedule_thread(client, make_thread(topic), photo.url, due)
        except Exception:
            state["items"][topic.key]["status"] = "review"
            write_journal(state, state_path)
            checkpoint(state_path)
            raise
        state["items"][topic.key].update(status="scheduled", buffer_id=delivery.post_id)
        write_journal(state, state_path)
        checkpoint(state_path)
        used.add(ident)
        scheduled += 1
        local = due.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d/%m/%Y %H:%M %Z")
        print(f"SCHEDULED {topic.key}: id={delivery.post_id}; media={photo.kind}; when={local}")
    print(f"Bootstrap v11: {scheduled} scheduled; {len(used)} unique media assets; "
          f"{len(topics)} topics checked in historical order")
    return scheduled


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preview", "schedule", "audit"), default="preview")
    args = parser.parse_args()
    run(mode=args.mode)
