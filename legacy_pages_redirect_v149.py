"""Keep existing public trophy links alive while removing duplicate SEO content.

This file publishes only a lightweight legacy redirect layer. The independent
site in xFederiko11/gta-6 owns the full Italian content and canonical URLs.
Do not delete trophy data, publication ledgers or saved X history.
"""
from __future__ import annotations
from pathlib import Path
from html import escape
from urllib.parse import urlsplit
import json
import os
from portal_links_v148 import trophy_url, PORTAL_BASE

OUT=Path(os.getenv("LEGACY_SITE_OUT","_site"))
OLD_BASE="https://xfederiko11.github.io/federiko-gta-playstation-bot/"
DESTS={
    "index.html": PORTAL_BASE+"/trofei/",
    "guida-medaglie-oro.html": PORTAL_BASE+"/trofei/medaglie-oro/",
}

def render(target: str, title: str) -> str:
    p=urlsplit(target)
    if p.scheme!="https" or p.netloc!="xfederiko11.github.io" or not p.path.startswith("/gta-6/"):
        raise ValueError("Redirect target must belong to the verified GTA 6 site")
    link=escape(target,quote=True)
    name=escape(title)
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8">'
            f'<meta name="robots" content="noindex,follow">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<link rel="canonical" href="{link}">'
            f'<meta http-equiv="refresh" content="0; url={link}">'
            f'<title>{name} — nuova sede GTA 6 Italia</title>'
            f'</head><body><main><h1>La guida si è trasferita</h1>'
            f'<p>Le guide aggiornate si trovano nel nuovo portale.</p>'
            f'<p><a href="{link}">Apri {name} su GTA 6 Italia</a></p>'
            f'</main></body></html>')

def main():
    data=json.loads(Path("trophies-gta6-v142.json").read_text(encoding="utf-8"))
    trophies=data["trophies"]
    if len(trophies)!=55:
        raise ValueError("Expected exactly 55 historical trophy permalinks")
    paths=dict(DESTS)
    for t in trophies:
        path=t["id"]+".html"
        if path in paths: raise ValueError("Duplicate old trophy slug")
        paths[path]=trophy_url(t)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/".nojekyll").write_text("",encoding="utf-8")
    (OUT/"robots.txt").write_text("User-agent: *\nAllow: /\n",encoding="utf-8")
    for filename,target in paths.items():
        title=("Tutti i 55 trofei" if filename=="index.html" else
               "Medaglie Oro" if filename=="guida-medaglie-oro.html" else
               next(t["name_it"] for t in trophies if t["id"]+".html"==filename))
        (OUT/filename).write_text(render(target,title),encoding="utf-8")
    print("LEGACY_REDIRECTS",len(paths),"metadata preserved separately in metrics.json")
if __name__=="__main__":
    main()
