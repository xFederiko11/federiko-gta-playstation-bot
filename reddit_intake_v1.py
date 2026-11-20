"""Review-only Reddit lead inbox from user-authorized GitHub Issue intake.

The user may connect Reddit -> IFTTT -> GitHub Issues. We NEVER read Reddit
credentials, scrape Reddit or post Reddit/X responses. Trust only issues
created by the repository owner, with explicit marker and Reddit permalink.
Titles/body are untrusted; avoid translating claims into gameplay facts.
"""
from __future__ import annotations
import argparse,json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from html import escape

OWNER="xfederiko11"
PREFIX="[REDDIT-LEAD]"
SUBS={"gta6":"r/GTA6","gtavi":"r/GTAVI","italygames":"r/italygames"}
MAX_AGE=timedelta(days=7)
MAX_ITEMS=18
PHOTO_MAX_ITEMS=8
LINK=re.compile(r"https://(?:www\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/[A-Za-z0-9]+(?:/[A-Za-z0-9_%-]+)?/?",re.I)
SCORE=(
  ("soldi",r"\b(?:money|cash|soldi|farming|guadagn|heist|rapin)\w*\b"),
  ("glitch",r"\b(?:glitch(?:es)?|exploit(?:s)?|bugs?|duplicat(?:e|ion|ions?)|duplicazion\w*)\b"),
  ("auto",r"\b(?:cars?|auto|veicol|vehicle|garage|save car|salvare|randy|rare car)\w*\b"),
  ("platino",r"\b(?:trophy|trophies|trofe|platino|platinum|100%|achievement|missable)\w*\b"),
  ("guida",r"\b(?:mission|missioni|location|posizion|map|mappa|how to|guide|guida|ps5|help|aiuto)\w*\b"),
  # Title-only lead: an image/clip is NOT downloaded, visually inspected or licensed.
  ("foto",r"\b(?:screenshots?|screen[ -]?shots?|screencaps?|captures?|photomode|photos?|pics?|foto(?:grafi[ae])?|immagin[ei]|mappe|maps?|clips?|gameplay[ -]?footage)\b"),
)
GTA_TITLE=re.compile(r"\b(?:gta[ -]?(?:6|vi)|grand theft auto[ -]?(?:6|vi))\b",re.I)
PHOTO_HUB="https://xfederiko11.github.io/gta-6/screenshot-ps5/"

QUESTION_START=re.compile(r"^(?:how\s+(?:do|can)\s+i\b|where\s+(?:do|can)\s+i\b|anyone\s+know\b|is\s+there\s+a\s+way\b|come\s+(?:faccio|si\s+fa|posso|arrivo)\b|dove\s+(?:trovo|si\s+trova|posso)\b)",re.I)

def generic_question(title):
    """Ambiguous gameplay question: review ONLY after resolving exact GTA VI subreddit."""
    return (isinstance(title,str) and 14<=len(title.strip())<=180
            and QUESTION_START.search(title.strip()) is not None and "?" in title)

def title_topics(title):
    """Use only headline terms for triage; do not infer claims from link text."""
    if not isinstance(title,str):return []
    return [label for label,pattern in SCORE if re.search(pattern,title,re.I)]

def canonical_url(text):
    if not isinstance(text,str) or len(text)>350 or any(ord(c)<33 for c in text):return None
    try:u=urlsplit(text)
    except ValueError:return None
    if u.scheme!="https" or u.hostname not in {"reddit.com","www.reddit.com"} or u.port not in (None,443) or u.username or u.password or u.query or u.fragment:
        return None
    parts=u.path.strip("/").split("/")
    if len(parts) not in (4,5) or parts[0].lower()!="r" or parts[2].lower()!="comments":return None
    sub=parts[1].lower()
    if sub not in SUBS or not re.fullmatch(r"[A-Za-z0-9]{4,12}",parts[3]):return None
    if len(parts)==5 and not re.fullmatch(r"[A-Za-z0-9_-]{1,180}",parts[4]):return None
    return "https://www.reddit.com/r/"+SUBS[sub][2:]+"/comments/"+parts[3]+"/"

# IFTTT shortens PostURL to ift.tt by default. Resolve only the redirect
# response header from that ONE approved shortener host. Never follow a
# redirect or access arbitrary URLs, private networks or Reddit contents.
SHORT_URL=re.compile(r"^https://ift\.tt/[A-Za-z0-9]{4,20}$")
SHORT_BODY=re.compile(r"(Reddit source:\s*)(https://ift\.tt/[A-Za-z0-9]{4,20})(?=\s|$)",re.I)
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None

def expand_ift_link(link):
    if not isinstance(link,str) or not SHORT_URL.fullmatch(link):return None
    req=Request(link,method="HEAD",headers={"User-Agent":"GTA6-Italia-Reddit-Review/1.0"})
    # Some shorteners reject HEAD but return a direct Location on GET.
    # Both requests are to the SAME strictly validated ift.tt URL. The
    # no-redirect opener MUST NOT contact the Location destination.
    opener=build_opener(NoRedirect())
    location=None
    for method in ("HEAD","GET"):
        if method=="GET":
            req=Request(link,method="GET",headers={
                "User-Agent":"GTA6-Italia-Reddit-Review/1.0",
                "Range":"bytes=0-0"})
        try:
            response=opener.open(req,timeout=6)
            response.close()
            return None
        except HTTPError as err:
            if err.code in (301,302,303,307,308):
                location=err.headers.get("Location","")
                break
            if method=="HEAD" and err.code in (403,405,501):
                continue
            return None
        except (URLError,TimeoutError,OSError,ValueError):
            return None
    if not location:return None
    try:
        final=urlsplit(location)
        if final.scheme!="https" or final.hostname not in ("reddit.com","www.reddit.com"):
            return None
        if final.username or final.password or final.port not in (None,443):
            return None
        normalized=urlunsplit(("https","www.reddit.com",final.path,"",""))
        return canonical_url(normalized)
    except (ValueError,TypeError):
        return None

def expand_short_links(rows,resolve=expand_ift_link,max_lookups=20):
    """Materialize verified Reddit permalink only in owner-created Issue leads."""
    if not isinstance(rows,list):return []
    result=[];cache={};remaining=max_lookups
    for original in rows:
        if not isinstance(original,dict):
            result.append(original);continue
        item=dict(original)
        if (str((item.get("author") or {}).get("login","")).lower()==OWNER
            and str(item.get("title") or "").startswith(PREFIX+" ")
            and (title_topics(str(item.get("title") or "")[len(PREFIX):])
                 or generic_question(str(item.get("title") or "")[len(PREFIX):]))
            and re.fullmatch(r"https://github\.com/xFederiko11/federiko-gta-playstation-bot/issues/[0-9]+",str(item.get("url") or ""))):
            body=str(item.get("body") or "")
            match=SHORT_BODY.search(body)
            if match:
                link=match.group(2)
                if link not in cache and remaining>0:
                    remaining-=1
                    cache[link]=resolve(link)
                target=cache.get(link)
                if target and canonical_url(target):
                    item["body"]=body[:match.start(2)]+target+body[match.end(2):]
        result.append(item)
    return result

def parse_issue(row,now):
    if not isinstance(row,dict):return None
    author=row.get("author") or {}
    if str(author.get("login","")).lower()!=OWNER:return None
    title=str(row.get("title") or "")
    if not title.startswith(PREFIX+" "):return None
    issue_url=row.get("url")
    if not isinstance(issue_url,str) or not re.fullmatch(r"https://github\.com/xFederiko11/federiko-gta-playstation-bot/issues/[0-9]+",issue_url):
        return None
    body=str(row.get("body") or "")
    links=LINK.findall(body)
    urls={canonical_url(x) for x in links}
    urls.discard(None)
    if len(urls)!=1:return None
    try:
        when=datetime.fromisoformat(str(row.get("createdAt") or "").replace("Z","+00:00"))
        if when.tzinfo is None:return None
    except (ValueError,TypeError):return None
    if not timedelta(0)<=now.astimezone(timezone.utc)-when.astimezone(timezone.utc)<=MAX_AGE:return None
    candidate=title[len(PREFIX):].strip()
    if len(candidate)<12 or len(candidate)>180:return None
    topics=title_topics(candidate)
    url=next(iter(urls))
    subreddit=urlsplit(url).path.split("/")[2]
    generic=False
    if not topics:
        if generic_question(candidate) and subreddit.lower() in ("gta6","gtavi"):
            # A bare question such as "How do I reach this item?" might be a
            # useful GTA VI help request, but no gameplay conclusion follows.
            topics=["domanda generica da verificare"]
            generic=True
        else:
            return None
    # r/italygames covers games other than GTA. A photo-only title from
    # there needs an explicit GTA VI reference to enter our visual queue.
    photo_only=(topics==["foto"])
    if photo_only and subreddit.lower()=="italygames" and not GTA_TITLE.search(candidate):
        return None
    photo_candidate=("foto" in topics and
                     (subreddit.lower() in ("gta6","gtavi") or
                      GTA_TITLE.search(candidate) is not None))
    return {"title":candidate,"reddit_url":url,"issue_url":issue_url,
            "subreddit":subreddit,"topics":topics,"generic_question":generic,
            "photo_candidate":bool(photo_candidate),
            "photo_reviewed":False,"reuse_authorized":False,
            "created_at":when.astimezone(timezone.utc).isoformat(),"rank":0 if generic else len(topics)}

def select(rows,now):
    if not isinstance(rows,list):return []
    unique={}
    for row in rows[:100]:
        value=parse_issue(row,now)
        if value:
            key=value["reddit_url"]
            if key not in unique or value["created_at"]>unique[key]["created_at"]:unique[key]=value
    # Greatest relevance score first, then NEWEST issues first (previously oldest first).
    return sorted(unique.values(),key=lambda e:(e["rank"],e["created_at"]),reverse=True)[:MAX_ITEMS]

def select_visual(rows,now):
    """Independent, bounded photo queue so generic news cannot hide imagery.

    This is triage of verified-format owner-created Issues, NOT an image feed.
    Visual leads about money and vehicles take priority, then recency.
    """
    if not isinstance(rows,list):
        return []
    uniq={}
    for row in rows[:100]:
        item=parse_issue(row,now)
        if item is None or not item["photo_candidate"]:
            continue
        key=item["reddit_url"]
        if key not in uniq or item["created_at"]>uniq[key]["created_at"]:
            uniq[key]=item
    return sorted(uniq.values(),key=lambda item: (
        int("soldi" in item["topics"]),int("auto" in item["topics"]),
        item["created_at"]),reverse=True)[:PHOTO_MAX_ITEMS]


def markdown(rows,now):
    selected=select(rows,now)
    received=sum(1 for item in (rows if isinstance(rows,list) else [])
        if isinstance(item,dict)
        and str((item.get("author") or {}).get("login","")).lower()==OWNER
        and str(item.get("title") or "").startswith(PREFIX+" "))
    shortened=sum(1 for item in (rows if isinstance(rows,list) else [])
        if isinstance(item,dict)
        and str((item.get("author") or {}).get("login","")).lower()==OWNER
        and str(item.get("title") or "").startswith(PREFIX+" ")
        and (title_topics(str(item.get("title") or "")[len(PREFIX):])
             or generic_question(str(item.get("title") or "")[len(PREFIX):]))
        and "https://ift.tt/" in str(item.get("body") or ""))
    irrelevant=sum(1 for item in (rows if isinstance(rows,list) else [])
        if isinstance(item,dict)
        and str((item.get("author") or {}).get("login","")).lower()==OWNER
        and str(item.get("title") or "").startswith(PREFIX+" ")
        and not title_topics(str(item.get("title") or "")[len(PREFIX):])
        and not generic_question(str(item.get("title") or "")[len(PREFIX):]))
    generic_count=sum(1 for item in selected if item.get("generic_question"))
    relevant_count=len(selected)-generic_count
    photo_candidates=select_visual(rows,now)
    lines=["<!-- gta6-reddit-intake-v1 -->","# GTA VI - Opportunità Reddit (revisione necessaria)","",
      "**Reddit → IFTTT → GitHub: ricezione confermata dall'Issue #69 del 20 novembre 2026.** "
      "Questa dashboard misura gli eventi effettivamente ricevuti, non lo stato live di IFTTT.",
      "**Questa coda non pubblica post, commenti, voti, follow o messaggi.**",
      "I titoli sono segnalazioni ricevute tramite IFTTT/GitHub, non fatti verificati. "
      "Apri il permalink e controlla regole del subreddit, contenuto e data prima di intervenire.","",
      f"Controllo UTC: {now.astimezone(timezone.utc).isoformat()} · "
      f"Eventi Reddit ricevuti: {received} · non pertinenti dal titolo: {irrelevant} · "
      f"pertinenti e con URL verificato: {relevant_count} · "
      f"domande generiche da rivedere: {generic_count} · "
      f"possibili foto/clip dal solo titolo: {len(photo_candidates)} · "
      f"link IFTTT da risolvere: {shortened} · "
      "nessuna metrica X o Reddit disponibile.",""]
    # A standalone, proof-only opportunity list uses previously trusted
    # owner-created Issue links. It NEVER scrapes Reddit posts or downloads
    # image bytes, and it cannot promise contributor rights or even an image.
    lines += ["## 📸 Possibili prove visive per le guide", "",
      "Queste sono **segnalazioni dal titolo**, non screenshot verificati, "
      "scaricati o ricevuti. Prima di usare una foto controlla il post, "
      "la piattaforma/patch, gli spoiler, la pertinenza al singolo passaggio "
      "e il consenso esplicito per la ripubblicazione.",
      "[Centro richieste screenshot PS5]("+PHOTO_HUB+") · "
      "[Materiali promozionali ufficiali Rockstar](https://www.rockstargames.com/VI/media/screenshots) "
      "(da non contare come prova delle singole procedure).", ""]
    if not photo_candidates:
        lines.append("Nessuna segnalazione fotografica verificabile nei titoli della coda attuale.")
    for item in photo_candidates[:8]:
        title=escape(re.sub(r"[\x00-\x1f\x7f]"," ",item["title"]))
        title=re.sub(r"([\\\x60*_{}\[\]()#+.!>|])",r"\\\1",title)
        lines.extend([
          "- **Da verificare:** "+title+" · r/"+item["subreddit"]+
          " · [Apri il post]("+item["reddit_url"]+") · "
          "[Issue originale]("+item["issue_url"]+")",
          "  - Non esaminato: non sappiamo se contenga un file originale, "
          "se raffiguri GTA VI su PS5 o se possa essere condiviso sul sito.",
        ])
    lines.append("")
    if not selected:
        reason=("La connessione IFTTT → GitHub è verificata: sono arrivati eventi, ma "
                "nessuno supera per ora i controlli di pertinenza e permalink."
                if received else
                "Nessun evento Reddit ancora ricevuto. Controlla l'Activity dell'Applet.")
        lines.extend([reason,""])
    for i,item in enumerate(selected,1):
        title=escape(re.sub(r"[\x00-\x1f\x7f]", " ", item["title"]))
        # No user-provided Markdown, links or instructions injected as link destinations.
        title=re.sub(r"([\\\x60*_{}\[\]()#+.!>|])",r"\\\1",title)
        lines.extend([f"### {i}. {title}",
          "- Subreddit: r/"+item["subreddit"]+" · temi: "+", ".join(item["topics"]),
          "- [Leggi il post originale]("+item["reddit_url"]+") · [Segnalazione importata]("+item["issue_url"]+")",
          ("- ⚠️ Titolo generico, **non è una scoperta GTA VI verificata**: leggi il contenuto reale prima di intervenire."
           if item.get("generic_question") else "- Argomento specifico: resta comunque da verificare il post completo."),
          ("- ⚠️ Glitch: controlla **patch PS5**, stato **trofei/platino**, "
           "rischi del salvataggio e due riscontri prima di proporre una procedura."
           if "glitch" in item["topics"] else ""),
          "- Se puoi aiutare: prepara una risposta concreta **senza link promozionali**. "
          "Leggi prima le regole del subreddit e invia manualmente solo se appropriato.",
          "- Non affermare che un glitch funziona, che i trofei sono al sicuro o che il "
          "post è confermato sulla base del titolo.",""])
    lines+=["## Attivazione","",
      "Account Reddit e GitHub già collegati in IFTTT secondo lo screenshot del 20 novembre; non ripetere la configurazione. In assenza di segnalazioni controlla l'Activity dell'Applet.",
      "Applet: Reddit (nuovo post pertinente in r/GTA6/r/GTAVI/r/italygames, "
      "secondo i trigger disponibili) → GitHub Create Issue nel repo del bot.",
      "Prefisso titolo: `[REDDIT-LEAD]` seguito dal titolo del post; body con il permalink completo "
      "https://www.reddit.com/r/.../comments/ID/. Senza URL valido o autore del "
      "repository, la segnalazione viene scartata.",
      "Non autorizzare pubblicazioni o commenti Reddit per questo flusso.","",
      "## Priorità","",
      "1. Risolvere domande concrete su soldi/auto/trofei con istruzioni attribuite.",
      "2. Preparare guide italiane originali quando c'è una scoperta indipendentemente verificata.",
      "3. Collegare la guida a X tramite il calendario editoriale esistente, "
      "senza spammare il subreddit.",
      ""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    rows=json.loads(args.input.read_text(encoding="utf-8"))
    rows=expand_short_links(rows)
    now=datetime.now(timezone.utc)
    output=markdown(rows,now)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(output,encoding="utf-8")
    print("REDDIT_INTAKE_VALID_REVIEW_ONLY",len(select(rows,now)))

if __name__=="__main__":main()
