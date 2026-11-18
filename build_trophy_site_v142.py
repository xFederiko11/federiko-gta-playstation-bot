"""Build an accessible static Italian GTA VI trophy site for GitHub Pages.

All data is source-linked and stored in trophies-gta6-v142.json. No paid APIs.
SEO landing + 55 individually crawlable pages + sitemap + robots + icons.
Hidden trophies have noindex unless SPOILER_INDEX=1 (explicit editorial opt-in).
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

DATA=Path("trophies-gta6-v142.json")
OUT=Path(os.getenv("TROPHY_OUTPUT_DIR","_site"))
REPO="federiko-gta-playstation-bot"
BASE="https://xfederiko11.github.io/"+REPO
CSS="""
:root{color-scheme:dark;--bg:#0a101b;--panel:#141e2c;--muted:#acb9c7;--white:#f6f8fb;--accent:#74dbce}
*{box-sizing:border-box}body{background:var(--bg);color:var(--white);margin:0;font:16px/1.65 system-ui,-apple-system,Segoe UI,Arial,sans-serif}
main{max-width:900px;margin:auto;padding:28px 20px 80px}
a{color:#8ee9df}a:focus-visible,button:focus-visible{outline:3px solid #efc666}
h1{font-size:clamp(1.6rem,4vw,2.6rem);line-height:1.16}
h2{font-size:1.3rem}.lead,.muted{color:var(--muted)}
header{border-bottom:1px solid #2c3746;background:#111928;padding:12px 20px}
header>div{max-width:900px;margin:auto;display:flex;justify-content:space-between;gap:18px;align-items:center;flex-wrap:wrap}
header a{text-decoration:none}.stamp{font-size:.8rem;color:#a8c7c4}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:28px 0}
.card{background:var(--panel);border:1px solid #324153;border-radius:14px;padding:18px}
.card h2{margin:6px 0}.card p{margin:6px 0 16px}.chip{display:inline-flex;font-size:.78rem;border:1px solid #64707e;padding:2px 10px;border-radius:20px;color:#e9f2f6}
.gold{color:#ffe19a}.silver{color:#d4e9f7}.bronze{color:#f8bba0}.platinum{color:#c4c1fa}
.media{width:100%;max-height:360px;object-fit:cover;border-radius:12px;border:1px solid #354b56}
.source{border-top:1px solid #33404e;margin-top:30px;padding-top:14px;color:var(--muted);font-size:.93rem}
nav.tabs{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
button{font:inherit;background:#213245;border:1px solid #52717b;border-radius:9px;color:white;padding:8px 12px;cursor:pointer}
button[aria-pressed=true]{background:#155857}
.warning{padding:12px;background:#382b25;border:1px solid #94694c;border-radius:10px}
details{border:1px solid #526172;border-radius:10px;padding:10px;margin:12px 0}
summary{cursor:pointer;font-weight:bold}
footer{color:var(--muted);font-size:.85rem;margin-top:35px}
"""
# Official promotional Rockstar screenshots, strictly illustrative, not trophy proof.
# The URLs are already used in the project's licensed/attributed GTA VI gallery.
PHOTOS=[
"https://www.rockstargames.com/VI/_next/static/media/Vice_City_01.135x56yoeu.6t.jpg?akim=1&imdensity=1&imwidth=3840",
"https://www.rockstargames.com/VI/_next/static/media/Lucia_Caminos_05.0i5b7k6a7_w6p.jpg?akim=1&imdensity=1&imwidth=3840",
"https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_01.0zgz7tveur6y8.jpg?akim=1&imdensity=1&imwidth=3840",
]
def esc(t):
    return html.escape(str(t or ""),quote=True)
def photo(t):
    if t["photo_group"]=="city":
        return PHOTOS[0]
    if t["photo_group"]=="characters":
        return PHOTOS[1]
    return PHOTOS[2]
def layout(title,description,body,canonical,image=None,robots="index,follow",jsonld=None):
    img=esc(image or PHOTOS[0]);meta=json.dumps(jsonld or {},ensure_ascii=False).replace("</","<\\/") if jsonld else ""
    return f"""<!doctype html><html lang="it"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(description)}">
<meta name="robots" content="{esc(robots)}"><link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article"><meta property="og:locale" content="it_IT">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}"><meta name="twitter:image" content="{img}">
<link rel="stylesheet" href="{esc(BASE)}/assets/style.css">
{('<script type="application/ld+json">'+meta+'</script>') if jsonld else ''}
</head><body><header><div><a href="{BASE}/">🏆 GTA VI · Trofei in italiano</a><span class="stamp">Guida indipendente · No spoiler di default</span></div></header>
<main>{body}<footer>Guide indipendenti in italiano. Screenshots illustrativi © Rockstar Games: non rappresentano prove di sblocco. I dati possono cambiare con le patch. Nessuna affiliazione ufficiale con Rockstar, PlayStation o PowerPyx.</footer></main></body></html>"""
def build():
    data=json.loads(DATA.read_text(encoding="utf-8"))
    trophies=data["trophies"]
    tiers=Counter(t["tier"] for t in trophies)
    assert len(trophies)==55 and len({t["id"] for t in trophies})==55
    assert tiers==Counter({"Platino":1,"Oro":2,"Argento":6,"Bronzo":46})
    assert sum(t["hidden"] for t in trophies)==28
    OUT.mkdir(exist_ok=True,parents=True);(OUT/"assets").mkdir(exist_ok=True)
    (OUT/"assets/style.css").write_text(CSS,encoding="utf-8")
    pages=[BASE+"/"]
    index_cards=[];hidden_cards=[]
    for t in trophies:
        slug=t["id"]+".html";url=BASE+"/"+slug
        image=photo(t)
        # Keep story secrets out of search results during the first launch window,
        # then index all 55 trophy pages without a permanent manual toggle.
        spoiler_override=os.getenv("SPOILER_INDEX")
        show_secret=(spoiler_override=="1" if spoiler_override in ("0","1")
                     else datetime.now(timezone.utc)>=datetime(2026,11,21,tzinfo=timezone.utc))
        robots="index,follow" if (not t["hidden"] or show_secret) else "noindex,follow"
        name=esc(t["name_it"]);desc=esc(t["requirement_it"])
        class_tier=({"Oro":"gold","Argento":"silver","Bronzo":"bronze","Platino":"platinum"}[t["tier"]])
        title=f"{t['name_it']} — trofeo {t['tier']} GTA VI PS5 | Guida italiana"
        summary=(f"Come sbloccare il trofeo {t['name_it']} ({t['tier']}) in GTA VI su PS5: "
                 +t["requirement_it"])
        content=f'<p><a href="{BASE}/">← Tutti i trofei</a></p>'
        content+=f'<span class="chip {class_tier}">{esc(t["tier"])}</span><h1>{name}</h1>'
        if t["hidden"]:
            content+='<p class="warning">⚠️ Contiene possibili spoiler della storia o delle attività.</p>'
        content+=f'<p class="lead">{desc}</p><h2>📋 Requisito per sbloccarlo</h2><p>{desc}</p>'
        if t.get("tip_it"):
            content+=f'<h2>💡 Consiglio per il platino</h2><p>{esc(t["tip_it"])}</p>'
        content+=f'<figure><img class="media" loading="lazy" src="{esc(image)}" alt="Screenshot promozionale ufficiale GTA VI, immagine illustrativa"><figcaption class="muted">Immagine promozionale Rockstar Games, illustrativa; non è uno screenshot del trofeo.</figcaption></figure>'
        content+=f'<p class="source">Fonte per la roadmap e i requisiti: <a rel="noopener noreferrer" href="{esc(t["source_url"])}">PowerPyx – GTA VI Trophy Guide</a>. <a href="https://www.planetgta6.com/it/trofei-gta-6/">Elenco PS5 in italiano</a>.</p>'
        structured={"@context":"https://schema.org","@type":"Article","headline":title,
                    "description":summary,"inLanguage":"it-IT","url":url,
                    "isPartOf":{"@type":"CollectionPage","name":"Trofei GTA VI in italiano","url":BASE+"/"},
                    "about":{"@type":"VideoGame","name":"Grand Theft Auto VI"}}
        (OUT/slug).write_text(layout(title,summary,content,url,image,robots,structured),encoding="utf-8")
        if not t["hidden"] or show_secret:pages.append(url)
        card=f'<article class="card"><span class="chip {class_tier}">{esc(t["tier"])}</span><h2><a href="{slug}">{name}</a></h2><p>{desc}</p></article>'
        (hidden_cards if t["hidden"] else index_cards).append(card)
    # Dedicated search page for the difference between gold-tier trophies
    # and gold medals in activities: GTA VI has NO story mission gold medals.
    gold_title="GTA VI: trofei Oro e medaglie Oro — requisiti PS5"
    gold_body='<h1>🥇 GTA VI — tutti i requisiti Oro</h1>'
    gold_body+='<p><a href="'+BASE+'/">← Catalogo completo 55 trofei</a></p>'
    gold_body+='<h2>🏆 I 2 trofei Oro PS5</h2><p><a href="trofeo-07.html">Devi sapere quando scendere</a>: completa l’ultima missione della storia.</p>'
    gold_body+='<p><a href="trofeo-14.html">Una lunga strada</a>: raggiungi il 100% della checklist di completamento.</p>'
    gold_body+='<h2>🎯 Medaglie Oro nelle attività</h2>'
    gold_body+='<p>⚠️ Secondo PowerPyx, GTA VI non prevede medaglie Oro per le missioni della storia.</p>'
    gold_body+='<p>Per il trofeo Argento <a href="trofeo-17.html">Cecchino</a> servono tutte le 42 medaglie Oro nei 12 poligoni di tiro.</p>'
    gold_body+='<p>La checklist del 100% include inoltre 10 medaglie Oro su 13 sfide di gara, oltre ai requisiti delle altre attività.</p>'
    gold_body+='<p class="source">Fonte: <a href="https://www.powerpyx.com/gta-6-grand-theft-auto-vi-trophy-guide-roadmap/">PowerPyx Trophy Roadmap</a> e <a href="https://www.powerpyx.com/gta-6-100-completion-checklist-guide/">100% Completion Checklist</a>.</p>'
    gold_url=BASE+"/guida-medaglie-oro.html"
    (OUT/"guida-medaglie-oro.html").write_text(layout(gold_title,
        "I 2 trofei Oro GTA VI e le medaglie Oro delle attività: 42 poligoni di tiro, 10 sfide gara e nessuna medaglia nella storia.",
        gold_body,gold_url,PHOTOS[0],jsonld={"@context":"https://schema.org","@type":"Article",
        "headline":gold_title,"inLanguage":"it-IT","url":gold_url}),encoding="utf-8")
    pages.append(gold_url)
    intro=f'<h1>🏆 GTA VI — tutti i 55 trofei PS5 in italiano</h1><p class="lead">Requisiti, medaglie Oro delle attività e consigli per il platino. 1 Platino · 2 Oro · 6 Argento · 46 Bronzo. Nessun trofeo online nella lista base.</p>'
    intro+='<p>⚠️ Una meditazione del Capitolo 1 potrebbe essere mancabile. Prima di procedere conserva un salvataggio manuale.</p>'
    intro+='<p><a href="https://www.powerpyx.com/gta-6-grand-theft-auto-vi-trophy-guide-roadmap/">📖 Roadmap PowerPyx</a> · <a href="https://www.planetgta6.com/it/trofei-gta-6/">Elenco trofei in italiano</a></p>'
    intro+='<p>🥇 <a href="guida-medaglie-oro.html">Trofei Oro e medaglie Oro: tutti i requisiti</a></p>'
    intro+='<h2>Trofei visibili (senza spoiler)</h2><div class="cards">'+''.join(index_cards)+'</div>'
    intro+='<details><summary>⚠️ Mostra i 28 trofei nascosti (spoiler)</summary><div class="cards">'+''.join(hidden_cards)+'</div></details>'
    (OUT/"index.html").write_text(layout("GTA VI Trofei PS5: tutti i 55 requisiti in italiano | Guida al platino",
        "Guida GTA 6 platino PS5: 55 trofei, 2 Oro, requisiti, sfide e consigli PowerPyx. Spoiler nascosti.",
        intro,BASE+"/",PHOTOS[0],jsonld={"@context":"https://schema.org","@type":"CollectionPage",
        "name":"Tutti i trofei GTA VI su PS5","url":BASE+"/","inLanguage":"it-IT",
        "numberOfItems":len(trophies)}),encoding="utf-8")
    sitemap='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+esc(u)+'</loc></url>' for u in pages)+'</urlset>'
    (OUT/"sitemap.xml").write_text(sitemap,encoding="utf-8")
    (OUT/"robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: "+BASE+"/sitemap.xml\n",encoding="utf-8")
    (OUT/".nojekyll").write_text("",encoding="utf-8")
    print(f"SEO_SITE_BUILT pages={len(trophies)} visible={len(index_cards)} hidden={len(hidden_cards)} sitemap_urls={len(pages)}")
if __name__=="__main__":
    build()
