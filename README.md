# ADO PR KPI Generator

CLI tool to compute pull request flow KPIs from Azure DevOps repositories using REST APIs and a Personal Access Token (PAT).

## What It Measures

The generator calculates percentile statistics (P50, P75, P90) for:

1. **PR Review Dwell Time (First Response Time)**  
	Time from PR creation to the first non-author comment.
2. **PR Completion Time (End-to-End Flow)**  
	Time from PR creation to PR completion (`status == completed`).

## Prerequisites

- Python 3.7+
- Azure DevOps Personal Access Token (PAT) with at least **Code (Read)** scope
- PAT exported as `ADO_PAT` environment variable

## Installation

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Optional editable install (adds CLI command):

```bash
pip install -e .
```

## Configuration

Set your PAT in `ADO_PAT` before running the tool:

```powershell
# Windows PowerShell (current session)
$env:ADO_PAT = "your-token"
```

```bash
# macOS/Linux (current session)
export ADO_PAT="your-token"
```

## Usage

Run via module:

```bash
python -m myapp.main --org myorg --project myproject --repo-name myrepo --days 30
```

Or, after `pip install -e .`, run:

```bash
ado-pr-kpi-generator --org myorg --project myproject --repo-name myrepo --days 30
```

Arguments:

- `--org` (required): Azure DevOps organization name
- `--project` (required): Azure DevOps project name
- `--repo-name` (required): Repository name to analyze
- `--days` (optional): Positive integer lookback window, default `30`

Exit codes:

- `0`: Success
- `1`: Unexpected error
- `2`: Configuration error (invalid arguments)
- `3`: Authentication error (missing or invalid PAT)
- `4`: API error (Azure DevOps request failed)

## More Documentation

- Getting started guide: `docs/getting_started.md`
- Design spec: `docs/SPEC/prkpi_design_spec.md`