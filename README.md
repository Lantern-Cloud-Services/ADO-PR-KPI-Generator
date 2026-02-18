# ADO PR KPI Generator

Simple Python script for collecting pull request flow KPIs from Azure DevOps using REST APIs.

The script calculates:
- PR Review Dwell Time (first non-author response)
- PR Completion Time (creation to completion)

For both metrics it reports:
- P50 (median)
- P75
- P90

## How It Works

The script queries Azure DevOps pull requests and PR thread comments, then aggregates timing metrics per repo and across all processed repos.

Repository targets can be provided by:
- `--repo-id` (repeatable)
- `--repo-name` (repeatable)

If no repos are provided, the script processes all repositories in the project.

## Prerequisites

- Python 3.8+
- Azure DevOps Personal Access Token (PAT) with `Code (Read)` scope

Install dependencies:

```bash
pip install -r requirements.txt
```

Set PAT in your environment:

```bash
export ADO_PAT="<your-pat>"
```

## Usage

Run as a module:

```bash
python -m myapp.main --org <org> --project <project> --repo-name <repo>
```

Or run the script directly:

```bash
python src/myapp/main.py --org <org> --project <project> --repo-name <repo>
```

### Common Examples

Time-boxed window (last 30 days):

```bash
python -m myapp.main --org <org> --project <project> --repo-name <repo> --days 30
```

All available PR data (omit `--days`):

```bash
python -m myapp.main --org <org> --project <project> --repo-name <repo>
```

Multiple repositories by name:

```bash
python -m myapp.main --org <org> --project <project> --repo-name repo-a --repo-name repo-b
```

Repository IDs instead of names:

```bash
python -m myapp.main --org <org> --project <project> --repo-id <repo-id-1> --repo-id <repo-id-2>
```

## CLI Arguments

- `--org` (required): Azure DevOps organization name
- `--project` (required): Azure DevOps project name
- `--repo-id` (optional, repeatable): repository ID
- `--repo-name` (optional, repeatable): repository name
- `--include-hidden` (optional): include hidden repos in name resolution
- `--pat` (optional): PAT value (otherwise read from `ADO_PAT`)
- `--days` (optional): lookback window in days; omit to query all available PRs

## Notes

- The script uses Azure DevOps REST API version `7.1` / `7.1-preview.1` endpoints.
- Large projects may take longer because each PR can require additional thread/comment API calls.

## Example Output

```text
=== Repo: AAAP_Code (2d80722b-1381-4325-9e61-fdfbe7041d45) ===
PR Review Dwell Time (First Response) | count=98 | P50=00:00:33 | P75=00:02:41 | P90=00:04:23
PR Completion Time | count=79 | P50=08:39:26 | P75=20:32:44 | P90=115:23:49

=== SUMMARY (across processed repos) ===
PR Review Dwell Time (First Response) | count=98 | P50=00:00:33 | P75=00:02:41 | P90=00:04:23
PR Completion Time | count=79 | P50=08:39:26 | P75=20:32:44 | P90=115:23:49
```

In this output:
- `P50` = 50th percentile (median)
- `P75` = 75th percentile
- `P90` = 90th percentile

Example interpretation:
- For `PR Completion Time`, `P50=08:39:26` means half of completed PRs finished in 8 hours, 39 minutes, and 26 seconds or less.