"""Optional, bounded Buffer insights diagnostic, never an X API or publishing action.

Uses the existing authorized personal Buffer API key only. Buffer's post
metrics are experimental and may require insightsRead, or be unavailable for X.
Failure/unavailable data NEVER means zero engagement or affects queue health.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import math
from pathlib import Path

from buffer_publisher import BufferClient, BufferAPIError, BufferConfigurationError

POST_METRICS = """query BufferMetrics($orgId:OrganizationId!,$channelId:ChannelId!) {
  posts(first:10,input:{organizationId:$orgId,
    filter:{status:[sent],channelIds:[$channelId]},
    sort:[{field:dueAt,direction:desc}]}) {
    edges { node { id status channelId metricsUpdatedAt
      metrics { type value unit } } }
  }
}"""
METRIC_NAMES = {
    "impressions":"Impression (Buffer)", "reactions":"Reazioni",
    "comments":"Commenti", "reposts":"Ripubblicazioni",
    "shares":"Condivisioni", "clicks":"Clic registrati da Buffer",
}
SOURCE = "Buffer API Post.metrics (experimental, personal API key, read only)"
MAX_POSTS = 10


def parse(payload, channel):
    """Count only actual reported values, not missing fields or predictions."""
    posts = payload.get("posts") if isinstance(payload,dict) else None
    edges = posts.get("edges") if isinstance(posts,dict) else None
    if not isinstance(edges,list) or len(edges)>MAX_POSTS:
        raise ValueError("Malformed Buffer insights response")
    totals = {}
    measured = 0
    updated = []
    for edge in edges:
        node = edge.get("node") if isinstance(edge,dict) else None
        if not isinstance(node,dict) or node.get("status")!="sent" or node.get("channelId")!=channel:
            raise ValueError("Unexpected insights channel or post state")
        stamp=node.get("metricsUpdatedAt")
        metrics=node.get("metrics")
        if stamp is None or metrics is None:
            continue
        if not isinstance(stamp,str) or not isinstance(metrics,list) or len(metrics)>40:
            raise ValueError("Malformed metrics fields")
        try:
            ts=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            if ts.tzinfo is None or ts>datetime.now(timezone.utc):
                raise ValueError("Invalid metrics timestamp")
        except (ValueError,TypeError,OverflowError):
            raise ValueError("Invalid metrics timestamp") from None
        measured += 1
        updated.append(ts.astimezone(timezone.utc))
        known=set()
        for metric in metrics:
            if not isinstance(metric,dict):raise ValueError("Invalid metric")
            typ=metric.get("type")
            if typ not in METRIC_NAMES:continue
            if typ in known:raise ValueError("Duplicate metric")
            known.add(typ)
            value=metric.get("value")
            if metric.get("unit")!="count" or isinstance(value,bool) or not isinstance(value,(int,float)):
                raise ValueError("Unexpected metric unit")
            if not math.isfinite(value) or value<0 or int(value)!=value:
                raise ValueError("Invalid metric value")
            totals[typ]=totals.get(typ,0)+int(value)
    return {"status":"available" if totals else "not_reported",
            "sampled_posts":len(edges),
            "posts_with_metrics_timestamp":measured,
            "totals_reported_subset":totals,
            "metrics_updated_at":max(updated).isoformat() if updated else None}


def snapshot(*,client=None):
    """Fail soft: never interfere with the existing Buffer posting workflow."""
    try:
        c=client or BufferClient(expected_username="xFederiko11")
        dest=c.verify_destination()
        if dest.get("service") not in (None,"twitter"):
            raise ValueError("Unexpected network")
        channels=c.list_channels()
        matches=[v for v in channels if isinstance(v,dict)
                 and v.get("id")==c.channel_id and v.get("service")=="twitter"]
        if len(matches)!=1:raise ValueError("Ambiguous channel")
        org=matches[0].get("organization_id")
        if not isinstance(org,str) or not org:
            raise ValueError("Missing Buffer organization")
        result=c._graphql(POST_METRICS,{"orgId":org,"channelId":c.channel_id})
        return parse(result,c.channel_id)
    except (BufferAPIError,BufferConfigurationError,ValueError,TypeError,KeyError) as err:
        return {"status":"unavailable","reason":type(err).__name__,
                "sampled_posts":None,"posts_with_metrics_timestamp":None,
                "totals_reported_subset":{},"metrics_updated_at":None}


def markdown(result,now):
    if now.tzinfo is None:raise ValueError("Timezone-aware clock required")
    lines=["## 📈 Buffer: diagnosi sperimentale delle performance X","",
        "Fonte: Buffer API personale, soli post Sent del canale verificato. "
        "Non sono follower, utenti unici o click attribuiti al sito.",
        "Controllo UTC: "+now.astimezone(timezone.utc).isoformat(), ""]
    if result["status"]=="available":
        lines.extend([
            f"Post Sent nel campione: {result['sampled_posts']} (massimo {MAX_POSTS}).",
            f"Post con aggiornamento metriche: {result['posts_with_metrics_timestamp']}.",
            f"Ultimo aggiornamento Buffer: {result['metrics_updated_at'] or 'non disponibile'}.",
            "Totali **solo sulle voci effettivamente ricevute nel campione**; "
            "metriche mancanti NON valgono zero:",""
        ])
        for key,label in METRIC_NAMES.items():
            if key in result["totals_reported_subset"]:
                lines.append(f"- {label}: {result['totals_reported_subset'][key]}")
    else:
        lines.extend([
            "Metriche X da Buffer: **non disponibili**, non significa 0 impression o engagement.",
            "Motivo tecnico: "+str(result.get("reason","nessun valore normalizzato restituito.")),
        ])
    lines.extend(["","Buffer documenta questa API come sperimentale e le metriche "
                  "possono arrivare con circa un giorno di ritardo. Non sono una "
                  "conferma della pubblicazione della seconda risposta nei thread.",
                  "Nessun accesso alle API X, nessun post creato o modificato.",
                  ""])
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--append-to",type=Path,required=True)
    args=p.parse_args()
    data=snapshot()
    with args.append_to.open("a",encoding="utf-8") as f:
        f.write("\n"+markdown(data,datetime.now(timezone.utc))+"\n")
    print("BUFFER_INSIGHTS_DIAGNOSTIC",data["status"],
          "sampled",data.get("sampled_posts"),
          "no_x_api=true","no_post_mutations=true")


if __name__=="__main__":
    main()
