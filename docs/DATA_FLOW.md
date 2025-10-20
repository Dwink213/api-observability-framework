# Data Flow Documentation

This document explains how data flows through the API Observability Framework.

---

## Overview

The framework uses **progressive validation** to ensure each capability works before enabling production workloads. Data flows through three phases:

1. **Validation Phase** - Test functions (F1-F5) validate infrastructure
2. **Collection Phase** - Production collector (F6) fetches and stores data
3. **Analysis Phase** - AI analyzer (F7) and dashboard (F8) generate insights

---

## 1. Progressive Validation Flow

Test functions run **once during setup** to validate each component independently.

```mermaid
graph TD
    Start([Deploy Infrastructure]) --> F1[F1: Timer & Logging Test]
    
    F1 -->|✓ Pass| Split{Split Validation}
    
    Split --> F2[F2: Key Vault Access Test]
    Split --> F5[F5: Table Storage Test]
    
    F2 -->|✓ Pass| F3[F3: API Authentication Test]
    F3 -->|✓ Pass| F4[F4: API Data Fetch Test]
    
    F4 -->|✓ Pass| Converge{All Tests Pass?}
    F5 -->|✓ Pass| Converge
    
    Converge -->|Yes| Prod[Enable Production Functions F6-F8]
    Converge -->|No| Debug[Debug Failed Component]
    
    Debug --> Start
    
    style F1 fill:#e1f5ff
    style F2 fill:#e1f5ff
    style F3 fill:#e1f5ff
    style F4 fill:#e1f5ff
    style F5 fill:#e1f5ff
    style Prod fill:#c8e6c9
```

### Validation Dependencies

| Function | Tests | Depends On | Duration |
|----------|-------|------------|----------|
| F1 | Timer triggers + logging | None | 5 min |
| F2 | Key Vault RBAC | F1 | 10 min |
| F3 | API authentication | F2 | 10 min |
| F4 | API data retrieval | F3 | 10 min |
| F5 | Table Storage write/read | F1 | 10 min |

**Total validation time:** ~45 minutes

---

## 2. Production Data Flow

Production functions run **automatically on schedule** after validation.

```mermaid
sequenceDiagram
    autonumber
    participant API as External API
    participant F6 as F6: Data Collector<br/>(Hourly)
    participant KV as Azure Key Vault
    participant TS as Table Storage
    participant F7 as F7: AI Analyzer<br/>(Daily 9 AM)
    participant AI as Azure OpenAI
    participant F8 as F8: Dashboard<br/>(Daily 9:30 AM)
    participant BS as Blob Storage
    
    Note over F6: Every hour at :00
    F6->>KV: Get API credentials
    KV-->>F6: Return secret
    
    F6->>API: Authenticate (OAuth2/API Key)
    API-->>F6: Access token
    
    F6->>API: Fetch data (with pagination)
    API-->>F6: JSON records (100-1000+)
    
    F6->>TS: Upsert entities<br/>(prevents duplicates)
    TS-->>F6: Confirmation
    
    Note over F7: Next day at 9 AM UTC
    F7->>TS: Query error records<br/>(last 7 days)
    TS-->>F7: Filtered records
    
    F7->>AI: Analyze patterns<br/>+ Generate insights
    AI-->>F7: Analysis report
    
    F7->>TS: Store analysis<br/>(PartitionKey=AI_ANALYSIS)
    
    Note over F8: Daily at 9:30 AM UTC
    F8->>TS: Get summary stats
    F8->>TS: Get latest AI analysis
    TS-->>F8: Data + analysis
    
    F8->>BS: Generate & upload<br/>HTML dashboard
    BS-->>F8: Public URL
```

### Data Collection Process (F6)

**Input:** API credentials from Key Vault  
**Output:** Deduplicated records in Table Storage

1. **Authenticate** - Retrieve credentials, obtain API token
2. **Paginate** - Fetch records in batches (100-1000 per page)
3. **Transform** - Map API fields to storage schema
4. **Upsert** - Insert new or update existing records (prevents duplicates)
5. **Log** - Record stats (new/updated counts)

**Deduplication:** Uses API's unique ID field as `RowKey` - same ID = update, not duplicate.

---

## 3. Component Architecture

Shows how Azure resources interact.

```mermaid
graph TB
    subgraph External
        API[Target API<br/>REST/GraphQL]
        OPENAI[Azure OpenAI<br/>GPT-4]
    end
    
    subgraph "Azure Function App"
        F1_5[Test Functions<br/>F1-F5<br/>Disabled]
        F6[Data Collector<br/>F6<br/>Hourly]
        F7[AI Analyzer<br/>F7<br/>Daily 9AM]
        F8[Dashboard<br/>F8<br/>Daily 9:30AM]
    end
    
    subgraph "Azure Storage Account"
        TS[(Table Storage<br/>ApiData)]
        BS[Blob Storage<br/>$web container]
    end
    
    subgraph Security
        KV[Key Vault<br/>Secrets]
        MI[Managed Identity<br/>RBAC]
    end
    
    subgraph Monitoring
        AI_MON[Application Insights<br/>Logs & Metrics]
    end
    
    API -->|Auth + Data| F6
    F6 -->|Read Secrets| KV
    F6 -->|Write Records| TS
    
    F7 -->|Query Errors| TS
    F7 -->|Analyze| OPENAI
    F7 -->|Store Analysis| TS
    
    F8 -->|Read Data| TS
    F8 -->|Upload HTML| BS
    
    MI -.->|Grants Access| KV
    MI -.->|Grants Access| TS
    
    F1_5 --> AI_MON
    F6 --> AI_MON
    F7 --> AI_MON
    F8 --> AI_MON
    
    User([User Browser]) -->|HTTPS| BS
    
    style F6 fill:#fff9c4
    style F7 fill:#fff9c4
    style F8 fill:#fff9c4
    style API fill:#e1f5ff
    style OPENAI fill:#e1f5ff
```

### Component Roles

| Component | Purpose | Access Method |
|-----------|---------|---------------|
| **Function App** | Serverless compute | Managed Identity |
| **Key Vault** | Store API credentials | RBAC (Secrets User) |
| **Table Storage** | Store API records | RBAC (Table Data Contributor) |
| **Blob Storage** | Host HTML dashboard | RBAC (Blob Data Contributor) |
| **App Insights** | Centralized logging | Connection String |
| **Azure OpenAI** | AI analysis | API Key |

---

## 4. Data Schema

### Table Storage Entity Structure

```json
{
  "PartitionKey": "api_data",
  "RowKey": "unique-id-from-api",
  "EventTimestamp": "2025-10-20T10:30:00Z",
  "Status": "Success",
  "Message": "Operation completed",
  "fetched_at": "2025-10-20T11:00:00Z",
  ...custom fields from FIELD_MAPPING
}
```

**Key Fields:**
- `PartitionKey` - Grouping strategy (static or category-based)
- `RowKey` - Unique identifier (prevents duplicates)
- `fetched_at` - When record was collected
- Custom fields - Mapped from API response via `FIELD_MAPPING`

### AI Analysis Storage

```json
{
  "PartitionKey": "AI_ANALYSIS",
  "RowKey": "2025-10-20T09:00:00Z",
  "analysis": "Full AI-generated report text",
  "records_analyzed": 150,
  "generated_at": "2025-10-20T09:00:00Z"
}
```

---

## 5. Error Handling & Retry Logic

```mermaid
graph LR
    Start[Function Triggered] --> Try{Try Operation}
    
    Try -->|Success| Log[Log Success]
    Try -->|Transient Error| Retry[Retry 2x<br/>5 sec delay]
    Try -->|Permanent Error| Fail[Log Error<br/>+ Continue]
    
    Retry -->|Success| Log
    Retry -->|Still Fails| Fail
    
    Log --> Next[Process Next Record]
    Fail --> Next
    
    Next --> Done[Complete]
    
    style Log fill:#c8e6c9
    style Fail fill:#ffcdd2
```

**Retry Configuration** (in host.json):
- Strategy: Fixed delay
- Max retries: 2
- Delay: 5 seconds

**Partial Success:** If 1 record fails out of 1000, the other 999 still get stored. Errors logged but don't stop processing.

---

## 6. Timing & Schedules

```mermaid
gantt
    title Daily Execution Schedule (UTC)
    dateFormat HH:mm
    axisFormat %H:%M
    
    section Hourly
    Data Collection (F6) :crit, 00:00, 1h
    Data Collection (F6) :crit, 01:00, 1h
    Data Collection (F6) :crit, 02:00, 1h
    
    section Daily Analysis
    AI Analyzer (F7) :active, 09:00, 30m
    Dashboard Gen (F8) :active, 09:30, 10m
```

**Production Schedule:**
- **F6 (Data Collector):** `0 0 */1 * * *` (every hour at :00)
- **F7 (AI Analyzer):** `0 0 9 * * *` (daily at 9:00 AM UTC)
- **F8 (Dashboard):** `0 30 9 * * *` (daily at 9:30 AM UTC)

**Why this timing?**
- F7 runs after 24 hours of F6 collections (enough data to analyze)
- F8 runs 30 min after F7 (ensures analysis is ready)

---

## 7. Security Data Flow

```mermaid
graph TB
    Deploy[Initial Deployment] --> Enable[Enable Managed Identity]
    Enable --> Grant[Grant RBAC Roles]
    
    Grant --> KV_RBAC[Key Vault Secrets User]
    Grant --> TS_RBAC[Table Data Contributor]
    Grant --> BS_RBAC[Blob Data Contributor]
    
    subgraph Runtime
        F[Function Executes] --> Auth[DefaultAzureCredential]
        Auth --> MI[Managed Identity Token]
        MI --> Access[Access Resource]
    end
    
    KV_RBAC -.->|Allows| Runtime
    TS_RBAC -.->|Allows| Runtime
    BS_RBAC -.->|Allows| Runtime
    
    style Grant fill:#fff9c4
    style Access fill:#c8e6c9
```

**Security Flow:**
1. Function app has system-assigned managed identity (like a service account)
2. RBAC roles grant identity access to resources
3. At runtime, `DefaultAzureCredential()` automatically uses managed identity
4. No connection strings or keys in code

**Zero Secrets in Code:**
- API credentials → Key Vault
- Storage access → Managed Identity (RBAC)
- OpenAI key → Environment variable (not in code)

---

## 8. Monitoring & Observability

All functions log to Application Insights:

```mermaid
graph LR
    F1[Function 1-8] -->|logging.info| AI[Application Insights]
    F1 -->|logging.error| AI
    
    AI --> Query[Kusto Queries]
    AI --> Portal[Azure Portal]
    AI --> Alerts[Alerts & Dashboards]
    
    Query --> Troubleshoot[Troubleshoot Issues]
    Portal --> Monitor[Real-time Monitoring]
    Alerts --> Notify[Email/SMS Notifications]
```

**Query Examples:**

```kusto
// View all function executions (last hour)
traces
| where timestamp > ago(1h)
| where message contains "PRODUCTION"
| project timestamp, message

// Find errors
traces
| where severityLevel == 3
| where timestamp > ago(24h)
| project timestamp, message, customDimensions

// Track data collection stats
traces
| where message contains "Stored"
| project timestamp, message
| order by timestamp desc
```

---

## 9. Disaster Recovery

**Data Loss Prevention:**
- Table Storage has built-in replication (3 copies)
- Upsert logic prevents duplicate processing
- Failed records logged but don't stop batch

**Recovery Scenarios:**

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Function fails mid-batch | Partial data stored | Next run fetches all (upsert handles duplicates) |
| API rate limit hit | Collection incomplete | Retry after delay, pagination resumes |
| OpenAI quota exceeded | No analysis generated | Function logs error, retries next day |
| Storage account unavailable | No data written | Function retries 2x, then logs error |

---

## 10. Scaling Considerations

**Current Design:**
- Single function app (consumption plan)
- Handles ~10K records/hour comfortably
- AI analysis limited to 100 records for token efficiency

**Scale Limits:**
| Component | Current | Max Capacity | Scale Solution |
|-----------|---------|--------------|----------------|
| API calls | 1/hour | ~720/hour | Increase schedule frequency |
| Table Storage | Unlimited | Petabytes | Partition by date/category |
| Function timeout | 10 min | 10 min (consumption) | Move to premium plan (30 min) |
| AI analysis | 100 records | ~1000/request | Batch processing or premium model |

**When to Scale:**
- Records > 100K/hour → Use Premium Plan or split by region
- Analysis > 1000 records → Implement batch processing
- Multiple APIs → Deploy separate function apps per API

---

## Summary

**Data Flow Path:**
```
External API 
  → F6 (collect hourly) 
  → Table Storage 
  → F7 (analyze daily) 
  → Azure OpenAI 
  → F8 (dashboard) 
  → Blob Storage 
  → User Browser
```

**Key Principles:**
1. **Progressive validation** - Each step proven before advancing
2. **Deduplication** - RowKey prevents duplicate storage
3. **Resilience** - Partial failures don't stop processing
4. **Security** - Zero secrets in code, all RBAC-based
5. **Observability** - Every action logged to App Insights

**See Also:**
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Technical deep-dive
- [azure-quickstart.md](azure-quickstart.md) - Deployment guide
- [azure-troubleshooting.md](azure-troubleshooting.md) - Common issues