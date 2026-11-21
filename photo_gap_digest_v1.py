"""Daily read-only digest of real GTA VI PS5 screenshot gaps.

Consumes ONLY the public, versioned and validated gta-6 site JSON. It does not
discover posts on X, touch Buffer, publish images or treat editorial photo
requirements as 55 missing gameplay proofs. On network failure it reports
"unavailable" and never invents progress or changes a public page.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen,Request,HTTPRedirectHandler,build_opener
from urllib.error import URLError,HTTPError

SOURCE="https://xfederiko11.github.io/gta-6/photo-backlog-v5.json"
COVER="https://xfederiko11.github.io/gta-6/screenshot-ps5/priorita/"
SCHEMA="gta6-photo-coverage-v5"
MAX_SIZE=150_000
PRIORITIES={"alta","media","normale"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):return None


def validate(data):
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA or data.get("total_requests")!=55:
        raise ValueError("Unexpected public photo-backlog schema/size")
    entries=data.get("tasks")
    if not isinstance(entries,list) or len(entries)!=55:
        raise ValueError("Missing photo tasks")
    seen=set();roles=defaultdict(set);approved=0
    for record in entries:
        if not isinstance(record,dict):
            raise ValueError("Unexpected task row")
        gid=record.get("guide_id")
        role=record.get("role")
        ident=record.get("id")
        if (not isinstance(gid,str) or not gid.replace("-","").isalnum() or
            type(role) is not int or not 1<=role<=5 or ident!=gid+"-"+str(role) or ident in seen):
            raise ValueError("Unsafe photo task id")
        seen.add(ident);roles[gid].add(role)
        if record.get("priority") not in PRIORITIES or record.get("status") not in {"approvato","da documentare"}:
            raise ValueError("Invalid role status or priority")
        title,description=record.get("guide_title"),record.get("description")
        if not isinstance(title,str) or not 4<=len(title)<=170 or not isinstance(description,str) or not 12<=len(description)<=220:
            raise ValueError("Unusable guide title or role")
        guide=record.get("guide_url")
        submit=record.get("submission_url")
        for link,part in ((guide,"/gta-6/"),(submit,"/gta-6/screenshot-ps5/invia/")):
            parsed=urlsplit(str(link))
            if (parsed.scheme!="https" or parsed.hostname!="xfederiko11.github.io"
                or parsed.username or parsed.password or parsed.port not in (None,443)
                or not parsed.path.startswith(part) or parsed.fragment):
                raise ValueError("Unsafe role link")
        good=record.get("status")=="approvato"
        if record.get("rights_verified") is not good or record.get("screenshot_verified") is not good:
            raise ValueError("Unlicensed photos cannot be auto-approved")
        if good:approved+=1
    if len(roles)!=11 or any(n!={1,2,3,4,5} for n in roles.values()):
        raise ValueError("Each guide must have five genuine roles")
    if (data.get("approved_new_community_screenshots")!=approved or
        data.get("unapproved_roles")!=55-approved or
        data.get("human_review_required") is not True or
        data.get("automatic_social_posting") is not False):
        raise ValueError("Fake approval or automated social posting flag")
    return sorted([x for x in entries if x["status"]!="approvato"],
                  key=lambda x:({"alta":0,"media":1,"normale":2}[x["priority"]],
                                x["guide_id"],x["role"]))


def fetch_public(open_fn=None):
    safe=open_fn or build_opener(NoRedirect()).open
    request=Request(SOURCE,headers={"Accept":"application/json","User-Agent":"GTA6Italia-PhotoGap/1.0"})
    with safe(request,timeout=12) as response:
        if response.geturl()!=SOURCE:
            raise ValueError("Changed trusted JSON endpoint")
        if response.headers.get("Content-Type","").split(";")[0].strip().lower() not in {"application/json","text/plain","application/octet-stream"}:
            raise ValueError("Unexpected public JSON response")
        binary=response.read(MAX_SIZE+1)
    if len(binary)>MAX_SIZE:
        raise ValueError("Oversized public backlog")
    data=json.loads(binary)
    validate(data)
    return data


def markdown(data):
    rows=validate(data)
    lines=["<!-- PHOTO_BACKLOG_PUBLIC_VERIFIED -->",
           "## 55 screenshot PS5: priorità editoriali verificate sul sito","",
           "Origine: [checklist pubblica e modulo X]("+COVER+")",
           " · Nessuna fotografia, autorizzazione o trofeo viene confermato da questa lista.","",
           "- Ruoli editoriali descritti: **55** (11 guide × 5 passaggi)",
           "- Foto nuove della community approvate: **"+str(data["approved_new_community_screenshots"])+"**",
           "- Ruoli senza nuova foto approvata: **"+str(data["unapproved_roles"])+"**",
           "- Foto già attribuite in inventario (permessi separati): **"+str(data["existing_attributed_editorial_screenshots"])+"**",
           "",
           "### Prossimi dieci passaggi da fotografare",
           ""]
    for row in rows[:10]:
        lines.append("- **"+escape(row["priority"].upper())+"** — "+escape(row["guide_title"])+
                     " · passo "+str(row["role"])+" · "+escape(row["description"])+
                     " ([proponi su X]("+row["submission_url"]+"))")
    if not rows:lines.append("Tutti i 55 ruoli hanno una foto nuova approvata.")
    lines+=["","**Regola di pubblicazione:** aprire il post originale, verificare screenshot",
            "e origine, accertare permesso specifico e approvare manualmente prima di",
            "modificare l'archivio WebP del sito. Il bot non copia immagini né",
            "pubblica sui social e non interpreta gli artwork come prove di gameplay.",""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="previews/gta6-photo-backlog-v1.md")
    p.add_argument("--append")
    a=p.parse_args()
    error=None
    try:
        data=fetch_public()
        body=markdown(data)
        status="PHOTO_GAP_SOURCE_OK"
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as ex:
        status="PHOTO_GAP_SOURCE_UNAVAILABLE"
        error=type(ex).__name__
        body=("## Stato delle richieste fotografiche GTA VI\n\n"
              "La checklist live non è stata verificata in questa esecuzione, "
              "quindi non vengono inventati ruoli approvati o nuove foto.\n\n"
              "[Apri la checklist sul sito]("+COVER+")\n")
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(body+"\n",encoding="utf-8")
    if a.append:
        dest2=Path(a.append)
        if not dest2.is_file():raise ValueError("Existing photo review digest missing")
        with dest2.open("a",encoding="utf-8") as stream:
            stream.write("\n---\n"+body+"\n")
    print(status,("error="+error if error else "roles=55"),
          "approved_not_inferred=true", "x_requests=0", "buffer_posts=0")


if __name__=="__main__":main()
