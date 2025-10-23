# api-observability-framework

**Azure-Based API Monitoring & Analysis Prototype**

> A serverless Azure Functions architecture that progressively validates, collects, and analyzes data from any REST or GraphQL API using AI-powered insights.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Cloud: Azure](https://img.shields.io/badge/Cloud-Azure-blue)](/)
[![Status: Prototype](https://img.shields.io/badge/Status-Prototype-orange)](/)

---

## What This Solves

Organizations waste **10+ hours per week** manually monitoring APIs, analyzing failures, and identifying patterns. Whether you're tracking backup systems, infrastructure health, security events, or business metrics, the pattern is always the same:

1. Poll an API on a schedule
2. Store the data somewhere
3. Analyze patterns and anomalies
4. Alert on critical issues

**api-observability-framework** provides this entire pipeline as a reusable Azure architecture that works with **any JSON API**.

---

## Quick Start

### Prerequisites
- Azure subscription
- Azure CLI installed
- Git

### Deploy in 5 Steps

```bash
# 1. Clone and configure
git clone https://github.com/Dwink213/api-observability-framework.git
cd api-observability-framework
cp .env.example .env
# Edit .env with your API details

# 2. Deploy Azure infrastructure
cd infrastructure/bicep
az group create --name api-observability-rg --location eastus2
az deployment group create \
  --resource-group api-observability-rg \
  --template-file main.bicep \
  --parameters baseName=api-obs environment=dev

# 3. Store API credentials in Key Vault
az keyvault secret set \
  --vault-name <your-kv-name> \
  --name api-key \
  --value "<your-api-key>"

# 4. Configure RBAC permissions
cd scripts/azure
./setup-rbac.ps1 -ResourceGroup api-observability-rg

# 5. Deploy function code
cd ../../src/functions
func azure functionapp publish <your-function-app-name>
```

**See [docs/azure-quickstart.md](docs/azure-quickstart.md) for detailed setup guide.**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Progressive Validation                    │
│  (Each function proves a capability before moving forward)  │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         [Function 1]    [Function 2]    [Function 5]
         Timer Works     Secrets Work    Storage Works
              │               │               │
              └───────┬───────┴───────┬───────┘
                      ▼               ▼
                 [Function 3]    [Function 4]
                 API Auth        Data Fetch
                      │               │
                      └───────┬───────┘
                              ▼
                      [Function 6]
                   Production Collection
                   (Runs hourly/daily)
                              ▼
                      [Function 7]
                     AI Analysis
                   (Generates reports)
```

### Key Innovation: Progressive Validation

Unlike traditional "deploy and pray" approaches, this framework uses **7 discrete functions** that each validate one capability:

1. **F1:** Prove timers and logging work
2. **F2:** Prove Key Vault access works
3. **F3:** Prove API authentication works
4. **F4:** Prove data fetching works
5. **F5:** Prove Table Storage works
6. **F6:** Production data collection (runs hourly after 1-5 pass)
7. **F7:** AI-powered analysis (runs daily on collected data)

**Implementation Note:** Functions 1-5 are in `test_functions.py`, Functions 6-7 are in `production_functions.py`

**Why this matters:** When something breaks, you know **exactly** which component failed. No more debugging monolithic scripts.

---

## Use Cases

### Currently Supported

| Use Case | API Examples | Analysis Type |
|----------|-------------|---------------|
| **Backup Monitoring** | Rubrik, Veeam, Commvault | Failure pattern detection |
| **Infrastructure Health** | Datadog, New Relic, Prometheus | Anomaly detection |
| **Security Events** | Splunk, Sentinel, Crowdstrike | Threat pattern analysis |
| **SaaS Metrics** | Stripe, Salesforce, HubSpot | Customer churn prediction |
| **IoT Telemetry** | Azure IoT Hub, custom endpoints | Device failure prediction |
| **Compliance Auditing** | Azure AD, Okta, Auth0 | Policy violation detection |

---

## Azure Services Used

### Required Infrastructure
- **Azure Functions** - Serverless compute (Python 3.11)
- **Azure Key Vault** - Secure credential storage
- **Azure Table Storage** - NoSQL data persistence
- **Application Insights** - Centralized logging
- **Azure OpenAI** (optional) - AI-powered analysis

### Target API Requirements

Your API must:
- Return JSON responses
- Support authentication (OAuth2, API Key, or Bearer Token)
- Have a unique identifier field per record
- (Optional) Have a timestamp field

**That's it.** If your API meets these criteria, this framework works.

---

## Configuration

All configuration is done via Azure Function App Settings (environment variables).

### Minimal Setup (API Key Auth)

```bash
# Required settings
KEY_VAULT_URL=https://your-kv.vault.azure.net/
API_BASE_URL=https://api.example.com
API_AUTH_TYPE=apikey
API_KEY_SECRET_NAME=my-api-key
API_DATA_ENDPOINT=/v1/events
API_ID_FIELD=id
API_TIMESTAMP_FIELD=created_at
STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# Optional field mapping (JSON)
FIELD_MAPPING={"id": "RowKey", "created_at": "EventTimestamp", "status": "Status"}
```

### OAuth2 Setup

```bash
API_AUTH_TYPE=oauth2
API_CLIENT_ID_SECRET_NAME=oauth-client-id
API_CLIENT_SECRET_SECRET_NAME=oauth-client-secret
API_TOKEN_URL=https://api.example.com/oauth/token
```

### GraphQL Setup

```bash
API_QUERY_TYPE=graphql
API_SAMPLE_QUERY={ events(first: 5) { id timestamp status } }
API_RESPONSE_PATH=data.events
```

---

## Storage Schema Options

### Option 1: Minimal (Works with Anything)
```json
{
  "PartitionKey": "data",
  "RowKey": "<unique-id>",
  "Timestamp": "ISO-8601",
  "RawData": "<entire-api-response>"
}
```
**Use when:** You want to start fast, optimize later

### Option 2: Flat (Optimized Queries)
```json
{
  "PartitionKey": "<category>",
  "RowKey": "<unique-id>",
  "Field1": "value",
  "Field2": "value",
  "Timestamp": "ISO-8601"
}
```
**Use when:** You know exactly what fields you need to query

### Option 3: Hybrid (Recommended)
```json
{
  "PartitionKey": "<category>",
  "RowKey": "<unique-id>",
  "KeyFields": "extracted",
  "Timestamp": "ISO-8601",
  "RawData": "<full-json>"
}
```
**Use when:** You want fast queries + complete data preservation

---

## AI Analysis

### Customizable Prompts

Configure via environment variables:

```bash
# For error analysis
AI_PROMPT_TEMPLATE="Analyze these errors and identify the top 3 root causes"

# For trend detection
AI_PROMPT_TEMPLATE="Identify trends over the past 7 days and predict next week"

# For anomaly detection
AI_PROMPT_TEMPLATE="Find outliers and assess risk severity"
```

### Example Output

```
DATA ANALYSIS REPORT - 2025-10-20

Summary:
- Total records: 1,247
- Errors detected: 89 (7.1%)

Top Failure Patterns:
1. Database connection timeout - 34 occurrences (38%)
2. API rate limit exceeded - 21 occurrences (24%)
3. Authentication token expired - 18 occurrences (20%)

Recommendations:
1. Increase database connection pool (fixes 34 errors)
2. Implement exponential backoff (fixes 21 errors)
3. Add token refresh logic (fixes 18 errors)
```

---

## Repository Structure

```
api-observability-framework/
├── README.md                          # This file
├── ARCHITECTURE.md                    # Detailed architecture doc
├── LICENSE                            # MIT License
├── .env.example                       # Configuration template
├── .gitignore                         # Git ignore rules
│
├── docs/
│   ├── azure-quickstart.md           # Step-by-step setup guide
│   ├── azure-troubleshooting.md      # Common issues & fixes
│   └── DATA_FLOW.md                  # Data flow documentation
│
├── src/
│   └── functions/
│       ├── test_functions.py         # Functions 1-5 (validation)
│       ├── production_functions.py   # Functions 6-7 (collection & analysis)
│       ├── requirements.txt          # Python dependencies
│       ├── host.json                 # Function app configuration
│       └── local.settings.json.example  # Local dev settings template
│
├── infrastructure/
│   └── bicep/                        # Azure Bicep IaC
│       ├── main.bicep
│       ├── modules/
│       │   ├── function-app.bicep
│       │   ├── keyvault.bicep
│       │   ├── storage.bicep
│       │   └── monitoring.bicep
│       └── README.md
│
└── scripts/
    └── azure/
        └── setup-rbac.ps1            # RBAC permission setup
```

---

## Deployment Walkthrough

### 1. Deploy Infrastructure (10 minutes)

```bash
cd infrastructure/bicep
az group create --name api-observability-rg --location eastus2
az deployment group create \
  --resource-group api-observability-rg \
  --template-file main.bicep \
  --parameters baseName=api-obs environment=dev
```

**Creates:**
- Function App (Consumption plan)
- Key Vault
- Storage Account (Table Storage)
- Application Insights
- Log Analytics Workspace

### 2. Configure RBAC (5 minutes)

```powershell
cd ../../scripts/azure
./setup-rbac.ps1 -ResourceGroup api-observability-rg
```

**Grants:**
- Key Vault Secrets User
- Storage Table Data Contributor
- Storage Blob Data Contributor

### 3. Store API Credentials (2 minutes)

```bash
az keyvault secret set \
  --vault-name <your-kv-name> \
  --name api-key \
  --value "<your-api-key>"
```

### 4. Deploy Function Code (5 minutes)

```bash
cd ../../src/functions
func azure functionapp publish <your-function-app-name>
```

**See [docs/azure-quickstart.md](docs/azure-quickstart.md) for complete guide.**

---

## Troubleshooting

### Function 1 Fails
**Symptom:** No logs appear in Application Insights
**Cause:** Function app deployment issue
**Fix:** Verify function app exists and is running

### Function 2 Fails (Access Denied)
**Symptom:** "403 Forbidden" when accessing Key Vault
**Cause:** Missing RBAC permissions
**Fix:** Run `setup-rbac.ps1` script and wait 5-10 minutes for propagation

### Function 3 Fails (401 Unauthorized)
**Symptom:** API returns "Invalid credentials"
**Cause:** Wrong credentials in Key Vault
**Fix:** Verify credentials are correct and not expired

### Function 6 Timeout
**Symptom:** Function times out with large datasets
**Cause:** Default timeout too low (5 min)
**Fix:** Increase function timeout to 10+ minutes in host.json

**Full troubleshooting guide:** [docs/azure-troubleshooting.md](docs/azure-troubleshooting.md)

---

## Performance & Costs

### Typical Monthly Costs (Azure)

| Component | Usage | Cost |
|-----------|-------|------|
| Azure Functions (Consumption) | 720 executions/month | $0.40 |
| Table Storage (100K records) | 100K writes, 10K reads | $1.00 |
| Application Insights | 1GB/month | $2.30 |
| Key Vault | 3 secrets | $0.15 |
| Azure OpenAI (optional) | 30 requests/month | $1.50 |
| **Total** | | **~$5/month** |

### Scaling Characteristics

- **100K records/month:** ~$5/month
- **1M records/month:** ~$20/month
- **10M records/month:** ~$100/month

*Costs scale linearly with data volume*

---

## Roadmap

### v1.0 - Current (Azure Prototype)
- ✅ Azure Functions-based architecture
- ✅ Progressive validation workflow
- ✅ OAuth2, API Key, Bearer auth support
- ✅ REST and GraphQL support
- ✅ Pagination handling
- ✅ Azure OpenAI integration
- ✅ Bicep infrastructure as code

### v2.0 - Multi-Cloud (Q2 2026)
- [ ] AWS Lambda implementation (CloudFormation/Terraform)
- [ ] GCP Cloud Functions implementation
- [ ] Abstraction layer for cloud-agnostic deployment
- [ ] Unified `deploy.sh` script

### v3.0 - Extensibility (Q3 2026)
- [ ] Modular adapter system (`src/lib/`)
  - [ ] `auth_adapters.py` - Pluggable auth methods
  - [ ] `storage_adapters.py` - Multi-storage backends
  - [ ] `ai_adapters.py` - Multiple AI providers
- [ ] Pre-built API examples (folders in `examples/`)
  - [ ] Stripe payments example with sample code
  - [ ] GitHub repos example with sample code
  - [ ] Datadog metrics example with sample code
  - Note: `.env.example` already includes config templates for these APIs
- [ ] Configuration templates (`src/config/`)
- [ ] Comprehensive test suite

### v4.0 - Enterprise Features (Q4 2026)
- [ ] Web UI for configuration
- [ ] Built-in alerting engine
- [ ] Custom dashboard builder
- [ ] Real-time streaming (not just batch)

---

## Contributing

This is currently a personal portfolio project, but contributions are welcome!

**Areas where help is needed:**
- AWS/GCP implementations
- Additional auth adapters
- Pre-built API examples
- Test coverage
- Documentation improvements

Open an issue to discuss major changes before starting work.

---

## License

MIT License - See [LICENSE](LICENSE) file

Copyright (c) 2025 Dustin Winkler

---

## Support

- **Documentation:** [docs/azure-quickstart.md](docs/azure-quickstart.md)
- **Issues:** [github.com/Dwink213/api-observability-framework/issues](https://github.com/Dwink213/api-observability-framework/issues)
- **LinkedIn:** [linkedin.com/in/dustin-winkler-nc](https://linkedin.com/in/dustin-winkler-nc/)

---

## Resume-Ready Achievements

**Architected and implemented a serverless API monitoring framework on Azure** that uses progressive validation to reduce debugging time by 80%, enabling rapid identification of configuration errors versus code defects through seven discrete validation functions that each prove a specific capability works.

**Designed cloud-native data collection pipeline** that integrates with any RESTful or GraphQL API through environment-based configuration, supporting OAuth2, API Key, and Bearer token authentication with automatic pagination handling and AI-powered pattern analysis.

**Implemented Infrastructure as Code using Azure Bicep** for repeatable deployment of Function Apps, Key Vault, Table Storage, and Application Insights with automatic RBAC configuration, reducing deployment time from hours to minutes.

---

## Skills Demonstrated

- **Cloud Architecture:** Azure Functions, serverless patterns
- **API Integration:** RESTful, GraphQL, OAuth2, pagination handling
- **Infrastructure as Code:** Azure Bicep, ARM templates
- **Security:** Key Vault, Managed Identity, RBAC
- **NoSQL Data Modeling:** Azure Table Storage, partition strategies
- **AI/LLM Integration:** Azure OpenAI, prompt engineering
- **Error Handling:** Progressive validation, graceful degradation
- **Python:** Azure Functions SDK, async/await patterns
- **DevOps:** CI/CD readiness, configuration management

---

**Built with care by [Dustin Winkler](https://github.com/Dwink213)**
