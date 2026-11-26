"""Bounded, read-only measurement of recent completed scheduled job durations.

Not a billing API or monthly forecast. Never creates workflows, writes to
GitHub or calls Buffer. Uses the existing GH_TOKEN supplied by health CI.
"""
from collections import defaultdict
from datetime import datetime
import json,math,subprocess,os,re
REPOSITORY="xFederiko11/federiko-gta-playstation-bot"
MAX_RUNS=12

def seconds(job):
    if job.get("conclusion")=="skipped":return None
    a,b=job.get("started_at"),job.get("completed_at")
    if not a or not b:return None
    delta=(datetime.fromisoformat(b.replace("Z","+00:00"))-datetime.fromisoformat(a.replace("Z","+00:00"))).total_seconds()
    if not math.isfinite(delta) or delta<0:raise ValueError("Invalid job duration")
    return int(delta)

def measure(runs,fetch_jobs):
    result={"runs":0,"jobs":0,"seconds":0,"rounded_minutes_model":0,"missing_job_times":0,"by_workflow":{}}
    counts=defaultdict(lambda:{"jobs":0,"seconds":0,"rounded_minutes_model":0})
    for run in runs[:MAX_RUNS]:
        if run.get("status")!="completed" or run.get("event")!="schedule":continue
        result["runs"]+=1
        for job in fetch_jobs(run["id"]):
            if job.get("conclusion")=="skipped":continue
            elapsed=seconds(job)
            if elapsed is None:
                result["missing_job_times"]+=1;continue
            minutes=math.ceil(elapsed/60)
            for row in (result,counts[run["name"]]):
                row["jobs"]+=1;row["seconds"]+=elapsed;row["rounded_minutes_model"]+=minutes
    result["by_workflow"]=dict(counts)
    return result

def gh_json(path):
    raw=subprocess.run(["gh","api",path],capture_output=True,text=True,timeout=12,check=True)
    return json.loads(raw.stdout)

def main():
    try:
        if os.getenv("GITHUB_REPOSITORY")!=REPOSITORY:raise ValueError("Unexpected repository")
        runs=gh_json("repos/"+REPOSITORY+"/actions/runs?event=schedule&status=completed&per_page="+str(MAX_RUNS))["workflow_runs"]
        def jobs(run_id):
            if type(run_id) is not int or run_id<=0:raise ValueError("Invalid run id")
            response=gh_json("repos/"+REPOSITORY+"/actions/runs/"+str(run_id)+"/jobs?per_page=100")
            rows=response["jobs"]
            if response.get("total_count",len(rows))!=len(rows):raise ValueError("Incomplete job page")
            return rows
        result=measure(runs,jobs)
        if not result["jobs"]:raise ValueError("No job measurements")
        print("ACTIONS_RUNTIME_SAMPLE_OK",json.dumps(result,sort_keys=True))
        summary=os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary,"a",encoding="utf-8") as out:
                out.write("\n### Durata job schedulati (campione, non fatturazione)\n\n")
                out.write(f'{result["runs"]} run, {result["jobs"]} job, {result["seconds"]} secondi effettivi, {result["rounded_minutes_model"]} minuti nel modello arrotondato. Timestamp mancanti: {result["missing_job_times"]}. Non è una stima mensile.\n')
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError):
        print("ACTIONS_RUNTIME_SAMPLE_UNAVAILABLE")
        return 1
    return 0

if __name__=="__main__":raise SystemExit(main())
