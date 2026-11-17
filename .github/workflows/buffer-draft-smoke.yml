"""Manual draft-only end-to-end check for Federiko GTA News Center.

Create one Buffer draft with a real Rockstar image. No news scraping, no
scheduling and no publishing. This file is NOT invoked by the normal monitor.
"""

import os

from buffer_publisher import BufferClient
from official_media import _probe_image

# Real official Rockstar asset previously previewed successfully in Buffer.
ROCKSTAR_IMAGE = (
    "https://www.rockstargames.com/VI/_next/static/media/"
    "Jason_Lucia_Rooftop_landscape.0c6p5do~-8~7..jpg"
)

DRAFT_THREAD = [
    "1/2 🎮 GTA VI NEWS CENTER\n\nTest tecnico con artwork Rockstar: Jason e Lucia.\n"
    "Bozza di verifica: NON pubblicare su X.",
    "2/2 📰 TEST BUFFER API\n\nVerifica del thread con immagine autentica. "
    "Non è una nuova notizia.\n\nFonte: rockstargames.com/VI/media\n\n#GTAVI #GTA6",
]


def run(*, client=None, image_check=None, environ=None):
    """Hard-stop unless explicitly invoked by the dedicated manual workflow."""
    env = os.environ if environ is None else environ
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or env.get("BUFFER_DRAFT_SMOKE_ONLY") != "1":
        raise RuntimeError("Il test richiede un avvio manuale del workflow dedicato")
    if env.get("AUTO_PUBLISH", "false").lower() != "false":
        raise RuntimeError("Imposta AUTO_PUBLISH=false prima del test")
    check = _probe_image if image_check is None else image_check
    if not check(ROCKSTAR_IMAGE, "rockstar"):
        raise RuntimeError("Artwork Rockstar non raggiungibile: nessuna bozza creata")
    if client is None:
        client = BufferClient(expected_username="xFederiko11")
    # One mutation only; there is intentionally no retry of createPost.
    draft_id = client.create_draft_thread(DRAFT_THREAD, media_url=ROCKSTAR_IMAGE)
    print("Buffer draft created safely, status=draft; id=" + draft_id)
    print("Open Buffer > @xFederiko11 > Drafts. Do NOT select Schedule or Send Now.")
    return draft_id


if __name__ == "__main__":
    run()
