"""Free, read-only Google Trends Trending Now signal; NOT national keyword volume."""
import argparse
from datetime import datetime,timezone
from html import escape
from pathlib import Path
import re,xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler

FEED="https://trends.google.com/trending/rss?geo=IT"
MAX_BYTES=750_000
GTA=re.compile(r"\b(?:gta\s*(?:6|vi)|grand\s+theft\s+auto\s+(?:6|vi))\b",re.I)
TOPICS=(
 ("Come salvare un’auto in GTA 6","gta 6 salvare auto","salvare-auto/"),
 ("Come registrare un veicolo in GTA 6","gta 6 registrare auto","salvare-auto/"),
 ("Garage gratuiti e codici GTA 6","gta 6 garage","garage-gratuiti/"),
 ("Come fare soldi in GTA 6","gta 6 soldi","soldi-facili/"),
 ("Glitch e stato patch GTA 6","gta 6 glitch","glitch/"),
 ("Platino e collezionabili GTA 6","gta 6 platino","trofei/"),
)
BASE="https://xfederiko11.github.io/gta-6/"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def fetch():
    req=Request(FEED,headers={"User-Agent":"GTA6Italia-Research/1.0","Accept":"application/rss+xml,application/xml,text/xml"})
    with build_opener(NoRedirect()).open(req,timeout=12) as r:
        if r.status!=200 or r.geturl()!=FEED:raise ValueError("Unexpected feed response")
        data=r.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ValueError("Feed too large")
    return data

def parse(data):
    if len(data)>MAX_BYTES or re.search(br"<!\s*(?:DOCTYPE|ENTITY)",data,re.I):raise ValueError("Unsafe RSS")
    root=ET.fromstring(data)
    if root.tag!="rss" or root.find("channel") is None:raise ValueError("Not Google Trends RSS")
    rows=[];seen=set();items=root.findall("./channel/item")
    for item in items:
        title=" ".join((item.findtext("title") or "").split())
        if not title or len(title)>180 or not GTA.search(title) or title.casefold() in seen:continue
        seen.add(title.casefold())
        # Untrusted titles remain plain text. Only a strictly numeric traffic label is accepted.
        traffic=next((v.text or "" for v in item if v.tag.split("}")[-1]=="approx_traffic"),"").strip()
        if not re.fullmatch(r"[0-9][0-9., ]{0,12}\+?",traffic):traffic=""
        rows.append((title,traffic))
    return len(items),rows

def md(text):
    # Prevent markdown, HTML, mentions and external link injection from RSS titles.
    return escape(text,quote=True).replace("@","&#64;").replace("[","&#91;").replace("]","&#93;").replace("|","&#124;").replace("!","&#33;").replace("`","&#96;").replace("*","&#42;").replace("_","&#95;").replace("\\","&#92;")

def report(loader=fetch):
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines=["\n## Google — domanda di ricerca Italia (sola lettura)","",f"Controllo UTC: {now}. Fonte: [Google Trends — Trending Now Italia](https://trends.google.com/trending?geo=IT)."]
    try:
        total,rows=parse(loader())
        lines.append(f"RSS letto: {total} trend generali; {len(rows)} titoli GTA VI pertinenti.")
        if not rows:lines.append("Nessun trend GTA VI nel campione: non significa zero ricerche.")
        for title,traffic in rows[:20]:
            lines.append("- "+md(title)+(" — traffico approssimativo del trend: "+traffic if traffic else ""))
        status="ok"
    except (OSError,ValueError,ET.ParseError) as exc:
        lines.append("Feed non disponibile ("+type(exc).__name__+"). Nessun volume o trend inventato.")
        status="unavailable"
    lines += ["","Trending Now osserva picchi generali, non è una graduatoria completa delle keyword GTA 6 né un volume mensile.","","### Ipotesi editoriali da verificare (non classifica per volume)","",
              "Priorità: salvataggio/registrazione su una sola pagina canonica; evitare duplicati. Controllare impressioni, CTR e pagina in Search Console prima di modificare titoli."]
    for label,query,path in TOPICS:
        link="https://trends.google.com/trends/explore?"+urlencode({"geo":"IT","date":"today 3-m","q":query})
        lines.append("- "+label+" — [Confronta in Trends]("+link+") · [Pagina canonica]("+BASE+path+")")
    lines += ["","[Search Console — prestazioni](https://search.google.com/search-console/performance/search-analytics) · [API Trends alpha](https://developers.google.com/search/apis/trends). I dati Search Console richiedono autorizzazione dedicata; non sono raccolti dal feed. Nessun servizio SEO a pagamento, nessuna riscrittura o pubblicazione automatica.",""]
    return status,"\n".join(lines)

def main():
    p=argparse.ArgumentParser();p.add_argument("--append",required=True);args=p.parse_args()
    status,body=report()
    with Path(args.append).open("a",encoding="utf-8") as f:f.write(body)
    print("GOOGLE_KEYWORD_WATCH",status,"read_only=True")
if __name__=="__main__":main()
