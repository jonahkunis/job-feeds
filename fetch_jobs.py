"""Pull public job-board feeds, keep early-career roles in Jonah's lanes, write data/jobs.json + data/report.md."""
import json, re, datetime, urllib.request, urllib.error

INCLUDE = re.compile(r"new ?grad|graduate|university|early career|entry|associate|rotational|2027|analyst|coordinator|specialist|apm(m)?\b", re.I)
LANE = re.compile(r"marketing|brand|growth|content|social|creative|video|community|communications|partnership|operations|ops\b|strategy|business|analyst|analytics|insights|go-to-market|gtm|lifecycle|e-?commerce|sales development|business development", re.I)
EXCLUDE = re.compile(r"senior|sr\.?|staff|principal|lead|director|head of|vp|intern|phd|mba|engineer|engineering|software|developer|scientist|counsel|attorney|recruit|nurse|clinical", re.I)
US = re.compile(r"united states|usa|\bus\b|remote|california|\bca\b|san francisco|bay area|oakland|berkeley|palo alto|mountain view|sunnyvale|san jose|menlo park|redwood city|south san francisco|los angeles|new york|\bny\b|seattle|austin|chicago|boston|denver", re.I)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "job-feeds/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

MANAGER = re.compile(r"manager", re.I)

def keep(title, loc):
    if MANAGER.search(title) and not re.search(r"associate", title, re.I):
        return False
    return INCLUDE.search(title) and LANE.search(title) and not EXCLUDE.search(title) and (not loc or US.search(loc))

def greenhouse(slug):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    for j in d.get("jobs", []):
        yield j["title"], (j.get("location") or {}).get("name", ""), j["absolute_url"], j.get("updated_at", "")

def lever(slug):
    for j in get(f"https://api.lever.co/v0/postings/{slug}?mode=json"):
        cat = j.get("categories") or {}
        ts = j.get("createdAt")
        yield j["text"], cat.get("location", ""), j["hostedUrl"], datetime.datetime.utcfromtimestamp(ts/1000).isoformat() if ts else ""

def ashby(slug):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    for j in d.get("jobs", []):
        yield j["title"], j.get("location", ""), j.get("jobUrl", ""), j.get("publishedAt", "")

def main():
    cfg = json.load(open("companies.json"))
    try:
        prev = {j["url"] for j in json.load(open("data/jobs.json"))["jobs"]}
    except Exception:
        prev = set()
    jobs, dead = [], []
    for board, fn in (("greenhouse", greenhouse), ("lever", lever), ("ashby", ashby)):
        for slug in cfg.get(board, []):
            try:
                for title, loc, url, ts in fn(slug):
                    if keep(title, loc):
                        jobs.append({"company": slug, "board": board, "title": title, "location": loc, "url": url, "posted_or_updated": ts, "new_since_last_run": url not in prev})
            except urllib.error.HTTPError as e:
                dead.append(f"{board}/{slug} (HTTP {e.code})")
            except Exception as e:
                dead.append(f"{board}/{slug} ({type(e).__name__})")
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    json.dump({"fetched_at": now, "count": len(jobs), "jobs": jobs, "dead_slugs": dead}, open("data/jobs.json", "w"), indent=1)
    new = [j for j in jobs if j["new_since_last_run"]]
    lines = [f"# Job feeds {now}", f"{len(jobs)} matching roles, {len(new)} new since last run.", "", "## New"]
    lines += [f"- {j['company']}: {j['title']} ({j['location']}) {j['url']}" for j in new] or ["- none"]
    lines += ["", "## DEAD slugs (fix in companies.json)"] + ([f"- {d}" for d in dead] or ["- none"])
    open("data/report.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
