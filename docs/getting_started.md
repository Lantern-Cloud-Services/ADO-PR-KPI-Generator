# Getting Started: ADO PR KPI Generator

This guide walks you through setup, authentication, and first run for the ADO PR KPI Generator.

## 1) Prerequisites

- Python 3.7+
- Access to an Azure DevOps organization/project/repository
- A Personal Access Token (PAT) with **Code (Read)** scope

## 2) Clone and Set Up Python Environment

From the project root:

```bash
python -m venv .venv
```

Activate the environment:

- **Windows PowerShell**

  ```powershell
  .venv\Scripts\Activate.ps1
  ```

- **Windows Command Prompt**

  ```cmd
  .venv\Scripts\activate.bat
  ```

- **macOS/Linux**

  ```bash
  source .venv/bin/activate
  ```

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional (recommended for local CLI usage):

```bash
pip install -e .
```

## 3) Create an Azure DevOps PAT

1. Open your org: `https://dev.azure.com/<your-org>`
2. In the top-right, open **User settings**.
3. Select **Personal access tokens**.
4. Choose **+ New Token**.
5. Configure:
   - Name: e.g., `ADO-PR-KPI-Generator`
   - Organization: your target org
   - Expiration: per your security policy
   - Scopes: **Code (Read)**
6. Create token and copy it immediately.

## 4) Configure `ADO_PAT` Environment Variable

The application reads credentials only from `ADO_PAT`.

### Windows PowerShell

Current session:

```powershell
$env:ADO_PAT = "your-pat-token"
```

Persistent (future sessions):

```powershell
[System.Environment]::SetEnvironmentVariable("ADO_PAT", "your-pat-token", "User")
```

### Windows Command Prompt

Persistent:

```cmd
setx ADO_PAT "your-pat-token"
```

### macOS/Linux

Current session:

```bash
export ADO_PAT="your-pat-token"
```

Persistent (bash example):

```bash
echo 'export ADO_PAT="your-pat-token"' >> ~/.bashrc
source ~/.bashrc
```

## 5) Run the KPI Generator

### Option A: Run as module

```bash
python -m myapp.main --org myorg --project myproject --repo-name myrepo --days 30
```

### Option B: Run installed CLI command

```bash
ado-pr-kpi-generator --org myorg --project myproject --repo-name myrepo --days 30
```

Supported arguments:

- `--org` (required)
- `--project` (required)
- `--repo-name` (required)
- `--days` (optional, positive integer, default `30`)

Exit codes:

- `0`: Success
- `1`: Unexpected error
- `2`: Configuration error (invalid arguments)
- `3`: Authentication error (missing or invalid PAT)
- `4`: API error (Azure DevOps request failed)

## 6) Example Usage Scenarios

### Scenario 1: Baseline last 30 days

```bash
ado-pr-kpi-generator --org contoso --project platform --repo-name api-service --days 30
```

Use this for regular KPI tracking.

### Scenario 2: Longer trend window (90 days)

```bash
ado-pr-kpi-generator --org contoso --project platform --repo-name api-service --days 90
```

Use this for quarterly health reviews.

## 7) Troubleshooting

- **Authentication error / missing PAT**
  - Ensure `ADO_PAT` is set in the same shell session running the command.
  - Verify token is not expired.

- **Repository not found**
  - Confirm `--repo-name` exactly matches repository name in the specified project.
  - Verify `--org` and `--project` values.

- **API errors (401/403)**
  - Confirm PAT includes at least **Code (Read)**.
  - Ensure PAT belongs to a user with access to the target project/repo.

- **No KPI samples returned**
  - Increase `--days`.
  - Check whether PR activity exists in the selected period.

## Design Reference

For KPI definitions, assumptions, and API flow details, see:

- `docs/SPEC/prkpi_design_spec.md`
