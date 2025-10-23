# Azure Infrastructure - Bicep Deployment

## Resources Deployed

- **Function App** (Consumption plan, Python 3.11, Linux)
- **Storage Account** (Table Storage + Blob Storage for dashboard)
- **Key Vault** (RBAC-enabled for secure credential storage)
- **Application Insights** (Centralized logging)
- **RBAC Assignments** (Function → KeyVault, Storage)

---

## Prerequisites

- Azure CLI installed
- Azure subscription
- Contributor access to subscription/resource group

---

## Quick Deploy

```powershell
# Login
az login
az account set --subscription "<your-subscription>"

# Create resource group
az group create --name api-observability-rg --location eastus2

# Deploy infrastructure
az deployment group create `
  --resource-group api-observability-rg `
  --template-file main.bicep `
  --parameters baseName=api-obs environment=dev

# Get outputs
az deployment group show `
  --resource-group api-observability-rg `
  --name main `
  --query properties.outputs
```

---

## Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `location` | Azure region | Resource group location | No |
| `baseName` | Base name for resources | `api-obs` | No |
| `environment` | Environment (dev/staging/prod) | `dev` | No |
| `enableOpenAI` | Deploy Azure OpenAI | `false` | No |

---

## Custom Deployment

```powershell
az deployment group create `
  --resource-group <your-rg> `
  --template-file main.bicep `
  --parameters `
    baseName=myapp `
    environment=prod `
    location=westus2
```

---

## What Gets Created

```
Resource Group
├── myapp-func-prod (Function App)
│   └── System-assigned Managed Identity
├── myapp-func-prod-plan (App Service Plan - Consumption)
├── myappst<unique> (Storage Account)
│   ├── Table Service (for data)
│   └── Blob Service ($web for dashboard)
├── myapp-kv-<unique> (Key Vault)
├── myapp-insights-prod (Application Insights)
└── myapp-insights-prod-workspace (Log Analytics)
```

---

## RBAC Assignments

Automatically configured:
- Function → Key Vault: **Key Vault Secrets User**
- Function → Storage Tables: **Storage Table Data Contributor**
- Function → Storage Blobs: **Storage Blob Data Contributor**

**Note:** RBAC propagation takes 5-10 minutes. Wait before deploying functions.

---

## Outputs

After deployment, get connection details:

```powershell
$outputs = az deployment group show `
  --resource-group api-observability-rg `
  --name main `
  --query properties.outputs -o json | ConvertFrom-Json

$keyVaultUrl = $outputs.keyVaultUrl.value
$storageConn = $outputs.storageConnectionString.value
$funcApp = $outputs.functionAppName.value

Write-Host "Key Vault URL: $keyVaultUrl"
Write-Host "Function App: $funcApp"
```

---

## Next Steps

1. **Wait 5 minutes** for RBAC propagation
2. **Store API credentials** in Key Vault:
   ```powershell
   az keyvault secret set `
     --vault-name <kv-name> `
     --name api-key `
     --value "<your-api-key>"
   ```
3. **Configure Function App settings** (see docs/azure-quickstart.md)
4. **Deploy function code** from `src/functions/`

---

## Validation

```powershell
# Check resources
az resource list --resource-group api-observability-rg -o table

# Verify RBAC assignments
$principalId = az functionapp identity show `
  --name <func-app-name> `
  --resource-group api-observability-rg `
  --query principalId -o tsv

az role assignment list --assignee $principalId --all -o table
```

---

## Clean Up

```powershell
az group delete --name api-observability-rg --yes --no-wait
```

---

## Troubleshooting

**Deployment fails with "name already exists":**
- Storage/KeyVault names are globally unique
- Change `baseName` parameter or delete existing resources

**Function can't access KeyVault:**
- Wait 5-10 minutes for RBAC propagation
- Run: `.\scripts\azure\setup-rbac.ps1` to verify/reset permissions

**See [docs/azure-troubleshooting.md](../../docs/azure-troubleshooting.md) for complete guide.**