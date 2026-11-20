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
from urllib.parse import urlsplit,unquote
from html import escape

OWNER="xfederiko11"
PREFIX="[REDDIT-LEAD]"
SUBS={"gta6":"r/GTA6","gtavi":"r/GTAVI","italygames":"r/italygames"}
MAX_AGE=timedelta(days=7)
MAX_ITEMS=18
LINK=re.compile(r"https://(?:www\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/[A-Za-z0-9]+(?:/[A-Za-z0-9_%-]+)?/?",re.I)
SCORE=(
  ("soldi",r"\b(?:money|cash|soldi|farming|guadagn|heist|rapin|glitch|duplicate|duplicazion)\w*\b"),
  ("auto",r"\b(?:cars?|auto|veicol|vehicle|garage|save car|salvare|randy|rare car)\w*\b"),
  ("platino",r"\b(?:trophy|trophies|trofe|platino|platinum|100%|achievement|missable)\w*\b"),
  ("guida",r"\b(?:mission|missioni|location|posizion|map|mappa|how to|guide|guida|ps5|help|aiuto)\w*\b"),
)

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
    lowered=candidate.lower()
    topics=[label for label,pattern in SCORE if re.search(pattern,lowered,re.I)]
    if not topics:return None
    # No inferred content: subject only, user must inspect the actual Reddit post.
    url=next(iter(urls))
    return {"title":candidate,"reddit_url":url,"issue_url":issue_url,
            "subreddit":urlsplit(url).path.split("/")[2],"topics":topics,
            "created_at":when.astimezone(timezone.utc).isoformat(),"rank":len(topics)}

def select(rows,now):
    if not isinstance(rows,list):return []
    unique={}
    for row in rows[:100]:
        value=parse_issue(row,now)
        if value:
            key=value["reddit_url"]
            if key not in unique or value["created_at"]>unique[key]["created_at"]:unique[key]=value
    return sorted(unique.values(),key=lambda e:(-e["rank"],e["created_at"]),reverse=False)[:MAX_ITEMS]

def markdown(rows,now):
    selected=select(rows,now)
    lines=["<!-- gta6-reddit-intake-v1 -->","# GTA VI - Opportunità Reddit (revisione necessaria)","",
      "**IFTTT Reddit → GitHub: Applet collegata secondo lo screenshot utente del 20 novembre 2026.** "
      "Questa dashboard misura soltanto gli eventi effettivamente ricevuti da GitHub, non lo stato live di IFTTT.",
      "**Questa coda non pubblica post, commenti, voti, follow o messaggi.**",
      "I titoli sono segnalazioni ricevute tramite IFTTT/GitHub, non fatti verificati. "
      "Apri il permalink e controlla regole del subreddit, contenuto e data prima di intervenire.","",
      f"Controllo UTC: {now.astimezone(timezone.utc).isoformat()} · "
      f"Segnalazioni valide: {len(selected)} · nessuna metrica X o Reddit disponibile.",""]
    if not selected:lines+=["Nessuna segnalazione Reddit valida ancora ricevuta: il collegamento IFTTT è visibile nello screenshot, ma il passaggio end-to-end non è ancora confermato. Verifica View activity se il trigger ha già trovato nuovi post.",""]
    for i,item in enumerate(selected,1):
        title=escape(re.sub(r"[\x00-\x1f\x7f]", " ", item["title"]))
        # No user-provided Markdown, links or instructions injected as link destinations.
        title=re.sub(r"([\\\x60*_{}\[\]()#+.!>|])",r"\\\1",title)
        lines.extend([f"### {i}. {title}",
          "- Subreddit: r/"+item["subreddit"]+" · temi: "+", ".join(item["topics"]),
          "- [Leggi il post originale]("+item["reddit_url"]+") · [Segnalazione importata]("+item["issue_url"]+")",
          "- Se puoi aiutare: prepara una risposta concreta **senza link promozionali**. "
          "Leggi prima le regole del subreddit e invia manualmente solo se appropriato.",
          "- Non affermare che un glitch funziona, che i trofei sono al sicuro o che il "
          "post è confermato sulla base del titolo.",""])
    lines+=["## Attivazione","",
      "Account Reddit e GitHub già collegati in IFTTT secondo lo screenshot del 20 novembre; non ripetere la configurazione. In assenza di segnalazioni controlla l'Activity dell'Applet.",
      "Applet: Reddit (nuovo post pertinente in r/GTA6/r/GTAVI/r/italygames, "
      "secondo i trigger disponibili) → GitHub Create Issue nel repo del bot.",
      "Prefisso titolo: \`[REDDIT-LEAD]\` seguito dal titolo del post; body con il permalink completo "
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
    now=datetime.now(timezone.utc)
    output=markdown(rows,now)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(output,encoding="utf-8")
    print("REDDIT_INTAKE_VALID_REVIEW_ONLY",len(select(rows,now)))

if __name__=="__main__":main()
