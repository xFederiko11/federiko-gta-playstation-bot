"""Read-only photo leads from the owner's existing public repository inputs.

No image downloads, X requests, inferred rights, auto-approval, or posts.
Pin all JSON reads to one observed commit. The deployed site's operational
backlog is deliberately private to the build and must stay excluded.
"""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode,urlsplit
import requests

API="https://api.github.com/repos/xFederiko11/gta-6/commits/main"
RAW="https://raw.githubusercontent.com/xFederiko11/gta-6/"
BASE="https://xfederiko11.github.io/gta-6/"
INPUTS={
    "guides":"data/guide.json",
    "visual_guides":"data/visual_guides.json",
    "requests":"data/visual_requests.json",
    "approved":"data/approved_screenshots_v4.json",
    "provenance":"data/photo_provenance_review_v3.json",
    "references":"data/step_image_sources_v1.json",
    "vehicles":"data/vehicle_catalog_v1.json",
    "archive":"site/assets/rockstar/gta-vi/manifest.json",
}
MAX_BYTES=2_000_000
HIGH={"meditazione-capitolo-1","prima-persona-glitch-ps5","poligoni-concentrazione","soldi-facili-capitolo-1"}
MEDIUM={"70-sfide-100-percento","soldi-2500-three-sheets-liquor","registrare-auto-personale","scansionare-veicoli"}
# Broad topic leads are deliberately distinct from exact vehicle identities.
TOPIC_SUBJECTS={
    "registrare-auto-personale":{"Rideout Customs","Safehouse Vehicles"},
    "scansionare-veicoli":{"Wyman Car Collection","Grotti Cheetah"},
    "studiare-animali":{"Grassrivers","Leonida Keys","Mount Kalaga National Park"},
}
SOURCE_HOSTS={"www.powerpyx.com","www.pushsquare.com","www.gtabase.com","gta6data.com",
              "www.rockstargames.com","support.rockstargames.com","gta6gps.com",
              "www.youtube.com","youtu.be","www.ign.com","insider-gaming.com",
              "www.insider-gaming.com","www.gamesradar.com"}

def read_json(url, session=None):
    if url != API and not any(re.fullmatch(re.escape(RAW)+r"[0-9a-f]{40}/"+re.escape(path),url)
                               for path in INPUTS.values()):
        raise ValueError("Outside fixed source inputs")
    with (session or requests).get(url,stream=True,timeout=(4,10),allow_redirects=False,
                headers={"Accept":"application/json","User-Agent":"GTA6Italia-PhotoDiscovery/1.0"}) as response:
        if response.status_code!=200 or response.url!=url:
            raise ValueError("Unavailable source snapshot")
        body=bytearray()
        for part in response.iter_content(16384):
            body.extend(part)
            if len(body)>MAX_BYTES:
                raise ValueError("Oversized source")
        data=json.loads(body)
        if not isinstance(data,dict):raise ValueError("Expected JSON object")
        return data

def snapshot(read=read_json):
    revision=read(API).get("sha")
    if not isinstance(revision,str) or not re.fullmatch(r"[0-9a-f]{40}",revision):
        raise ValueError("Invalid site revision")
    return revision,{key:read(RAW+revision+"/"+path) for key,path in INPUTS.items()}

def safe_source(value):
    if not isinstance(value,str):return None
    try:
        p=urlsplit(value)
        if (p.scheme=="https" and p.hostname in SOURCE_HOSTS and p.port in (None,443)
                and not p.username and not p.password and len(value)<=500):
            return value
    except ValueError:pass
    return None

def normalize(text):
    return " ".join(re.findall(r"[a-z0-9]+",str(text).casefold()))

def discover(data):
    guides={g["id"]:g for g in data["guides"]["guides"]+data["visual_guides"]["guides"]}
    requests_by_guide=data["requests"]["guides"]
    if set(guides)!=set(requests_by_guide) or len(guides)!=11 or any(len(v)!=5 for v in requests_by_guide.values()):
        raise ValueError("Guide requests changed; review schema")
    registry=data["approved"]
    if registry.get("schema")!="gta6-approved-screenshots-v4" or not isinstance(registry.get("photos"),list):
        raise ValueError("Invalid approval registry")
    # Metadata alone does not establish valid approval or a live binary.
    recorded={(x["guide_id"],x["role"]) for x in registry["photos"] if
              x.get("guide_id") in guides and type(x.get("role")) is int and 1<=x["role"]<=5
              and x.get("human_reviewed") is True and x.get("author_confirmed") is True
              and x.get("published") is True and x.get("gameplay_only") is True
              and x.get("no_real_people") is True}
    assets=data["archive"]["assets"]
    if len(assets)!=data["archive"]["asset_count"] or not assets:
        raise ValueError("Incomplete Rockstar archive")
    hashes=set()
    for item in assets:
        digest=item.get("sha256","")
        if not re.fullmatch(r"[a-f0-9]{64}",digest) or digest in hashes or item.get("credit")!="Rockstar Games":
            raise ValueError("Invalid or repeated archive identity")
        hashes.add(digest)
    exact=[]
    for car in data["vehicles"]["items"]:
        if car.get("status")!="Verificata" or car.get("spoiler"):continue
        model=normalize(car["name"])
        for item in assets:
            if normalize(item["subject"])==model:
                exact.append({"model":car["name"],"asset":item["title"],"kind":"exact_subject_metadata",
                              "review":"visual_and_rights_required"})
    topic=[]
    for guide,subjects in TOPIC_SUBJECTS.items():
        for item in assets:
            if item["subject"] in subjects and min(item["width"],item["height"])>=630:
                topic.append({"guide":guide,"asset":item["title"],"kind":"promotional_context_only",
                              "review":"visual_and_rights_required"})
    refs=[]
    seen=set()
    for gid,steps in data["references"]["guides"].items():
        for step,entry in steps.items():
            url=safe_source(entry.get("source"))
            if url and (gid,step,url) not in seen:
                seen.add((gid,step,url))
                refs.append({"guide":gid,"step":step,"url":url,"kind":"source_page_only"})
    for entry in data["provenance"].get("leads",[]):
        url=safe_source(entry.get("url"))
        if url:
            refs.append({"guide":entry["guide"],"url":url,"kind":"source_page_only"})
    # Include the existing verified guide source lists, even when they have no
    # manually indexed image. They remain links, never approved screenshots.
    seen_pages={(row["guide"],row["url"]) for row in refs}
    for gid,guide in guides.items():
        for candidate in [guide.get("source_url")]+guide.get("extra_sources",[]):
            url=safe_source(candidate)
            if url and (gid,url) not in seen_pages:
                seen_pages.add((gid,url))
                refs.append({"guide":gid,"url":url,"kind":"source_page_only"})
    tasks=[]
    for gid,roles in requests_by_guide.items():
        for i,desc in enumerate(roles,1):
            priority="alta" if gid in HIGH or gid in MEDIUM and i<=2 else "media" if gid in MEDIUM or i<=2 else "normale"
            if (gid,i) not in recorded:
                tasks.append({"guide":gid,"role":i,"description":desc,"priority":priority})
    tasks.sort(key=lambda x:({"alta":0,"media":1,"normale":2}[x["priority"]],x["guide"],x["role"]))
    return {"archive_count":len(assets),"requested_roles":55,"registry_rows":len(registry["photos"]),
            "roles_with_recorded_approval":len(recorded),"unrecorded_roles":len(tasks),
            "exact_model_leads":exact,"context_leads":topic,"source_references":refs,"tasks":tasks,
            "new_approvals":0,"downloaded_images":0,"posts":0}

def report(data,revision):
    lines=["# Ricerca fotografica — sola lettura","",
           "Snapshot GitHub del sito: "+revision+" (dati sorgente, non verifica del deploy).",
           "Metadati dell'archivio e link non provano paternità, pertinenza visiva o licenza.","",
           "- Originali catalogati: "+str(data["archive_count"]),
           "- Ruoli richiesti: "+str(data["requested_roles"]),
           "- Righe nel registro delle approvazioni: "+str(data["registry_rows"])+" (non riconfermate live)",
           "- Ruoli senza approvazione registrata: "+str(data["unrecorded_roles"]),
           "- Corrispondenze esatte per modello da verificare: "+str(len(data["exact_model_leads"])),
           "- Possibili contesti promozionali da verificare: "+str(len(data["context_leads"])),
           "- Riferimenti a pagine fonte, non foto autorizzate: "+str(len(data["source_references"])),
           "- Nuove foto approvate/scaricate/post: 0/0/0.","",
           "## Priorità da documentare"]
    for item in data["tasks"][:10]:
        lines.append("- "+item["priority"]+" · "+item["guide"]+" · ruolo "+str(item["role"])+" — "+item["description"])
    lines.extend(["","## Candidati da esaminare (nessun riuso automatico)"])
    for item in data["exact_model_leads"]+data["context_leads"]:
        lines.append("- "+item.get("model",item.get("guide",""))+" · "+item["asset"]+" · "+item["kind"])
    lines.extend(["","## Riferimenti alla fonte (nessun download)"])
    for item in data["source_references"][:60]:
        lines.append("- "+item["guide"]+" · "+item["url"])
    return "\n".join(lines)+"\n"

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="previews/gta6-photo-backlog-v1.md")
    parser.add_argument("--append")
    args=parser.parse_args()
    try:
        revision,inputs=snapshot()
        result=discover(inputs)
        body=report(result,revision)
        print("PHOTO_DISCOVERY_OK archive",result["archive_count"],"roles",result["requested_roles"],
              "registry",result["registry_rows"],"exact_models",len(result["exact_model_leads"]),
              "context",len(result["context_leads"]),"source_links",len(result["source_references"]),
              "new_approvals=0 downloads=0 buffer_posts=0")
    except (requests.RequestException,OSError,KeyError,TypeError,ValueError) as exc:
        body="# Ricerca fotografica non disponibile\n\nSnapshot non verificato; nessuna approvazione o foto inventata.\n"
        print("PHOTO_DISCOVERY_UNAVAILABLE",type(exc).__name__)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(body,encoding="utf-8")
    if args.append:
        with Path(args.append).open("a",encoding="utf-8") as out:out.write("\n---\n"+body)

if __name__=="__main__":main()
