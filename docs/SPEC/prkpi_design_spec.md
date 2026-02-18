# Project Overview

This project delivers a reusable, API-driven scripting framework for extracting and aggregating pull request–level flow metrics from Azure DevOps Services. The primary goal is to enable consistent, repeatable measurement of engineering workflow health using system-of-record data rather than manual reporting or tool-specific dashboards.

The script focuses on two foundational pull request KPIs—review dwell time (first response) and end-to-end completion time—computed using clearly defined, auditable events exposed by Azure DevOps REST APIs. Metrics are calculated using median (P50) as the primary indicator, with higher percentiles (P75, P90) included to highlight variability and bottlenecks without distortion from outliers.

The solution is designed to operate at repository, project, and organizational scopes, supports repository name–based configuration for ease of use, and can be integrated into scheduled jobs, reporting pipelines, or downstream analytics workflows. By standardizing KPI definitions and data extraction logic, this approach establishes a durable foundation for longitudinal trend analysis and continuous improvement of development flow.

---

# PR-KPIs Design

## KPI 1: PR Review Dwell Time (First Response Time)

### Business Question

How long does it typically take for a pull request to receive attention after it's opened?

**Metric:** Median time from PR creation  first non-author review action

### Rationale

Because Azure DevOps Services does not expose a clean historical "first vote timestamp" via REST, the most reliable and auditable definition is:

 **First non-author comment on the PR**

This represents real human engagement and is consistently timestamped.

### Data Collection

#### Step 1: List PRs (time-boxed)

```
GET https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repoId}/pullrequests
  ?searchCriteria.status=all
  &searchCriteria.minTime={ISO-8601}
  &searchCriteria.maxTime={ISO-8601}
  &api-version=7.1-preview.1
```

**Captured Fields:**
- `pullRequestId`
- `creationDate`
- `createdBy.id`

#### Step 2: Retrieve PR Threads & Comments

For each PR from Step 1, retrieve all threads and comments:

```
GET https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repoId}/pullRequests/{prId}/threads
  ?api-version=7.1
```

**For Each Thread, Identify:**
- `comment.author.id`
- `comment.publishedDate`

#### Step 3: Compute Dwell Time

```
first_response_time = MIN(comment.publishedDate) 
                      WHERE comment.author.id != pr.createdBy.id
```

### KPI Calculation

- **Median (P50)** dwell time per repo / team / org
- **P75 / P90** percentiles for additional insights

---

## KPI 2: PR Completion Time (End-to-End Flow)

### Business Question

How long does it typically take for code to move from open  merged?

**Metric:** Median time from PR creation  PR completion

### How to Compute (REST APIs)

Collect the following from the PR list:
- `creationDate`
- `closedDate` (for completed PRs)
- `status == completed`

#### Calculation

```
completion_time = closedDate - creationDate
```

#### Aggregation

- **Median (P50)** completion time
- **P75 / P90** as flow-health indicators

---

## Authentication & Setup

### Personal Access Token (PAT) for ADO APIs

The script requires authentication to access Azure DevOps REST APIs. This is accomplished using a **Personal Access Token (PAT)**, which is a secure, credential-free method for programmatic access to ADO resources.

#### Creating a PAT

1. Navigate to your Azure DevOps organization: `https://dev.azure.com/{org}`
2. Click **User Settings** (icon in the top-right corner)
3. Select **Personal access tokens**
4. Click **+ New Token**
5. Configure the token:
   - **Name:** Choose a descriptive name (e.g., `PR-KPI-Generator`)
   - **Organization:** Select the organization to grant access to
   - **Expiration:** Set an appropriate expiration period
   - **Scopes:** Grant the following scopes:
     - `Code (Read)` – Required to read pull requests and threads

6. Click **Create** and copy the generated token immediately (you cannot retrieve it again)

#### Storing the PAT as an Environment Variable

To avoid hardcoding credentials in your scripts or command line, store the PAT as an environment variable:

**On Windows (PowerShell):**
```powershell
$env:ADO_PAT = "your-pat-token-here"
```

**On Windows (Command Prompt, persistent):**
```cmd
setx ADO_PAT "your-pat-token-here"
```

**On macOS/Linux (temporary):**
```bash
export ADO_PAT="your-pat-token-here"
```

**On macOS/Linux (persistent, add to ~/.bashrc or ~/.zshrc):**
```bash
echo 'export ADO_PAT="your-pat-token-here"' >> ~/.bashrc
source ~/.bashrc
```

#### Security Best Practices

- **Never commit PATs** to version control or configuration files
- **Use environment variables** for all automated/scripted access
- **Rotate tokens regularly** and delete old tokens from the Personal access tokens page
- **Restrict token scope** to the minimum required permissions
- **Monitor token usage** through the ADO audit logs if available in your organization

---

## Reference Implementation

See [reference_kpis.py](reference_kpis.py) for the full Python reference script that demonstrates the KPI collection and calculation workflow:

- **Authentication:** PAT via Basic auth (sourced from `ADO_PAT` environment variable)
- **Repository Resolution:** Maps repo names to IDs via REST
- **Data Collection:** Fetches PR list + threads/comments with pagination support
- **KPI 1 Computation:** Identifies first non-author comment timestamp
- **KPI 2 Computation:** Calculates PR creation-to-close duration
- **Statistics:** Computes P50/P75/P90 percentiles per repo and org-wide

### Prerequisites

- **Python 3.7+**
- **requests library:** Install via `pip install requests`
- **Azure DevOps PAT token:** Store in the `ADO_PAT` environment variable (see [Authentication & Setup](#authentication--setup) above)

### Usage

Ensure your PAT is stored in the `ADO_PAT` environment variable, then run the script:

```bash
# The script reads the PAT from the ADO_PAT environment variable automatically
# Time-bounded mode (analyze recent PRs only)
python reference_kpis.py --org {org} --project {project} --repo-name {repo} --days 30

# All-PRs mode (analyze all PRs regardless of age)
python reference_kpis.py --org {org} --project {project} --repo-name {repo}
```

**Arguments:**
- `--org` (required): Azure DevOps organization name
- `--project` (required): Project name within the organization
- `--repo-name` (required): Repository name to analyze
- `--days` (optional): Number of days of historical PR data to analyze. If omitted, analyzes all PRs regardless of age.

**Examples:**
```bash
# Time-bounded mode
python reference_kpis.py --org myorg --project myproject --repo-name myrepo --days 60

# All-PRs mode
python reference_kpis.py --org myorg --project myproject --repo-name myrepo
```

The script will retrieve the PAT from the `ADO_PAT` environment variable and use it to authenticate all API requests. No credentials need to be specified on the command line.
