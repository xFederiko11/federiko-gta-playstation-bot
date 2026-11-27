"""Read-only Buffer queue health; never creates posts or spends X API credits."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit
import re
import argparse
from buffer_publisher import BufferClient, BufferAPIError, BufferConfigurationError, ORGANIZATIONS_QUERY
from buffer_slot_reconcile_v1 import from_ledger, aware
from buffer_delivery_receipts_v1 import _post_image_attached

POST_QUERY = """query BufferHealth($orgId:OrganizationId!,$channelId:ChannelId!) {
  sent:posts(first:15,input:{organizationId:$orgId,
    filter:{status:[sent],channelIds:[$channelId]},
    sort:[{field:dueAt,direction:desc}]}) { edges { node {
      id status dueAt sentAt externalLink
      assets { mimeType source }
      metadata { ... on TwitterPostMetadata { thread { assets { mimeType source } } } }
    } } }
  scheduled:posts(first:15,input:{organizationId:$orgId,
    filter:{status:[scheduled],channelIds:[$channelId]},
    sort:[{field:dueAt,direction:asc}]}) { edges { node { id status dueAt externalLink } } }
  error:posts(first:15,input:{organizationId:$orgId,
    filter:{status:[error],channelIds:[$channelId]},
    sort:[{field:dueAt,direction:desc}]}) { edges { node { id status dueAt externalLink } } }
}"""
CHANNELS_URL="https://publish.buffer.com/settings/channels"


def verified_account_post_link(value: str | None) -> str | None:
    """Only render canonical links already bound to the verified channel handle.

    Buffer sometimes returns account numeric IDs instead of an X username:
    those URLs should not be described as publicly confirmed X tweets.
    """
    if not isinstance(value,str):
        return None
    try:
        url=urlsplit(value)
    except ValueError:
        return None
    if (url.scheme!="https" or url.hostname not in ("x.com","www.x.com",
         "twitter.com","www.twitter.com") or url.username or url.password
         or url.query or url.fragment or url.port not in (None,443)):
        return None
    if not re.fullmatch(r"/xFederiko11/status/[0-9]{8,25}/?",url.path,re.I):
        return None
    return value

def observed_image(post):
    """True for a Buffer image attachment, False only for an inspectable empty/non-image model."""
    if _post_image_attached(post):
        return True
    if not isinstance(post.get("assets"),list) or "metadata" not in post:
        return None
    metadata=post["metadata"]
    if metadata is None or metadata=={}:
        return False
    if isinstance(metadata,dict) and isinstance(metadata.get("thread"),list):
        thread=metadata["thread"]
        if not thread or (isinstance(thread[0],dict) and isinstance(thread[0].get("assets"),list)):
            return False
    return None

def summarize(data,*,paused=False):
    result={"status":"ok","is_queue_paused":bool(paused),"sample_limit_per_state":15}
    for state in ("sent","scheduled","error"):
        container=data.get(state)
        if not isinstance(container,dict) or not isinstance(container.get("edges"),list):
            raise ValueError("Buffer post status query incomplete")
        if len(container["edges"])>15:
            raise ValueError("Unexpected Buffer post count")
        posts=[]
        seen=set()
        for edge in container["edges"]:
            node=edge.get("node") if isinstance(edge,dict) else None
            if not isinstance(node,dict) or node.get("status")!=state:
                raise ValueError("Unexpected Buffer post status")
            bid=node.get("id")
            if not isinstance(bid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,80}",bid):
                raise ValueError("Invalid Buffer post ID in verified sample")
            due=node.get("dueAt")
            url=node.get("externalLink")
            if due is not None and not isinstance(due,str):
                raise ValueError("Invalid dueAt")
            if url is not None and not isinstance(url,str):
                raise ValueError("Invalid externalLink")
            if bid in seen:
                raise ValueError("Duplicate Buffer post ID in sample")
            seen.add(bid)
            record={"id":bid,"dueAt":due,"externalLink":url}
            if state=="sent":
                stamp=aware(node.get("sentAt"))
                record["sent_at"]=stamp.isoformat() if stamp else None
                record["buffer_image"]=observed_image(node)
            posts.append(record)
        result[state]=posts
    return result

def snapshot(*,client=None):
    try:
        c=client or BufferClient(expected_username="xFederiko11")
        dest=c.verify_destination()
        orgdata=c._graphql(ORGANIZATIONS_QUERY,{})
        orgs=(orgdata.get("account") or {}).get("organizations")
        if not isinstance(orgs,list) or len(orgs)!=1 or not isinstance(orgs[0],dict):
            raise ValueError("Ambiguous Buffer organization")
        orgid=str(orgs[0].get("id") or "")
        if not orgid:
            raise ValueError("Buffer organization ID missing")
        data=c._graphql(POST_QUERY,{"orgId":orgid,"channelId":c.channel_id})
        return summarize(data,paused=dest.get("isQueuePaused"))
    except (BufferAPIError,BufferConfigurationError,ValueError,TypeError,KeyError) as err:
        return {"status":"unavailable","reason":type(err).__name__,
                "sent":[],"scheduled":[],"error":[]}

def sent_sample_by_day(posts,now):
    """Observed records only: dueAt is not evidence of actual dispatch time."""
    rome=ZoneInfo("Europe/Rome")
    today=now.astimezone(rome).date()
    days={today-timedelta(days=n):{"sent":0,"image":0,"no_image":0,"unknown_image":0} for n in (0,1)}
    missing=0
    for row in posts:
        stamp=aware(row.get("sent_at"))
        if stamp is None or stamp>now.astimezone(timezone.utc):
            missing+=1
            continue
        day=stamp.astimezone(rome).date()
        if day not in days:
            continue
        item=days[day]
        item["sent"]+=1
        asset=row.get("buffer_image")
        item["image" if asset is True else "no_image" if asset is False else "unknown_image"]+=1
    return days,missing

def photo_readiness():
    """Count exact reviewed records; never infer permission from an image or source."""
    from photo_rights_v1 import load
    records=load()
    pages={url for url,_,_ in records}
    return len(records),len(pages)

def render_photo_readiness():
    records,pages=photo_readiness()
    lines=["## Disponibilità foto per nuovi post","",
           "Record di riutilizzo specifico validi nel registro: "+str(records)+".",
           "Articoli distinti con almeno un record: "+str(pages)+"."]
    if not pages:
        lines += ["**Allegati fotografici bloccati: nessuna copertina con riutilizzo documentato nel registro.**",
                  "Non allegare immagini senza prova di riutilizzo per lo specifico asset e canale.",
                  "La policy corrente ammette separatamente solo post con link fonte/video originali, verificati per singolo elemento e privi di foto caricate (source_link_only / official_video_link): non sono autorizzazioni per miniature o screenshot.",
                  "Acquisire e verificare screenshot originali PS5 prima di abilitare post fotografici."]
    else:
        lines += ["I record non sono post pronti: restano obbligatori verifica live di copertina/hash, pertinenza, deduplica e limiti editoriali."]
    lines += ["Registro vuoto, mancante o non valido = nessuna autorizzazione operativa. Nessun URL degli asset o prova privata esposta.",""]
    return "\n".join(lines)

def render(snapshot_data,now):
    if now.tzinfo is None:
        raise ValueError("Aware date required")
    lines=["# GTA VI - Audit coda Buffer/X","",
           "Controllo API Buffer in sola lettura; non invia, ritenta o rischedula post.",
           "Controllo UTC: "+now.astimezone(timezone.utc).isoformat(),""]
    if snapshot_data["status"]=="ok":
        lines += ["## Risultati verificati dall'API Buffer","",
                  "Campione degli ultimi 15 post per ciascuno stato, NON totali storici.",
                  "- Sent: "+str(len(snapshot_data["sent"])),
                  "- Scheduled: "+str(len(snapshot_data["scheduled"])),
                  "- Error: "+str(len(snapshot_data["error"])),
                  "- Coda sospesa: "+("sì" if snapshot_data["is_queue_paused"] else "nessuna pausa segnalata"),
                  ""]
        if snapshot_data["sent"]:
            last=snapshot_data["sent"][0]
            lines += ["Orario di invio (sentAt) del primo record Sent nel campione: "+str(last.get("sent_at") or "non disponibile")]
            url=last["externalLink"] or ""
            trusted=verified_account_post_link(url)
            if trusted:
                lines += ["[Apri collegamento Buffer al post su X]("+trusted+")"]
            elif url:
                lines += ["Buffer ha restituito un link con handle non verificabile: "
                          "controlla il post direttamente nella dashboard Buffer."]
            lines += [""]
        days,missing=sent_sample_by_day(snapshot_data["sent"],now)
        lines += ["## Invii osservati nel campione e allegati Buffer","",
                  "| Giorno (Roma) | Sent osservati (sentAt) | Immagine allegata | Nessuna immagine rilevata | Allegato non verificabile |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for day,row in days.items():
            lines.append("| "+day.isoformat()+" | "+" | ".join(str(row[k]) for k in ("sent","image","no_image","unknown_image"))+" |")
        lines += ["","Record Sent con orario assente, non valido o futuro: "+str(missing)+".",
                  "Il campione non è il totale giornaliero; nessuna conclusione automatica sull'obiettivo 5–6.",
                  "Gli allegati sono controllati nel modello Buffer, non sulla timeline pubblica X. Nessun URL degli asset viene pubblicato.",""]
        if snapshot_data["scheduled"]:
            lines += ["Prossimo Scheduled nel campione: "+
                      str(snapshot_data["scheduled"][0]["dueAt"] or "data non disponibile"),""]
        if snapshot_data["error"]:
            lines += ["Attenzione: post in Error nel campione. Non ripubblicare automaticamente.",
                      "Controllare Buffer Sent/Failed e connessione del canale.", ""]
    else:
        lines += ["## Dati Buffer non disponibili",
                  "Errore: "+str(snapshot_data.get("reason","non disponibile")),
                  "Non significa automaticamente che l'account X sia bloccato.",
                  "Controllare la connessione del canale, senza inviare post di prova.", ""]
    lines += ["Un post Sent in Buffer non dimostra da solo quante impression abbia su X.",
              "Nessuna modifica al profilo, al calendario o ai Quick Tips sospesi.","",
              "[Apri Buffer](https://publish.buffer.com/) · [Canali Buffer]("+CHANNELS_URL+")",""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result=snapshot()
    now=datetime.now(timezone.utc)
    report=render(result,now)
    report+='\n'+render_photo_readiness()+'\n'+from_ledger(result,now)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(report,encoding="utf-8")
    print("BUFFER_QUEUE_HEALTH",result["status"],"sent",len(result["sent"]),
          "scheduled",len(result["scheduled"]),"errors",len(result["error"]))

if __name__=="__main__":
    main()
