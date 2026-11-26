"""Publisher Buffer senza API X diretta.

Fonti ufficiali consultate il 17/11/2026:
https://buffer.com/pricing
https://developers.buffer.com/guides/api-limits.html
https://developers.buffer.com/types/CreatePostInput.md
https://developers.buffer.com/types/ShareMode.md
https://developers.buffer.com/types/PostStatus.md
https://developers.buffer.com/guides/hosting-media.md

Il piano Free include l'API, con quote: 150 richieste/15 min, 600/24 ore,
1.000/canale/30 giorni fino a 3.000. Non sono 1.000 post: anche le letture
consumano richieste. Questo client non fa polling automatico né auto-upgrade.
La documentazione Buffer non promette disponibilità gratuita illimitata.

Una risposta accettata non significa post pubblicato: publish ritorna l'ID
Buffer solo quando status=sent. Per gli invii accettati ma ancora in lavorazione
solleva BufferPending con post_id, da conservare e verificare tramite
delivery_status senza ripetere createPost. L'ID Buffer NON è un ID post X.

Buffer non dispone di un endpoint per caricare file multimediali. Un'immagine
deve avere un URL HTTPS pubblico e stabile; per file locali si può iniettare
media_uploader(Path)->URL. Non viene effettuato alcun upload implicito.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests

ENDPOINT = "https://api.buffer.com"

DESTINATION_QUERY = """query Destination($id: ChannelId!) {
  channel(input: {id: $id}) {
    id name service isDisconnected isLocked isQueuePaused externalLink
  }
}"""
CREATE_MUTATION = """mutation Publish($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status channelId externalLink } }
    ... on MutationError { message }
  }
}"""
STATUS_QUERY = """query Delivery($id: PostId!) {
  post(input: {id: $id}) { id status channelId externalLink }
}"""
ORGANIZATIONS_QUERY = """query Organizations {
  account { organizations { id name } }
}"""
CHANNELS_QUERY = """query Channels($organizationId: OrganizationId!) {
  channels(input: {organizationId: $organizationId}) {
    id name service isDisconnected isLocked externalLink
  }
}"""


class BufferConfigurationError(ValueError):
    """Configurazione mancante o destinazione diversa da quella attesa."""


class BufferMediaError(ValueError):
    """Media privo di un URL pubblico; nessun post è stato creato."""


class BufferAPIError(RuntimeError):
    def __init__(self, message, *, status=0, retry_after=0, outcome_unknown=False, post_id=None):
        self.status = status
        self.retry_after = retry_after
        self.outcome_unknown = outcome_unknown
        self.post_id = post_id
        super().__init__(message)


class BufferPending(BufferAPIError):
    """Invio accettato. Non richiamare publish: verificare lo stesso post_id."""

    def __init__(self, post_id, delivery_state):
        self.delivery_state = delivery_state
        super().__init__("Buffer ha accettato il post, consegna da verificare",
                         status=202, retry_after=60, outcome_unknown=False, post_id=post_id)


class BufferDeliveryFailed(BufferAPIError):
    """Buffer ha creato il record ma la pubblicazione è fallita."""

    def __init__(self, post_id):
        super().__init__("Pubblicazione Buffer fallita: controllare il post nella dashboard",
                         status=409, outcome_unknown=False, post_id=post_id)


@dataclass(frozen=True)
class Delivery:
    post_id: str
    status: str
    external_url: str | None = None


def _required(name, value):
    value = (value if value is not None else os.getenv(name, "")).strip()
    if not value:
        raise BufferConfigurationError(f"Configura {name}")
    return value


def _retry_after(response):
    try:
        explicit = float(response.headers.get("Retry-After", 0))
    except (TypeError, ValueError):
        explicit = 0
    # RateLimit contiene una policy per finestra, ad es. "150-in-15min";r=0;t=420.
    # Si aspetta solo la finestra esaurita, non ogni finestra ancora disponibile.
    exhausted = []
    for policy in response.headers.get("RateLimit", "").split(","):
        if re.search(r"(?:^|;)\s*r=0(?:;|$)", policy):
            match = re.search(r"(?:^|;)\s*t=(\d+)", policy)
            if match:
                exhausted.append(float(match.group(1)))
    return max([explicit, *exhausted, 60])


def _channel_handle(channel):
    """Preferisce l'URL profilo al nome visibile restituito da Buffer.

    Channel.externalLink è documentato come URL del profilo. Channel.name è
    descritto come handle/username nella reference, ma non è necessariamente
    distinguibile da un display name: si usa solo quando il link manca ed è
    sintatticamente un handle X. Un link presente ma non interpretabile non
    viene sostituito con il nome, per non nascondere una destinazione diversa.
    https://developers.buffer.com/types/Channel.md
    """
    link = channel.get("externalLink")
    if link:
        try:
            url = urlsplit(str(link))
        except ValueError:
            return None
        if (url.scheme not in {"http", "https"} or url.username or url.password
                or url.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}):
            return None
        segments = [segment for segment in url.path.split("/") if segment]
        if len(segments) != 1:
            return None
        candidate = segments[0]
        if candidate.casefold() in {"home", "explore", "notifications", "messages", "settings", "search", "intent", "i"}:
            return None
    else:
        candidate = str(channel.get("name", "")).strip().lstrip("@")
    return candidate.casefold() if re.fullmatch(r"[A-Za-z0-9_]{1,15}", candidate) else None


class BufferClient:
    def __init__(self, api_key=None, channel_id=None, expected_username=None,
                 *, session=None, media_uploader=None, request_guard=None,
                 timeout=30, require_media=True):
        self.api_key = _required("BUFFER_API_KEY", api_key)
        self.channel_id = (channel_id if channel_id is not None else os.getenv("BUFFER_CHANNEL_ID", "")).strip()
        if expected_username is None:
            expected_username = os.getenv("BUFFER_EXPECTED_USERNAME") or os.getenv("X_EXPECTED_USERNAME", "")
        self.expected_username = expected_username.strip().lstrip("@").casefold()
        self.session = session if session is not None else requests.Session()
        self.media_uploader = media_uploader
        # Production default: every X post and thread MUST carry an image.
        # The independent editorial gate checks provenance and deduplication;
        # this is a final fail-closed check against alternative text-only paths.
        self.require_media = bool(require_media)
        # Facoltativo: contabilizzazione persistente/limite locale gestito dal chiamante.
        # Chiamato prima di ogni richiesta, mai in un retry nascosto.
        self.request_guard = request_guard
        self.timeout = timeout
        self.destination = None
        self.last_delivery = None

    def _graphql(self, query, variables, *, mutation=False):
        # Final barrier for every production createPost, including legacy
        # scheduled mutations that bypass publish(). No text-only replies.
        if mutation and "createPost" in query and (self.expected_username == "xfederiko11" or os.getenv("GTA6_REQUIRE_ALL_POST_PHOTOS") == "true"):
            value = variables.get("input") or {}
            thread = ((value.get("metadata") or {}).get("twitter") or {}).get("thread")
            messages = thread if thread is not None else [value]
            def has_image(message):
                return any(isinstance(asset, dict)
                           and isinstance(asset.get("image"), dict)
                           and isinstance(asset["image"].get("url"), str)
                           and asset["image"]["url"].startswith("https://")
                           for asset in (message.get("assets") or []))
            if not messages or not all(isinstance(m, dict) and has_image(m) for m in messages):
                raise BufferAPIError("Invio bloccato: fotografia obbligatoria in ogni messaggio X",
                                     status=400, outcome_unknown=False)
            from photo_rights_v1 import message_attachments_allowed
            if not all(message_attachments_allowed(message) for message in messages):
                raise BufferAPIError("Invio bloccato: diritti di riutilizzo della fotografia non documentati",
                                     status=400, outcome_unknown=False)
        if self.request_guard is not None:
            self.request_guard()
        try:
            response = self.session.post(
                ENDPOINT, headers={"Authorization": "Bearer " + self.api_key},
                json={"query": query, "variables": variables}, timeout=self.timeout,
            )
        except requests.RequestException:
            # Il server può avere creato il post prima della perdita della risposta.
            raise BufferAPIError("Connessione Buffer non completata", outcome_unknown=mutation) from None
        if not 200 <= response.status_code < 300:
            raise BufferAPIError(
                f"Buffer: HTTP {response.status_code}", status=response.status_code,
                retry_after=_retry_after(response) if response.status_code == 429 else 0,
                outcome_unknown=mutation and response.status_code >= 500,
            )
        try:
            body = response.json()
        except ValueError:
            raise BufferAPIError("Risposta Buffer non leggibile", outcome_unknown=mutation) from None
        if not isinstance(body, dict) or body.get("errors") or not isinstance(body.get("data"), dict):
            # Non mostrare messaggi remoti, payload o token nei log.
            raise BufferAPIError("Buffer ha restituito un errore GraphQL o dati parziali",
                                 outcome_unknown=mutation)
        return body["data"]

    def verify_destination(self):
        _required("BUFFER_CHANNEL_ID", self.channel_id)
        data = self._graphql(DESTINATION_QUERY, {"id": self.channel_id})
        channel = data.get("channel")
        if not isinstance(channel, dict) or str(channel.get("id")) != self.channel_id:
            raise BufferConfigurationError("Canale Buffer non trovato")
        if channel.get("service") != "twitter":
            raise BufferConfigurationError("Il canale Buffer selezionato non è un account X")
        if channel.get("isDisconnected") or channel.get("isLocked"):
            raise BufferConfigurationError("Il canale X in Buffer è scollegato o bloccato")
        if self.expected_username:
            actual_username = _channel_handle(channel)
            if actual_username is None:
                raise BufferConfigurationError("Impossibile verificare l'handle X del canale Buffer: controllare il link del profilo")
            if actual_username != self.expected_username:
                raise BufferConfigurationError("Il canale Buffer appartiene a un account diverso da quello atteso")
        self.destination = channel
        return channel

    def list_channels(self, organization_id=None):
        """Recupera gli ID reali senza crearli o dedurli; non richiede channel_id.

        Usa una lettura per organizzazione, più la lista iniziale delle
        organizzazioni quando non viene fornito organization_id.
        """
        if organization_id is None:
            data = self._graphql(ORGANIZATIONS_QUERY, {})
            organizations = (data.get("account") or {}).get("organizations")
            if not isinstance(organizations, list):
                raise BufferAPIError("Elenco organizzazioni Buffer non leggibile")
        else:
            organizations = [{"id": str(organization_id), "name": ""}]
        channels = []
        for organization in organizations:
            if not isinstance(organization, dict) or not organization.get("id"):
                raise BufferAPIError("Organizzazione Buffer senza identificativo")
            data = self._graphql(CHANNELS_QUERY, {"organizationId": organization["id"]})
            items = data.get("channels")
            if not isinstance(items, list):
                raise BufferAPIError("Elenco canali Buffer non leggibile")
            for channel in items:
                if not isinstance(channel, dict) or not channel.get("id"):
                    raise BufferAPIError("Canale Buffer senza identificativo")
                channels.append({**channel, "organization_id": organization["id"],
                                 "organization_name": organization.get("name", "")})
        return channels

    @staticmethod
    def _media_url(value):
        value = str(value)
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise BufferMediaError("L'immagine richiede un URL HTTPS pubblico senza credenziali")
        return value

    def _assets(self, media_path):
        if media_path is None:
            return []
        if isinstance(media_path, str) and media_path.startswith("https://"):
            url = self._media_url(media_path)
        else:
            path = Path(media_path)
            if not path.is_file():
                raise BufferMediaError("File immagine non trovato")
            if self.media_uploader is None:
                raise BufferMediaError("Buffer richiede un URL immagine pubblico: configura prima l'hosting delle card")
            url = self._media_url(self.media_uploader(path))
        return [{"image": {"url": url}}]

    def _delivery(self, post):
        if not isinstance(post, dict) or not post.get("id") or not post.get("status"):
            raise BufferAPIError("Consegna Buffer senza ID o stato", outcome_unknown=True)
        if post.get("channelId") and post["channelId"] != self.channel_id:
            raise BufferAPIError("Post Buffer associato a una destinazione diversa", outcome_unknown=True,
                                 post_id=str(post["id"]))
        result = Delivery(str(post["id"]), str(post["status"]), post.get("externalLink"))
        self.last_delivery = result
        return result

    def publish(self, text, media_path=None, media_url=None):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Il post non può essere vuoto")
        if media_path is not None and media_url is not None:
            raise BufferMediaError("Indica media_path oppure media_url, non entrambi")
        # Valida i media prima di qualsiasi creazione di post.
        assets = [{"image": {"url": self._media_url(media_url)}}] if media_url is not None else self._assets(media_path)
        if self.require_media and not assets:
            raise BufferMediaError("Ogni pubblicazione X deve includere un'immagine pubblica verificata")
        if self.destination is None:
            self.verify_destination()
        data = self._graphql(CREATE_MUTATION, {"input": {
            "text": text, "channelId": self.channel_id, "schedulingType": "automatic",
            "mode": "shareNow", "assets": assets,
        }}, mutation=True)
        result = data.get("createPost")
        if not isinstance(result, dict):
            raise BufferAPIError("Esito creazione Buffer mancante", outcome_unknown=True)
        if not result.get("post"):
            # MutationError è un rifiuto documentato, non un invio dall'esito incerto.
            if result.get("message"):
                raise BufferAPIError("Buffer ha rifiutato il post: verificare limiti, media e connessione del canale",
                                     status=400, outcome_unknown=False)
            raise BufferAPIError("Esito creazione Buffer incompleto", outcome_unknown=True)
        delivery = self._delivery(result["post"])
        if delivery.status == "error":
            raise BufferDeliveryFailed(delivery.post_id)
        if delivery.status != "sent":
            raise BufferPending(delivery.post_id, delivery.status)
        return delivery.post_id

    def publish_gallery(self, text, image_urls):
        """Publish one X post carrying 2-4 distinct public HTTPS images.

        Caller MUST verify public image provenance and reuse restrictions.
        Buffer media URLs must remain accessible until X has fetched them.
        """
        from editorial_seo_v135 import x_weight
        if not isinstance(text, str) or not text.strip() or x_weight(text) > 280:
            raise ValueError("Didascalia della galleria non valida")
        if not isinstance(image_urls, (list, tuple)) or not 2 <= len(image_urls) <= 4:
            raise BufferMediaError("La galleria deve contenere da 2 a 4 immagini")
        if len(set(image_urls)) != len(image_urls):
            raise BufferMediaError("Non ripetere la stessa immagine nella galleria")
        assets = [{"image": {"url": self._media_url(url)}} for url in image_urls]
        if self.destination is None:
            self.verify_destination()
        data = self._graphql(CREATE_MUTATION, {"input": {
            "text": text, "channelId": self.channel_id, "schedulingType": "automatic",
            "mode": "shareNow", "assets": assets,
        }}, mutation=True)
        result = data.get("createPost")
        if not isinstance(result, dict):
            raise BufferAPIError("Esito galleria Buffer mancante", outcome_unknown=True)
        if not result.get("post"):
            if result.get("message"):
                raise BufferAPIError("Buffer ha rifiutato la galleria", status=400, outcome_unknown=False)
            raise BufferAPIError("Esito galleria incompleto", outcome_unknown=True)
        delivery = self._delivery(result["post"])
        if delivery.status == "error":
            raise BufferDeliveryFailed(delivery.post_id)
        if delivery.status != "sent":
            raise BufferPending(delivery.post_id, delivery.status)
        return delivery.post_id

    def publish_thread(self, posts, *, media_url=None):
        """Invia un thread X come UN SOLO record Buffer.

        Ciascun post ha il proprio limite caratteri. Non esegue retry
        automatici se l'esito di createPost non e' noto.
        """
        if self.require_media and not media_url:
            raise BufferMediaError("Il primo messaggio del thread X deve avere una fotografia")
        from presentation import _post_weight
        if not isinstance(posts, (list, tuple)) or not 2 <= len(posts) <= 5:
            raise ValueError("Il thread deve contenere da 2 a 5 post")
        if any(not isinstance(t, str) or not t.strip() or _post_weight(t) > 280 for t in posts):
            raise ValueError("Ogni post del thread deve essere testo valido entro 280 caratteri pesati")
        if media_url is not None:
            # A photo attached to the first X post consumes extra text budget.
            # Keep 45 characters spare for the attachment and Unicode counting.
            from editorial_seo_v135 import x_weight
            if x_weight(posts[0]) > 235:
                raise ValueError("Il post con foto supera il budget prudente di 235 caratteri")
        if self.destination is None:
            self.verify_destination()
        items = [{"text": t, "assets": []} for t in posts]
        if media_url is not None:
            items[0]["assets"] = [{"image": {"url": self._media_url(media_url)}}]
        data = self._graphql(CREATE_MUTATION, {"input": {
            "text": posts[0], "channelId": self.channel_id, "schedulingType": "automatic",
            "mode": "shareNow", "assets": [], "metadata": {"twitter": {"thread": items}},
        }}, mutation=True)
        result = data.get("createPost")
        if not isinstance(result, dict):
            raise BufferAPIError("Esito creazione thread mancante", outcome_unknown=True)
        if not result.get("post"):
            if result.get("message"):
                raise BufferAPIError("Buffer ha rifiutato il thread: controllare canale, limiti e formato",
                                     status=400, outcome_unknown=False)
            raise BufferAPIError("Esito creazione thread incompleto", outcome_unknown=True)
        delivery = self._delivery(result["post"])
        if delivery.status == "error":
            raise BufferDeliveryFailed(delivery.post_id)
        if delivery.status != "sent":
            raise BufferPending(delivery.post_id, delivery.status)
        return delivery.post_id

    def create_draft_thread(self, posts, *, media_url):
        """Create an X thread as a Buffer DRAFT ONLY; never schedule or publish.

        Used exclusively by the separate manual smoke-test workflow. It is not
        called by the automated news delivery path. Never retry a write with an
        unknown outcome: Buffer may have accepted the original request.
        """
        from presentation import _post_weight
        if not isinstance(posts, (list, tuple)) or not 2 <= len(posts) <= 5:
            raise ValueError("Il test richiede un thread da 2 a 5 post")
        if any(not isinstance(text, str) or not text.strip() or _post_weight(text) > 280 for text in posts):
            raise ValueError("Ogni post deve restare entro 280 caratteri pesati")
        if not media_url:
            raise BufferMediaError("Il test richiede un'immagine ufficiale")
        url = self._media_url(media_url)
        if self.destination is None:
            self.verify_destination()

        thread_items = [{"text": text, "assets": []} for text in posts]
        thread_items[0]["assets"] = [{"image": {"url": url}}]
        draft_input = {
            "channelId": self.channel_id,
            "text": posts[0],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "saveToDraft": True,
            "assets": [],
            "metadata": {"twitter": {"thread": thread_items}},
        }
        data = self._graphql(CREATE_MUTATION, {"input": draft_input}, mutation=True)
        result = data.get("createPost")
        if not isinstance(result, dict):
            raise BufferAPIError("Risposta Buffer al test non valida", outcome_unknown=True)
        if not result.get("post"):
            if result.get("message"):
                raise BufferAPIError("Buffer ha rifiutato la bozza tecnica", status=400)
            raise BufferAPIError("Esito test Buffer incompleto", outcome_unknown=True)
        delivery = self._delivery(result["post"])
        if delivery.status != "draft":
            # Do not claim that the request was safe if Buffer reports any other
            # status. Manual inspection is mandatory; do not retry blindly.
            raise BufferAPIError("Stato inatteso: verifica subito la dashboard Buffer",
                                 outcome_unknown=True, post_id=delivery.post_id)
        return delivery.post_id

    def delivery_status(self, post_id):
        """Una sola lettura: non ricrea il post e non esegue polling nascosto."""
        data = self._graphql(STATUS_QUERY, {"id": str(post_id)})
        return self._delivery(data.get("post"))
