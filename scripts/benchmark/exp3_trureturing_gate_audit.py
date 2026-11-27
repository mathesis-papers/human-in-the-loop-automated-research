#!/usr/bin/env python3
"""Track 3: Empirical read-only audit of public PR admission/filtering and formal dependency reuse
on the-omega-institute/trureturing using gh api graphql."""
import json
import re
import statistics
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

OUT = Path("data/benchmark/exp3_trureturing_audit.json")

QUERY = """
query($cursor: String) {
  repository(owner: "the-omega-institute", name: "trureturing") {
    pullRequests(first: 100, after: $cursor, states: [MERGED, CLOSED], orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        state
        title
        createdAt
        closedAt
        mergedAt
        additions
        deletions
        changedFiles
        commits { totalCount }
        labels(first: 10) { nodes { name } }
        closingIssuesReferences(first: 5) { totalCount }
        bodyText
      }
    }
    mergedTotal: pullRequests(states: MERGED) { totalCount }
    closedUnmergedTotal: pullRequests(states: CLOSED) { totalCount }
    openTotal: pullRequests(states: OPEN) { totalCount }
    issuesTotal: issues { totalCount }
    issuesClosed: issues(states: CLOSED) { totalCount }
  }
}
"""

def run_gql(cursor=None):
    cmd = ["gh", "api", "graphql", "-f", f"query={QUERY}"]
    if cursor:
        cmd += ["-f", f"cursor={cursor}"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)

prs = []
totals = {}
cursor = None
for page in range(10):  # 1,000 most recent completed PRs
    data = run_gql(cursor)["data"]["repository"]
    if page == 0:
        totals = {
            "merged_all_time": data["mergedTotal"]["totalCount"],
            "closed_unmerged_all_time": data["closedUnmergedTotal"]["totalCount"],
            "open_current": data["openTotal"]["totalCount"],
            "issues_all_time": data["issuesTotal"]["totalCount"],
            "issues_closed_all_time": data["issuesClosed"]["totalCount"],
        }
    pr_conn = data["pullRequests"]
    prs.extend(pr_conn["nodes"])
    print(f"Page {page+1}: fetched {len(pr_conn['nodes'])} PRs (total {len(prs)})", flush=True)
    if not pr_conn["pageInfo"]["hasNextPage"]:
        break
    cursor = pr_conn["pageInfo"]["endCursor"]

merged = [p for p in prs if p["state"] == "MERGED"]
closed = [p for p in prs if p["state"] == "CLOSED"]

def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

merge_mins = []
multi_commit_merged = 0
escape_mentions_merged = 0
prereg_link_merged = 0
refute_merged = 0
prove_merged = 0
bind_or_reject_closed = 0
issue_ref_re = re.compile(r"#\d+|issues/\d+|question_answered|preregist", re.I)
escape_re = re.compile(r"escape|non-binding|witness", re.I)
refute_re = re.compile(r"\b(refut|disprov|counterexample|false)\b", re.I)
prove_re = re.compile(r"\b(prov|settl|theorem|establish|formaliz)\b", re.I)
reject_reason_re = re.compile(r"bind-only|duplicate|already|supersed|inflation|escape|sorry|fail|invalid", re.I)

for p in merged:
    if p["createdAt"] and p["mergedAt"]:
        dt = (parse_ts(p["mergedAt"]) - parse_ts(p["createdAt"])).total_seconds() / 60.0
        if dt >= 0:
            merge_mins.append(dt)
    if (p["commits"]["totalCount"] or 0) > 1:
        multi_commit_merged += 1
    txt = f"{p['title']} {p.get('bodyText','')}"
    if escape_re.search(txt):
        escape_mentions_merged += 1
    if (p["closingIssuesReferences"]["totalCount"] or 0) > 0 or issue_ref_re.search(txt):
        prereg_link_merged += 1
    if refute_re.search(p["title"]):
        refute_merged += 1
    elif prove_re.search(p["title"]):
        prove_merged += 1

for p in closed:
    txt = f"{p['title']} {p.get('bodyText','')}"
    if reject_reason_re.search(txt):
        bind_or_reject_closed += 1

all_time_completed = totals["merged_all_time"] + totals["closed_unmerged_all_time"]
summary = {
    "repository": "the-omega-institute/trureturing",
    "sampled_recent_completed_prs": len(prs),
    "date_range_utc": [prs[-1]["createdAt"], prs[0]["createdAt"]] if prs else [],
    "all_time": {
        **totals,
        "completed_all_time": all_time_completed,
        "all_time_merge_rate_pct": round(100.0 * totals["merged_all_time"] / all_time_completed, 2) if all_time_completed else 0,
        "all_time_closed_unmerged_rate_pct": round(100.0 * totals["closed_unmerged_all_time"] / all_time_completed, 2) if all_time_completed else 0,
    },
    "recent_1000_sample": {
        "n": len(prs),
        "merged": len(merged),
        "closed_unmerged": len(closed),
        "merge_rate_pct": round(100.0 * len(merged) / len(prs), 2),
        "closed_unmerged_rate_pct": round(100.0 * len(closed) / len(prs), 2),
        "median_time_to_merge_min": round(statistics.median(merge_mins), 1) if merge_mins else None,
        "p75_time_to_merge_min": round(sorted(merge_mins)[int(0.75 * len(merge_mins))], 1) if merge_mins else None,
        "multi_commit_revision_rate_pct": round(100.0 * multi_commit_merged / len(merged), 2) if merged else 0,
        "multi_commit_merged_count": multi_commit_merged,
        "prereg_or_issue_linked_merged_count": prereg_link_merged,
        "prereg_or_issue_linked_pct": round(100.0 * prereg_link_merged / len(merged), 2) if merged else 0,
        "escape_or_witness_mentioned_merged_count": escape_mentions_merged,
        "escape_or_witness_mentioned_pct": round(100.0 * escape_mentions_merged / len(merged), 2) if merged else 0,
        "title_refutation_count": refute_merged,
        "title_proof_count": prove_merged,
        "median_additions_merged": round(statistics.median(p["additions"] for p in merged), 1) if merged else None,
        "median_changed_files_merged": round(statistics.median(p["changedFiles"] for p in merged), 1) if merged else None,
        "closed_unmerged_median_commits": round(statistics.median(p["commits"]["totalCount"] for p in closed), 1) if closed else None,
        "closed_unmerged_median_additions": round(statistics.median(p["additions"] for p in closed), 1) if closed else None,
    },
}

OUT.write_text(json.dumps(summary, indent=2))
print("\n=== TRACK 3 SUMMARY ===")
print(json.dumps(summary, indent=2))
