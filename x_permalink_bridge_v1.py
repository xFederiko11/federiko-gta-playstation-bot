"""Read-only, bounded Buffer -> real X permalink bridge for GTA VI website.

Buffer post IDs are NEVER X status IDs. A link is exported only when Buffer
reports: verified xFederiko11 channel, sent status, sentAt, externalLink with
an actual numeric X status ID, and an exact owned article match. No mutations,
posts, retries or scraping X. Existing verified links survive pagination.
Official docs: https://developers.buffer.com/reference.html (Post.externalLink).
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit
import json,re
from buffer_publisher import BufferClient

STATE=Path(".state/editorial-autopilot-v137.json")
OUTPUT=Path("data/x-permalinks-v1.json")
BASE="https://xfederiko11.github.io/gta-6/"
SCHEMA="verified-buffer-x-permalinks-v1"
MAX_PAGES=2
PAGE_SIZE=80
POSTS_QUERY="""query SiteXPosts($org: OrganizationId!, $chan: ChannelId!, $after: String) {
 posts(first: 80, after: $after, input: {
   organizationId: $org
   filter: {status: [sent], channelIds: [$chan]}
 }) {
   edges { node { id status channelId channelService text sentAt externalLink } }
   pageInfo { hasNextPage endCursor }
 }
}"""
ARTICLE_RE=re.compile(r"^https://xfederiko11\.github\.io/gta-6/(?:[a-z0-9-]+/)*$")
MENTION_RE=re.compile(r"https://xfederiko11\.github\.io/gta-6/(?:[a-z0-9-]+/)*")
STATUS_RE=re.compile(r"/(?:xfederiko11|i/web|[0-9]{8,25})/status/([0-9]{8,25})/?",re.I)

def clean_article(url):
    if not isinstance(url,str) or len(url)>230 or any(ord(ch)<33 for ch in url):
        return None
    try:u=urlsplit(url)
    except ValueError:return None
    if (u.scheme!="https" or u.hostname!="xfederiko11.github.io" or u.port not in (None,443)
        or u.username or u.password or u.query or u.fragment or not ARTICLE_RE.fullmatch(url)):
        return None
    return url

def real_x_permalink(link):
    """Normalize only an exact Buffer-provided status path on the owned channel."""
    if not isinstance(link,str) or any(ord(ch)<33 for ch in link) or len(link)>250:
        return None
    try:u=urlsplit(link)
    except ValueError:return None
    if (u.scheme!="https" or u.hostname not in {"x.com","www.x.com","twitter.com","www.twitter.com"}
        or u.port not in (None,443) or u.username or u.password or u.query or u.fragment):
        return None
    match=STATUS_RE.fullmatch(u.path)
    if not match:return None
    # Buffer's verified channel proves X ownership even if link used /i/web/.
    return "https://x.com/xFederiko11/status/"+match.group(1)

def parse_sent(value,now):
    try:
        date=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if date.tzinfo is None:return None
    except (ValueError,TypeError):
        return None
    date=date.astimezone(timezone.utc)
    if not datetime(2026,11,17,tzinfo=timezone.utc)<=date<=now+timedelta(minutes=5):
        return None
    return date.isoformat().replace("+00:00","Z")

def ledger_map(state):
    entries=state.get("entries")
    if not isinstance(entries,dict):raise ValueError("Missing editorial ledger")
    result={}
    for item in entries.values():
        if not isinstance(item,dict) or item.get("status")=="rejected":continue
        url=clean_article(item.get("url"))
        bid=item.get("buffer_id")
        if url and isinstance(bid,str) and re.fullmatch(r"[a-z0-9]{15,40}",bid):
            first=item.get("thread",[None])
            first=first[0] if isinstance(first,list) and first else None
            original=first or item.get("text") or ""
            result[bid]={"article_url":url,"title":str(item.get("title") or "")[:140],
                         "first_text":str(original)}
    return result

def comparable(a):
    return " ".join(str(a).split()).casefold()

def node_match(node,known):
    expected=comparable(known.get("first_text"))
    actual=comparable(node.get("text"))
    # Own posts should match the first paragraph; otherwise no URL attribution.
    return len(expected)>=15 and len(actual)>=15 and (expected[:55]==actual[:55] or expected==actual)

def records(nodes,ledger,channel_id,*,now):
    matches=[]
    for node in nodes:
        if not isinstance(node,dict) or node.get("channelId")!=channel_id or node.get("channelService")!="twitter":
            continue
        if node.get("status")!="sent":continue
        link=real_x_permalink(node.get("externalLink"))
        sent=parse_sent(node.get("sentAt"),now)
        if not link or not sent:continue
        bid=str(node.get("id") or "")
        entry=ledger.get(bid)
        if entry:
            if not node_match(node,entry):continue
            url=entry["article_url"]
            title=entry["title"]
        else:
            urls={clean_article(x) for x in MENTION_RE.findall(str(node.get("text") or ""))}
            urls.discard(None)
            if len(urls)!=1:continue
            url=next(iter(urls))
            title=""
        text=str(node.get("text") or "").strip()
        if len(text)<12:continue
        matches.append({"article_url":url,"x_url":link,"buffer_id":bid,"sent_at":sent,
                        "excerpt":text[:440],"title":title,
                        "verified_by":"Buffer sent Post.externalLink on verified @xFederiko11 channel"})
    return matches

def merge(existing,new,*,now):
    result={}
    for item in list(existing)+list(new):
        if not isinstance(item,dict):continue
        url=clean_article(item.get("article_url"))
        xurl=real_x_permalink(item.get("x_url"))
        when=parse_sent(item.get("sent_at"),now)
        if not url or not xurl or not when or not isinstance(item.get("buffer_id"),str):
            continue
        key=(url,xurl)
        result[key]={**item,"article_url":url,"x_url":xurl,"sent_at":when}
    ordered=sorted(result.values(),key=lambda x:x["sent_at"],reverse=True)
    return ordered[:200]

def read_existing(path=OUTPUT):
    if not path.is_file():return []
    try:
        content=json.loads(path.read_text(encoding="utf-8"))
        if content.get("schema")!=SCHEMA:return []
        return content.get("posts") if isinstance(content.get("posts"),list) else []
    except (OSError,ValueError,TypeError):return []

def collect(state,*,client,now=None,previous=None,max_pages=MAX_PAGES):
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    channel=client.verify_destination()
    if channel.get("service")!="twitter":raise ValueError("Expected verified X channel")
    candidates=client.list_channels()
    matches=[c for c in candidates if c.get("id")==client.channel_id
             and c.get("service")=="twitter"]
    if len(matches)!=1:raise ValueError("Cannot prove owning Buffer organization")
    org=matches[0]["organization_id"]
    ledger=ledger_map(state)
    nodes=[]
    cursor=None
    for _ in range(max_pages):
        result=client._graphql(POSTS_QUERY,{"org":org,"chan":client.channel_id,"after":cursor}).get("posts")
        if not isinstance(result,dict) or not isinstance(result.get("edges"),list):
            raise ValueError("Malformed Buffer posts query")
        nodes.extend(edge.get("node") for edge in result["edges"] if isinstance(edge,dict))
        page=result.get("pageInfo") or {}
        if not page.get("hasNextPage"):break
        cursor=page.get("endCursor")
        if not isinstance(cursor,str) or not cursor:raise ValueError("Invalid Buffer cursor")
    gathered=records(nodes,ledger,client.channel_id,now=now)
    return {"schema":SCHEMA,"checked_utc":now.isoformat().replace("+00:00","Z"),
            "posts":merge(previous or [],gathered,now=now),
            "matched_this_run":len(gathered),
            "note":"Buffer delivery receipts verified; live X existence and engagement are not independently checked"}

def main():
    import os
    state=json.loads(STATE.read_text(encoding="utf-8"))
    client=BufferClient(expected_username="xFederiko11")
    data=collect(state,client=client,previous=read_existing())
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    result=json.dumps(data,ensure_ascii=False,indent=2)+"\n"
    OUTPUT.write_text(result,encoding="utf-8")
    print("BUFFER_X_PERMALINKS_VERIFIED",len(data["posts"]),
          "matched_this_run",data["matched_this_run"],"queries_bounded",MAX_PAGES+3)

if __name__=="__main__":
    main()
