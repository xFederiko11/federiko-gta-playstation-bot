"""GTA VI Italia: free, read-only map launch promotion and honest funnel metrics.

Never mutate Buffer/X, fetch paid X analytics, imply follower conversions from
link clicks, or announce map embeds unless the live Pages audit is verified.
"""
from __future__ import annotations
import argparse,csv,json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit,quote
from urllib.request import Request,HTTPRedirectHandler,build_opener
from urllib.error import HTTPError,URLError

SOURCE="https://xfederiko11.github.io/gta-6/map-rollout-v1.json"
BASE="https://xfederiko11.github.io/gta-6/"
SCHEMA="gta6-interactive-maps-v1"
FIELDS=("date","map_load_intents","map_named_search_intents","map_external_open_intents",
        "map_follow_intents","x_profile_visits","x_new_followers")
MANUAL=Path("map-engagement-manual-v1.csv")
DRAFTS=(
 ("mappa-generale","mappe-guide/",
  "🗺️ GTA VI | Non basta vedere un nome su una mappa. Abbiamo raccolto un marker della CASA di Jason, una zona e due schede locali, distinguendoli dai pin dei singoli oggetti. Mappe zoomabili con le fonti."),
 ("collezionabili","collezionabili/percorsi/",
  "📍 GTA VI PS5 | 123 checkpoint, 9 link utili a edifici o zone e 0 pin certi di oggetti singoli. Usa la mappa per orientarti, poi apri la guida con foto e fonti. Quale punto ti manca?"),
 ("meditazioni","guide-e-tutorial/meditazione-capitolo-1/",
  "🏆 GTA VI | Meditazione con Lucia nel Capitolo 1: il riferimento è la CASA di Jason a Key Lento. Abbiamo trovato il marker dell'edificio, non la coordinata di ogni interazione. Salva prima di avanzare.")
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):return None


def validate(data):
    required={"guide_articles":11,"trophy_articles":55,"articles_with_map":66,
              "pages_with_interactive_map":68,"guide_location_descriptions":18,
              "collectible_descriptions":123,"exact_gameplay_coordinate_pairs_verified":0,
              "external_map_references_reviewed":4,"external_community_building_markers":1,
              "external_community_region_links":1,"external_location_detail_links":2,
              "individual_collectible_pins_verified":0}
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA:
        raise ValueError("Unexpected map status")
    if any(type(data.get(k)) is not int or data[k]!=v for k,v in required.items()):
        raise ValueError("Map rollout not verified")
    if data.get("external_maps_loaded_automatically") is not False or data.get("named_place_search_is_exact_pin") is not False:
        raise ValueError("Privacy / map accuracy claim invalid")
    if data.get("external_link_verification")!="indexed_public_source_not_in_game_or_live_api":
        raise ValueError("No proof that the community marker corresponds to in-game GPS")
    providers=data.get("providers")
    if not isinstance(providers,list) or [x.get("embed") for x in providers if isinstance(x,dict)]!=[
        "https://vice-map.com/embed/map","https://gta6.city/embed/map"]:
        raise ValueError("Unverified map provider")
    return True


def fetch_public(open_fn=None):
    opener=open_fn or build_opener(NoRedirect()).open
    request=Request(SOURCE,headers={"User-Agent":"GTA6Italia-MapGrowth/1.0","Accept":"application/json"})
    with opener(request,timeout=12) as response:
        if response.geturl()!=SOURCE:
            raise ValueError("Untrusted map status redirect")
        if response.headers.get("Content-Type","").split(";")[0].strip().lower() not in {"application/json","text/plain","application/octet-stream"}:
            raise ValueError("Map status not JSON")
        payload=response.read(65537)
    if len(payload)>65536:raise ValueError("Map report too large")
    data=json.loads(payload)
    validate(data)
    return data


def metric_row(path=MANUAL):
    path=Path(path)
    if not path.exists():return None
    with path.open(encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or ())!=FIELDS:raise ValueError("Metric fields mismatch")
        rows=list(reader)
    if len(rows)>365:raise ValueError("Excessive manual metrics")
    values=[]
    for row in rows:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",row.get("date","")):
            raise ValueError("Bad manual metric date")
        datetime.strptime(row["date"],"%Y-%m-%d")
        record={"date":row["date"]}
        for key in FIELDS[1:]:
            raw=(row.get(key) or "").strip()
            if raw and (not raw.isdigit() or int(raw)>1_000_000_000):
                raise ValueError("Malformed manual analytics")
            record[key]=int(raw) if raw else None
        values.append(record)
    if len({x["date"] for x in values})!=len(values):
        raise ValueError("Duplicate metric date")
    return sorted(values,key=lambda x:x["date"])[-1] if values else None


def drafts():
    from editorial_seo_v135 import x_weight
    posts=[]
    for ident,path,body in DRAFTS:
        if not re.fullmatch(r"(?:[a-z0-9-]+/)+",path) or x_weight(body)>235:
            raise ValueError("Map campaign draft unsafe for image-backed post")
        url=BASE+path
        reply="🗺️ Apri la guida con fonti e limiti dei pin:\n"+url
        if x_weight(reply)>280:raise ValueError("Reply over X limit")
        posts.append({"id":ident,"url":url,"text":body,
                      "reply":reply,"compose":"https://x.com/intent/tweet?text="+quote(body,safe=""),
                      "published":False})
    return posts


def markdown(verified,metrics):
    out=["## 🗺️ Mappe interattive: campagna X e verifica della conversione","",
         "Tutti i contenuti sono manuali o utilizzano slot editoriali già previsti: "
         "niente post extra, follower acquistati, reply automatiche o API X a consumo.",""]
    if verified:
        out+=["**Copertura live verificata:** 11 guide + 55 schede di trofei + hub + atlante = "
              "**68 pagine con mappa**; 123 checkpoint descritti, nessuna coordinata inventata.",
              "**Quattro link esterni curati:** un marker di edificio (casa di Jason),",
              "un collegamento regionale (Permit Keys), due schede località (Starlet Motel, Key Lento).",
              "**Zero pin del singolo oggetto confermati.** Il link a un edificio non individua",
              "una rivista, una carta o l'esatto requisito di un trofeo.",
              "I permalink sono riferimenti pubblicamente indicizzati, non una verifica GPS in-game.","",
              "### Tre bozze originali per far scoprire le mappe",""]
        for row in drafts():
            out+=["**"+row["id"]+"** · [Bozza X]("+row["compose"]+") · [Articolo]("+row["url"]+")",
                  "~~~text",row["text"],"~~~",
                  "Risposta con link (soltanto dopo aver pubblicato il primo post):",
                  "~~~text",row["reply"],"~~~",""]
        out+=["Non pubblicare tutte le bozze in serie. Il normale post del 23/11 può "
              "parlare della nuova mappa, senza superare il budget editoriale.",""]
    else:
        out+=["**Mappa live non verificabile al momento del controllo:** nessuna bozza viene "
              "spacciata per un annuncio già pubblicabile.",
              "[Apri il sito per un controllo manuale]("+BASE+"mappe-guide/)",""]
    out+=["### Piano leggero per i primi follower (solo contributi utili)","",
          "1. **Scegli una domanda reale su GTA VI** dalla coda verificata X #48 oppure",
          " da ricerca X manuale. Non dichiarare un tweet verificato senza permalink.",
          "2. **Rispondi con una soluzione concreta**: indica dove aprire il marker",
          " della casa di Jason o la scheda dello Starlet Motel solo se è pertinente",
          " alla domanda, specificando che non è il pin preciso di un collezionabile.",
          "3. **Pubblica al massimo una bozza originale** tra quelle sopra nel",
          " normale piano editoriale; usa una copertina diversa dalla precedente",
          " e rispetta il limite di 235 caratteri per un post con foto.",
          "4. **Osserva le metriche per sette giorni**: impression solo da X/Buffer",
          " quando davvero disponibili, aperture di mappe/CTA solo da Umami,",
          " follower solo dal profilo X. Non sono la stessa metrica e non",
          " si possono attribuire automaticamente l'una all'altra.", "",
          "### Misure distinte: Umami non è X","",
          "Umami: game-map-load-intent, game-map-named-search-intent, "
          "game-map-curated-link-open-intent, game-map-external-open, game-map-follow-intent. "
          "Un'intenzione non dimostra caricamento dell'iframe, un pin trovato o un follower.",
          "X: visite profilo e follower nuovi si registrano solo quando osservati realmente su X.",""]
    if metrics is None:
        out+=["**Nessuna riga manuale disponibile:** metriche non disponibili, non zero.",""]
    else:
        out+=["**Data registrata:** "+metrics["date"]+
              " (valori immessi dal proprietario, non raccolti dal bot).",""]
        for key in FIELDS[1:]:
            value=metrics[key]
            out+=["- "+key+": "+(str(value) if value is not None else "non disponibile")]
        out+=[""]
    out+=["Dashboard: [Umami](https://cloud.umami.is/) · [X](https://x.com/xFederiko11) · "
          "[Buffer](https://publish.buffer.com/) · [Mappe](https://xfederiko11.github.io/gta-6/mappe-guide/).",
          "Fonti embed: [Vice Map](https://vice-map.com/embed) e [GTA6.city](https://gta6.city/embed).",""]
    return "\n".join(out)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="previews/gta6-map-growth-v1.md")
    parser.add_argument("--insert-into")
    parser.add_argument("--metrics",default=str(MANUAL))
    args=parser.parse_args()
    try:
        fetch_public()
        live=True
    except (HTTPError,URLError,OSError,ValueError,TypeError,json.JSONDecodeError,TimeoutError):
        live=False
    values=metric_row(Path(args.metrics))
    body=markdown(live,values)
    destination=Path(args.output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(body+"\n",encoding="utf-8")
    if args.insert_into:
        issue=Path(args.insert_into)
        if not issue.is_file():raise ValueError("Expected existing organic growth digest")
        text=issue.read_text(encoding="utf-8")
        anchor="## Profilo: stato osservato dagli screenshot"
        if text.count(anchor)!=1:raise ValueError("Unexpected growth digest format")
        issue.write_text(text.replace(anchor,body+"\n"+anchor),encoding="utf-8")
    print("MAP_GROWTH", "public_verified="+str(live),
          "proposed_manual_posts="+str(len(DRAFTS) if live else 0),
          "manual_metrics="+str(values is not None),"paid_x_api=0","buffer_mutations=0")


if __name__=="__main__":main()
