"""Read-only Buffer queue health; never creates posts or spends X API credits."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import re
import argparse
from buffer_publisher import BufferClient, BufferAPIError, BufferConfigurationError, ORGANIZATIONS_QUERY

POST_QUERY = """query BufferHealth($orgId:OrganizationId!,$channelId:ChannelId!) {
  sent:posts(first:15,input:{organizationId:$orgId,
    filter:{status:[sent],channelIds:[$channelId]},
    sort:[{field:dueAt,direction:desc}]}) { edges { node { id status dueAt externalLink } } }
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

def summarize(data,*,paused=False):
    result={"status":"ok","is_queue_paused":bool(paused),"sample_limit_per_state":15}
    for state in ("sent","scheduled","error"):
        container=data.get(state)
        if not isinstance(container,dict) or not isinstance(container.get("edges"),list):
            raise ValueError("Buffer post status query incomplete")
        if len(container["edges"])>15:
            raise ValueError("Unexpected Buffer post count")
        posts=[]
        for edge in container["edges"]:
            node=edge.get("node") if isinstance(edge,dict) else None
            if not isinstance(node,dict) or node.get("status")!=state:
                raise ValueError("Unexpected Buffer post status")
            due=node.get("dueAt")
            url=node.get("externalLink")
            if due is not None and not isinstance(due,str):
                raise ValueError("Invalid dueAt")
            if url is not None and not isinstance(url,str):
                raise ValueError("Invalid externalLink")
            posts.append({"dueAt":due,"externalLink":url})
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
            lines += ["Ultimo post Sent nel campione: "+str(last["dueAt"] or "data non disponibile")]
            url=last["externalLink"] or ""
            trusted=verified_account_post_link(url)
            if trusted:
                lines += ["[Apri collegamento Buffer al post su X]("+trusted+")"]
            elif url:
                lines += ["Buffer ha restituito un link con handle non verificabile: "
                          "controlla il post direttamente nella dashboard Buffer."]
            lines += [""]
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
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(result,datetime.now(timezone.utc)),encoding="utf-8")
    print("BUFFER_QUEUE_HEALTH",result["status"],"sent",len(result["sent"]),
          "scheduled",len(result["scheduled"]),"errors",len(result["error"]))

if __name__=="__main__":
    main()
