# Quick Start: Clone to Deploy in 30 Minutes

## Prerequisites
- Azure subscription
- Azure CLI installed
- Git
- VSCode with Azure Functions extension (recommended)

---

## Step 1: Clone & Configure (5 min)

```powershell
# Clone repository
git clone https://github.com/Dwink213/api-observability-framework.git
cd api-observability-framework

# Copy environment template
cp .env.example .env

# Edit .env with your API details
code .env
```

**Required in .env:**
- `API_BASE_URL` - Your API endpoint
- `API_AUTH_TYPE` - oauth2, apikey, or bearer
- `API_KEY_SECRET_NAME` - Name for secret in Key Vault
- `API_DATA_ENDPOINT` - Path to data endpoint
- `API_ID_FIELD` - Unique ID field name
- `API_TIMESTAMP_FIELD` - Timestamp field name

---

## Step 2: Deploy Azure Infrastructure (10 min)

```powershell
# Login
az login
az account set --subscription "<your-subscription>"

# Create resource group
$RG = "api-observability-rg"
$REGION = "eastus2"
az group create --name $RG --location $REGION

# Deploy Bicep (creates Function App, KeyVault, Storage, App Insights)
cd infrastructure/bicep
az deployment group create `
  --resource-group $RG `
  --template-file main.bicep `
  --parameters `
    functionAppName="api-obs-func" `
    keyVaultName="api-obs-kv" `
    storageAccountName="apiobsstorage"
```

---

## Step 3: Configure RBAC Permissions (5 min)

```powershell
# Run RBAC setup script
cd ../../scripts/azure
.\setup-rbac.ps1 `
  -ResourceGroup "api-observability-rg" `
  -FunctionAppName "api-obs-func" `
  -KeyVaultName "api-obs-kv" `
  -StorageAccountName "apiobsstorage" `
  -WaitForPropagation
```

**What this does:**
- ✅ Grants Key Vault Secrets User role
- ✅ Grants Storage Table Data Contributor role
- ✅ Grants Storage Blob Data Contributor role
- ✅ Waits 5 minutes for propagation
- ✅ Restarts function app

---

## Step 4: Store API Credentials (2 min)

```powershell
# Store your API key in Key Vault
az keyvault secret set `
  --vault-name "api-obs-kv" `
  --name "api-key" `
  --value "<your-actual-api-key>"

# For OAuth2 (if applicable):
az keyvault secret set `
  --vault-name "api-obs-kv" `
  --name "oauth-client-id" `
  --value "<client-id>"

az keyvault secret set `
  --vault-name "api-obs-kv" `
  --name "oauth-client-secret" `
  --value "<client-secret>"
```

---

## Step 5: Configure Function App Settings (3 min)

```powershell
# Get storage connection string
$STORAGE_CONN = az storage account show-connection-string `
  --name "apiobsstorage" `
  --resource-group "api-observability-rg" `
  --query connectionString -o tsv

# Push settings from .env to Function App
az functionapp config appsettings set `
  --name "api-obs-func" `
  --resource-group "api-observability-rg" `
  --settings `
    KEY_VAULT_URL="https://api-obs-kv.vault.azure.net" `
    API_BASE_URL="<from-your-.env>" `
    API_AUTH_TYPE="<from-your-.env>" `
    API_KEY_SECRET_NAME="api-key" `
    API_DATA_ENDPOINT="<from-your-.env>" `
    API_ID_FIELD="<from-your-.env>" `
    API_TIMESTAMP_FIELD="<from-your-.env>" `
    STORAGE_CONNECTION_STRING="$STORAGE_CONN" `
    STORAGE_TABLE_NAME="ApiData"
```

---

## Step 6: Deploy Function Code (5 min)

```powershell
# Navigate to functions folder
cd ../../src/functions

# Deploy to Azure
func azure functionapp publish api-obs-func --python
```

**Expected output:**
```
Functions in api-obs-func:
    test_timer_and_logging - [timerTrigger]
    test_keyvault_access - [timerTrigger]
    test_api_auth - [timerTrigger]
    test_api_fetch - [timerTrigger]
    test_table_storage - [timerTrigger]
    api_data_collector - [timerTrigger]
    ai_data_analyzer - [timerTrigger]
    generate_dashboard - [timerTrigger]
```

---

## Step 7: Validate Setup (15 min)

### Enable Test Function 1
```powershell
# In test_functions.py, change F1 schedule:
schedule="*/10 * * * *"  # Enable (runs every 10 min)

# Redeploy
func azure functionapp publish api-obs-func --python
```

**Wait 10 minutes, then check logs:**
```powershell
az monitor app-insights query `
  --app "api-obs-insights" `
  --analytics-query "traces | where timestamp > ago(15m) and message contains 'TEST 1' | project timestamp, message"
```

**Expected:** See "TEST 1: Timer trigger executed successfully"

✅ **F1 Passed** - Continue to F2

---

### Enable Test Functions 2-5 (One at a Time)

**Repeat for each function:**
1. Change schedule to `"*/10 * * * *"`
2. Redeploy: `func azure functionapp publish api-obs-func`
3. Wait 10 minutes
4. Check logs for success message
5. Once validated, change schedule back to `"0 0 1 1 1 2099"` (disable)

**Validation queries:**
```powershell
# F2 - Key Vault
# Expected: "Retrieved API key (length: X)"

# F3 - API Auth
# Expected: "TEST 3: PASSED - API authentication works"

# F4 - API Fetch
# Expected: "Retrieved X records from API"

# F5 - Table Storage
# Expected: "TEST 5: PASSED - Table Storage works"
```

---

## Step 8: Enable Production (2 min)

**All test functions passed? Enable production collection:**

Production functions are already enabled by default:
- ✅ F6 (api_data_collector) - Runs hourly
- ✅ F7 (ai_data_analyzer) - Runs daily at 9 AM UTC
- ✅ F8 (generate_dashboard) - Runs daily at 9:30 AM UTC

**No changes needed!** Production collection starts automatically.

---

## Verify Production

**After 1 hour, check data collection:**
```powershell
# Check if table has data
az storage table list `
  --account-name apiobsstorage `
  --query "[?name=='ApiData']"

# View logs
az monitor app-insights query `
  --app "api-obs-insights" `
  --analytics-query "traces | where timestamp > ago(1h) and message contains 'PRODUCTION' | project timestamp, message"
```

**Expected:** See "Data collection completed successfully"

---

## Access Dashboard

**After 24 hours (when F7 runs):**

1. Enable static website hosting:
```powershell
az storage blob service-properties update `
  --account-name apiobsstorage `
  --static-website `
  --index-document index.html
```

2. Get dashboard URL:
```powershell
az storage account show `
  --name apiobsstorage `
  --resource-group api-observability-rg `
  --query "primaryEndpoints.web" -o tsv
```

3. Open URL in browser

---

## Troubleshooting

**403 Forbidden errors?**
```powershell
# Re-run RBAC script and wait 5 min
.\scripts\azure\setup-rbac.ps1 -ResourceGroup "api-observability-rg" -FunctionAppName "api-obs-func" -KeyVaultName "api-obs-kv" -StorageAccountName "apiobsstorage" -WaitForPropagation
```

**Secret not found?**
```powershell
# List secrets (verify name matches exactly)
az keyvault secret list --vault-name "api-obs-kv" -o table
```

**Functions not triggering?**
```powershell
# Check function app status
az functionapp show --name "api-obs-func" --resource-group "api-observability-rg" --query "state"
```

**See [docs/azure-troubleshooting.md](docs/azure-troubleshooting.md) for complete troubleshooting guide.**

---

## Success! 🎉

You now have:
- ✅ Automated hourly data collection
- ✅ Daily AI-powered analysis
- ✅ HTML dashboard with insights
- ✅ Centralized logging

**Next steps:**
- Customize field mapping in .env
- Adjust collection frequency (F6 schedule)
- Configure AI analysis prompts
- Set up alerts in Azure Monitor