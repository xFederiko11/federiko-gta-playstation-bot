"""Search Console query/page analytics: read-only, private output, no paid service."""
import argparse,json,math,os,re
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import quote,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from zoneinfo import ZoneInfo

SITE="https://xfederiko11.github.io/gta-6/"
SCOPE="https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URL="https://oauth2.googleapis.com/token"
QUERY_URL="https://www.googleapis.com/webmasters/v3/sites/"+quote(SITE,safe="")+"/searchAnalytics/query"
LIMIT=1000
MAX_PAGES=5
SAVE=re.compile(r"\b(?:salvar\w*|registr\w*|conservar\w*)\b",re.I)
CAR=re.compile(r"\b(?:auto|macchin\w*|veicol\w*)\b",re.I)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def request_json(url,body,headers):
    if url not in (TOKEN_URL,QUERY_URL):raise ValueError("Unexpected endpoint")
    req=Request(url,data=body,headers=headers,method="POST")
    with build_opener(NoRedirect()).open(req,timeout=20) as response:
        if response.status!=200 or response.geturl()!=url:raise ValueError("Unexpected response")
        raw=response.read(4_000_001)
    if len(raw)>4_000_000:raise ValueError("Oversized response")
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError("Unexpected document")
    return result

def access_token(env=os.environ,request=request_json):
    required=("GSC_CLIENT_ID","GSC_CLIENT_SECRET","GSC_REFRESH_TOKEN")
    if not all(env.get(k) for k in required):raise ValueError("Missing OAuth configuration")
    result=request(TOKEN_URL,urlencode({"client_id":env[required[0]],"client_secret":env[required[1]],"refresh_token":env[required[2]],"grant_type":"refresh_token","scope":SCOPE}).encode(),
                   {"Content-Type":"application/x-www-form-urlencoded"})
    token=result.get("access_token")
    if not isinstance(token,str) or not token or any(c in token for c in "\r\n"):raise ValueError("Invalid OAuth response")
    if result.get("scope") and set(result["scope"].split())!={SCOPE}:raise ValueError("Unexpected OAuth scopes")
    return token

def periods(now=None):
    now=now or datetime.now(ZoneInfo("America/Los_Angeles"))
    # Search Console uses Pacific Time; leave three full days for final data.
    end=now.date()-timedelta(days=3)
    return [(end-timedelta(days=6),end),(end-timedelta(days=13),end-timedelta(days=7))]

def fetch_rows(token,start,end,dimensions,request=request_json):
    if dimensions not in (["query","page"],["page"]):raise ValueError("Unexpected dimensions")
    rows=[];seen=set();truncated=False
    for page in range(MAX_PAGES):
        payload={"startDate":start.isoformat(),"endDate":end.isoformat(),"dimensions":dimensions,
                 "type":"web","dataState":"final","rowLimit":LIMIT,"startRow":page*LIMIT,
                 "dimensionFilterGroups":[{"groupType":"and","filters":[{"dimension":"country","operator":"equals","expression":"ita"}]}]}
        result=request(QUERY_URL,json.dumps(payload).encode(),{"Content-Type":"application/json","Authorization":"Bearer "+token})
        batch=result.get("rows",[])
        if not isinstance(batch,list) or len(batch)>LIMIT:raise ValueError("Invalid row batch")
        for row in batch:
            keys=row.get("keys",[])
            if not isinstance(keys,list) or len(keys)!=len(dimensions) or any(not isinstance(k,str) for k in keys):raise ValueError("Invalid row keys")
            if not keys[-1].startswith(SITE):continue
            if tuple(keys) in seen:continue
            seen.add(tuple(keys))
            clean={"keys":keys}
            for metric in ("clicks","impressions","ctr","position"):
                value=row.get(metric)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError("Invalid metric")
                clean[metric]=value
            if clean["ctr"]>1:raise ValueError("Invalid CTR")
            rows.append(clean)
        if len(batch)<LIMIT:break
        if page==MAX_PAGES-1:truncated=True
    return {"rows":sorted(rows,key=lambda r:(-r["impressions"],r["keys"])),"local_cap_reached":truncated}

def review(rows):
    ideas=[]
    for row in rows:
        query,page=row["keys"]
        if SAVE.search(query) and CAR.search(query):
            target=SITE+"salvare-auto/"
            if page!=target:ideas.append({"query":query,"observed_page":page,"canonical_target":target,
                  "impressions":row["impressions"],"position":row["position"],
                  "action":"Review internal links and canonical intent; no automatic title edits."})
    return ideas

def collect(token,now=None,request=request_json):
    windows=[]
    for start,end in periods(now):
        queries=fetch_rows(token,start,end,["query","page"],request)
        pages=fetch_rows(token,start,end,["page"],request)
        windows.append({"start":start.isoformat(),"end":end.isoformat(),"query_page":queries,"page":pages,
                        "review":review(queries["rows"])})
    return {"schema":"gsc-private-keyword-watch-v1","property":SITE,"market":"ita","data_state":"final",
            "limitations":"Top reported rows only; not national search volumes. Page aggregates and query rows are not additive.",
            "windows":windows}

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--force",action="store_true");a=p.parse_args()
    # Even explicit local execution refuses unless private context is declared.
    if os.environ.get("BOTX_GSC_PRIVATE")!="true":
        print("GSC_SKIPPED_PRIVATE_ONLY");return
    if not a.force and datetime.now(ZoneInfo("UTC")).hour>=4:
        print("GSC_SKIPPED_DAILY_WINDOW");return
    if not all(os.environ.get(k) for k in ("GSC_CLIENT_ID","GSC_CLIENT_SECRET","GSC_REFRESH_TOKEN")):
        print("GSC_SKIPPED_MISSING_CONFIGURATION");return
    try:
        data=collect(access_token())
        target=Path(a.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        # Never write into public previews or source files.
        if not target.resolve().is_relative_to(Path(".runtime/gsc-private").resolve()):raise ValueError("Private output path required")
        with target.open("w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
        print("GSC_PRIVATE_REPORT_OK")
    except Exception:
        # Do not log exception bodies, request headers, OAuth secrets or user queries.
        print("GSC_PRIVATE_REPORT_FAILED")
        raise SystemExit(1)

if __name__=="__main__":main()
