"""Safe, gradual migration from the technical bot's old Pages to GTA 6 Italia.

Never switch to a new permalink before a confirmed 200 response and matching
canonical; no account credentials, web scrapers or paid API.
"""
from __future__ import annotations
import os
import re
import unicodedata
from urllib.parse import urlsplit
import requests

PORTAL_BASE="https://xfederiko11.github.io/gta-6"
TIPS={
    "waink-vehicles-ps5":"scansionare-veicoli",
    "study animals":"studiare-animali",
    "70 challenges":"70-sfide-100-percento",
    "chapter one meditation":"meditazione-capitolo-1",
    "fast travel taxi":"viaggio-rapido-taxi",
    "shooting ranges":"poligoni-concentrazione",
}
def enabled():
    return os.getenv("GTA6_PORTAL_LINKS_ENABLED","false").lower()=="true"

def slug(name):
    ascii_name=unicodedata.normalize("NFKD",name).encode("ascii","ignore").decode("ascii")
    return re.sub(r"^-|-$","",re.sub(r"[^a-z0-9]+","-",ascii_name.lower()))[:70]

def trophy_url(t):
    return PORTAL_BASE + "/trofei/trofeo-"+str(t["number"]).zfill(2)+"-"+slug(t["name_it"])+"/"

def guide_url(tip_id):
    return PORTAL_BASE+"/guide-e-tutorial/"+TIPS[tip_id]+"/"

def page_live(target, session=None):
    """A green GitHub workflow is not proof of a published URL."""
    if not enabled():
        return False
    parsed=urlsplit(target)
    if parsed.scheme!="https" or parsed.hostname!="xfederiko11.github.io":
        return False
    if not parsed.path.startswith("/gta-6/"):
        return False
    http=session or requests
    try:
        with http.get(target,timeout=(3,7),stream=True,allow_redirects=False,
                      headers={"User-Agent":"Federiko-GTA6-Portal/1.0"}) as r:
            if r.status_code!=200:
                return False
            piece=next(r.iter_content(32768),b"").decode("utf-8",errors="replace")
            return ('rel="canonical" href="'+target+'"') in piece and 'lang="it"' in piece
    except (requests.RequestException,StopIteration,OSError):
        return False

def guide_if_live(tip_id,session=None):
    try:
        link=guide_url(tip_id)
    except KeyError:
        return None
    return link if page_live(link,session=session) else None

def trophy_if_live(t,session=None):
    link=trophy_url(t)
    return link if page_live(link,session=session) else None
