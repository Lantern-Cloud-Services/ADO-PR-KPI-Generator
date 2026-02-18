import os
import sys
import time
import math
import argparse
import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth


# ---------- stats helpers ----------
def percentile(sorted_values: List[float], p: float) -> Optional[float]:
    """Linear interpolation percentile. p in [0, 100]."""
    if not sorted_values:
        return None
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def seconds_to_hhmmss(seconds: Optional[float]) -> str:
    if seconds is None:
        return "n/a"
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_ado_datetime(s: str) -> dt.datetime:
    """Parse ADO ISO8601 timestamps; normalizes 'Z' to UTC offset."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)


# ---------- ADO REST client ----------
@dataclass
class AdoConfig:
    organization: str
    project: str
    pat: str
    api_version_repos: str = "7.1"               # repo list endpoint supports 7.1
    api_version_pr_list: str = "7.1-preview.1"   # PR list commonly used with preview versions
    api_version_threads: str = "7.1"             # threads/comments documented in 7.1


class AdoClient:
    def __init__(self, cfg: AdoConfig):
        self.cfg = cfg
        self.session = requests.Session()
        # PAT via Basic auth: username empty, password PAT (common pattern)
        self.auth = HTTPBasicAuth("", cfg.pat)
        self.session.auth = self.auth
        self.session.headers.update({"Accept": "application/json"})

    def _url(self, path: str) -> str:
        # base: https://dev.azure.com/{org}/{project}/_apis/...
        return f"https://dev.azure.com/{self.cfg.organization}/{self.cfg.project}/{path.lstrip('/')}"

    def _get(self, url: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """GET with small retry/backoff; returns (json, headers)."""
        for attempt in range(1, 6):
            r = self.session.get(url, params=params)
            if r.status_code in (429, 500, 502, 503, 504):
                retry_after = int(r.headers.get("Retry-After", "1"))
                time.sleep(min(30, retry_after * attempt))
                continue
            r.raise_for_status()
            return r.json(), dict(r.headers)
        r.raise_for_status()  # if we fall out, raise

    # ---- repository resolution ----
    def list_repositories(self, include_hidden: bool = False) -> List[Dict[str, Any]]:
        """
        List repos in project:
        GET .../_apis/git/repositories?api-version=7.1
        """
        url = self._url("/_apis/git/repositories")
        params = {
            "api-version": self.cfg.api_version_repos,
            "includeHidden": str(include_hidden).lower()
        }
        data, _headers = self._get(url, params=params)
        return data.get("value", [])

    def resolve_repo_names_to_ids(self, repo_names: List[str], include_hidden: bool = False) -> Dict[str, str]:
        """
        Returns mapping {normalized_input_name: repo_id}.
        Resolution is case-insensitive on repo 'name'.
        """
        repos = self.list_repositories(include_hidden=include_hidden)
        by_name = {r.get("name", "").lower(): r.get("id") for r in repos if r.get("name") and r.get("id")}

        resolved: Dict[str, str] = {}
        for raw in repo_names:
            key = raw.strip()
            if not key:
                continue
            rid = by_name.get(key.lower())
            if rid:
                resolved[key] = rid
            else:
                # allow partial "project/_git/repo" inputs: take last segment
                simplified = key.split("/")[-1]
                rid2 = by_name.get(simplified.lower())
                if rid2:
                    resolved[key] = rid2
        return resolved

    # ---- PR + threads/comments ----
    def list_pull_requests(self, repo_id: str, status: str,
                           min_time: dt.datetime, max_time: dt.datetime,
                           top: int = 100) -> List[Dict[str, Any]]:
        """
        List PRs for repo, time-bounded.
        Uses continuation token header if present (x-ms-continuationtoken).
        """
        url = self._url(f"/_apis/git/repositories/{repo_id}/pullrequests")
        prs: List[Dict[str, Any]] = []
        continuation = None

        while True:
            params = {
                "searchCriteria.status": status,  # active | completed | abandoned
                "searchCriteria.minTime": min_time.isoformat().replace("+00:00", "Z"),
                "searchCriteria.maxTime": max_time.isoformat().replace("+00:00", "Z"),
                "$top": top,
                "api-version": self.cfg.api_version_pr_list
            }
            if continuation:
                params["continuationToken"] = continuation

            data, headers = self._get(url, params=params)
            prs.extend(data.get("value", []))

            continuation = headers.get("x-ms-continuationtoken")
            if not continuation:
                break

        return prs

    def list_threads(self, repo_id: str, pr_id: int) -> List[Dict[str, Any]]:
        url = self._url(f"/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads")
        params = {"api-version": self.cfg.api_version_threads}
        data, _headers = self._get(url, params=params)
        return data.get("value", [])

    def list_thread_comments(self, repo_id: str, pr_id: int, thread_id: int) -> List[Dict[str, Any]]:
        """
        Thread comments have 'publishedDate' and author identity, per docs.
        """
        url = self._url(
            f"/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads/{thread_id}/comments"
        )
        params = {"api-version": self.cfg.api_version_threads}
        data, _headers = self._get(url, params=params)
        return data.get("value", [])


# ---------- KPI logic ----------
def first_non_author_comment_time_utc(ado: AdoClient, repo_id: str, pr: Dict[str, Any],
                                     ignore_bots: bool = True) -> Optional[dt.datetime]:
    pr_id = pr.get("pullRequestId")
    created_by = pr.get("createdBy", {}) or {}
    pr_author_id = created_by.get("id")

    earliest: Optional[dt.datetime] = None

    for thread in ado.list_threads(repo_id, pr_id):
        tid = thread.get("id")
        if tid is None:
            continue
        for c in ado.list_thread_comments(repo_id, pr_id, tid):
            author = c.get("author", {}) or {}
            author_id = author.get("id")
            display = (author.get("displayName") or "").lower()

            # must have timestamp
            ts = c.get("publishedDate")
            if not ts:
                continue

            # exclude PR author
            if pr_author_id and author_id == pr_author_id:
                continue

            # optional: crude bot filter (best-effort)
            if ignore_bots and any(tok in display for tok in ("bot", "build", "service", "pipeline")):
                continue

            t = parse_ado_datetime(ts)
            if earliest is None or t < earliest:
                earliest = t

    return earliest


def summarize_metric(name: str, values_seconds: List[float]) -> Dict[str, Any]:
    vals = sorted([v for v in values_seconds if v is not None and v >= 0])
    return {
        "metric": name,
        "count": len(vals),
        "p50": percentile(vals, 50),
        "p75": percentile(vals, 75),
        "p90": percentile(vals, 90)
    }


def compute_kpis_for_repo(ado: AdoClient, repo_id: str,
                          min_time: dt.datetime, max_time: dt.datetime,
                          ignore_bots: bool = True) -> Tuple[List[float], List[float]]:
    """
    Dwell: PR creation -> first non-author comment.
    Completion: PR creation -> closedDate (completed PRs).
    """
    dwell_seconds: List[float] = []
    completion_seconds: List[float] = []

    # For dwell, you typically care about active PRs (still waiting) AND recently completed ones (for trend).
    # We'll collect both.
    prs_active = ado.list_pull_requests(repo_id, "active", min_time, max_time)
    prs_completed = ado.list_pull_requests(repo_id, "completed", min_time, max_time)

    for pr in prs_active + prs_completed:
        created = pr.get("creationDate")
        if not created:
            continue
        created_t = parse_ado_datetime(created)

        # KPI 1: first response dwell time
        first_resp = first_non_author_comment_time_utc(ado, repo_id, pr, ignore_bots=ignore_bots)
        if first_resp:
            dwell_seconds.append((first_resp - created_t).total_seconds())

        # KPI 2: completion time (completed only)
        if (pr.get("status") or "").lower() == "completed":
            closed = pr.get("closedDate")
            if closed:
                closed_t = parse_ado_datetime(closed)
                completion_seconds.append((closed_t - created_t).total_seconds())

    return dwell_seconds, completion_seconds


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(
        description="Azure DevOps Services PR KPI extractor (Median/P75/P90). Resolves repo names to IDs."
    )
    ap.add_argument("--org", required=True, help="Azure DevOps organization name")
    ap.add_argument("--project", required=True, help="Azure DevOps project name")

    # Repo inputs (repeatable)
    ap.add_argument("--repo-id", action="append", default=[], help="Repository GUID/ID (repeatable)")
    ap.add_argument("--repo-name", action="append", default=[], help="Repository name (repeatable)")

    ap.add_argument("--include-hidden", action="store_true", help="Include hidden repos when resolving names")
    ap.add_argument("--pat", default=os.getenv("ADO_PAT"), help="PAT (or set env var ADO_PAT)")
    ap.add_argument("--days", type=int, default=30, help="Lookback window in days")
    ap.add_argument("--ignore-bots", action="store_true", help="Ignore bot/service comments (best-effort)")

    args = ap.parse_args()

    if not args.pat:
        print("ERROR: PAT required via --pat or env var ADO_PAT", file=sys.stderr)
        sys.exit(2)

    max_time = dt.datetime.now(dt.timezone.utc)
    min_time = max_time - dt.timedelta(days=args.days)

    ado = AdoClient(AdoConfig(organization=args.org, project=args.project, pat=args.pat))

    # Resolve repo names -> IDs
    resolved: Dict[str, str] = {}
    if args.repo_name:
        resolved = ado.resolve_repo_names_to_ids(args.repo_name, include_hidden=args.include_hidden)

        # Warn on unresolved
        unresolved = [n for n in args.repo_name if n.strip() and n.strip() not in resolved]
        if unresolved:
            print("WARNING: Could not resolve these repo names (check spelling/project):")
            for n in unresolved:
                print(f"  - {n}")

    # Build final repo ID set
    repo_ids = set([rid for rid in args.repo_id if rid])
    repo_ids.update(resolved.values())

    # If no repos provided, process all repos in project
    if not repo_ids:
        repos = ado.list_repositories(include_hidden=args.include_hidden)
        repo_ids = set([r["id"] for r in repos if r.get("id")])
        print(f"No repos specified; processing ALL repos in project (count={len(repo_ids)}).")

    all_dwell: List[float] = []
    all_completion: List[float] = []

    for repo_id in sorted(repo_ids):
        print(f"\n=== Repo: {repo_id} ===")
        dwell, comp = compute_kpis_for_repo(ado, repo_id, min_time, max_time, ignore_bots=args.ignore_bots)
        all_dwell.extend(dwell)
        all_completion.extend(comp)

        s1 = summarize_metric("PR Review Dwell Time (First Response)", dwell)
        s2 = summarize_metric("PR Completion Time", comp)

        print(f"{s1['metric']} | count={s1['count']} | P50={seconds_to_hhmmss(s1['p50'])} "
              f"| P75={seconds_to_hhmmss(s1['p75'])} | P90={seconds_to_hhmmss(s1['p90'])}")
        print(f"{s2['metric']} | count={s2['count']} | P50={seconds_to_hhmmss(s2['p50'])} "
              f"| P75={seconds_to_hhmmss(s2['p75'])} | P90={seconds_to_hhmmss(s2['p90'])}")

    print("\n=== ORG/PROJECT SUMMARY (across processed repos) ===")
    a1 = summarize_metric("PR Review Dwell Time (First Response)", all_dwell)
    a2 = summarize_metric("PR Completion Time", all_completion)
    print(f"{a1['metric']} | count={a1['count']} | P50={seconds_to_hhmmss(a1['p50'])} "
          f"| P75={seconds_to_hhmmss(a1['p75'])} | P90={seconds_to_hhmmss(a1['p90'])}")
    print(f"{a2['metric']} | count={a2['count']} | P50={seconds_to_hhmmss(a2['p50'])} "
          f"| P75={seconds_to_hhmmss(a2['p75'])} | P90={seconds_to_hhmmss(a2['p90'])}")


if __name__ == "__main__":
    main()
