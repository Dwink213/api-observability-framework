# Azure Deployment Troubleshooting Guide

> **Critical:** This document contains the **actual commands** you need to fix permission errors. Bookmark this page.

---

## 🚨 The #1 Issue: RBAC Permissions

**90% of deployment failures are missing RBAC role assignments.**

Azure uses **managed identities** for serverless functions. Your function app has an identity (like a user account), but by default it has **zero permissions** to access Key Vault or Storage.

---

## ⚡ Quick Fix Commands

### Get Your Function's Identity
```powershell
# Get the managed identity's principal ID (like a user ID)
$FUNC_IDENTITY = az functionapp identity show `
  --name <your-function-app-name> `
  --resource-group <your-rg-name> `
  --query principalId -o tsv

# Verify it worked (should see a GUID)
echo $FUNC_IDENTITY
```

### Grant Key Vault Access
```powershell
# Give function permission to read secrets
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv-name>

# Alternative: More permissive (if you need to SET secrets too)
az role assignment create `
  --role "Key Vault Secrets Officer" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv-name>
```

### Grant Table Storage Access
```powershell
# Give function permission to read/write table data
az role assignment create `
  --role "Storage Table Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-name>
```

---

## 📋 Complete Setup Checklist

Run these **AFTER** deploying your function app but **BEFORE** running functions:

```powershell
# 1. Get subscription ID
$SUB_ID = az account show --query id -o tsv

# 2. Set your resource names
$RG = "your-rg-name"
$FUNC_APP = "your-function-app-name"
$KV_NAME = "your-keyvault-name"
$STORAGE_NAME = "your-storage-account-name"

# 3. Get function's managed identity
$FUNC_IDENTITY = az functionapp identity show `
  --name $FUNC_APP `
  --resource-group $RG `
  --query principalId -o tsv

echo "Function Identity: $FUNC_IDENTITY"

# 4. Grant Key Vault access
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $FUNC_IDENTITY `
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.KeyVault/vaults/$KV_NAME"

# 5. Grant Storage Table access
az role assignment create `
  --role "Storage Table Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$STORAGE_NAME"

# 6. Grant Storage Blob access (for function app itself)
az role assignment create `
  --role "Storage Blob Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$STORAGE_NAME"

echo "✅ All RBAC permissions granted"
```

---

## 🔍 Common Errors & Fixes

### Error: "403 Forbidden" when accessing Key Vault

**Symptom:**
```
azure.core.exceptions.HttpResponseError: (Forbidden) 
The user, group or application does not have secrets get permission
```

**Cause:** Missing Key Vault RBAC role

**Fix:**
```powershell
# Option 1: Read-only access (recommended for production)
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv>

# Option 2: Read/write access (if you need to SET secrets from function)
az role assignment create `
  --role "Key Vault Secrets Officer" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv>
```

**Verify it worked:**
```powershell
# Check role assignments
az role assignment list `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv> `
  -o table
```

---

### Error: "AuthorizationFailure" when accessing Table Storage

**Symptom:**
```
azure.core.exceptions.HttpResponseError: (AuthorizationFailure)
This request is not authorized to perform this operation
```

**Cause:** Missing Storage RBAC role

**Fix:**
```powershell
# Grant table access
az role assignment create `
  --role "Storage Table Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>
```

**Verify it worked:**
```powershell
# Check role assignments
az role assignment list `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage> `
  -o table
```

---

### Error: "DefaultAzureCredential failed to retrieve a token"

**Symptom:**
```
azure.identity.CredentialUnavailableError: 
DefaultAzureCredential failed to retrieve a token from the included credentials
```

**Cause:** Function app doesn't have a managed identity enabled

**Fix:**
```powershell
# Enable system-assigned managed identity
az functionapp identity assign `
  --name <function-app-name> `
  --resource-group <rg-name>

# Verify it was created
az functionapp identity show `
  --name <function-app-name> `
  --resource-group <rg-name>
```

---

### Error: Key Vault uses "Access Policies" not RBAC

**Symptom:**
```
Error: The vault does not have RBAC authorization enabled
```

**Cause:** Key Vault was created with legacy "Access Policies" instead of RBAC

**Option 1: Enable RBAC on existing Key Vault**
```powershell
# Update Key Vault to use RBAC
az keyvault update `
  --name <kv-name> `
  --resource-group <rg-name> `
  --enable-rbac-authorization true
```

**Option 2: Use Access Policies Instead (Legacy)**
```powershell
# Grant access via policy (not RBAC)
az keyvault set-policy `
  --name <kv-name> `
  --resource-group <rg-name> `
  --object-id $FUNC_IDENTITY `
  --secret-permissions get list
```

**Recommendation:** Use RBAC (Option 1) for new deployments. It's the modern approach and integrates better with Azure governance.

---

### Error: "Secret not found"

**Symptom:**
```
azure.core.exceptions.ResourceNotFoundError: 
Secret not found: my-secret-name
```

**Cause:** Secret doesn't exist or name mismatch

**Fix:**
```powershell
# List all secrets in Key Vault
az keyvault secret list --vault-name <kv-name> -o table

# Verify exact secret name (case-sensitive!)
az keyvault secret show --vault-name <kv-name> --name <secret-name>

# Create secret if missing
az keyvault secret set `
  --vault-name <kv-name> `
  --name <secret-name> `
  --value "<secret-value>"
```

---

### Error: RBAC role assignments take too long to propagate

**Symptom:** Role assigned successfully but function still gets 403 errors

**Cause:** Azure RBAC propagation delay (can take 5-10 minutes)

**Fix:**
```powershell
# Wait and retry
Start-Sleep -Seconds 300  # Wait 5 minutes

# Force function app restart to pick up new permissions
az functionapp restart `
  --name <function-app-name> `
  --resource-group <rg-name>

# Verify role assignment propagated
az role assignment list `
  --assignee $FUNC_IDENTITY `
  --all `
  -o table
```

---

## 🎯 Role Assignment Reference

### Key Vault Roles

| Role | Permissions | Use Case |
|------|-------------|----------|
| **Key Vault Secrets User** | Read secrets | Function reads API keys (recommended) |
| **Key Vault Secrets Officer** | Read + Write secrets | Function creates/updates secrets |
| **Key Vault Administrator** | Full control | Deployment scripts only |

### Storage Roles

| Role | Permissions | Use Case |
|------|-------------|----------|
| **Storage Table Data Contributor** | Read/Write tables | Function stores data (recommended) |
| **Storage Table Data Reader** | Read-only tables | Read-only analytics |
| **Storage Blob Data Contributor** | Read/Write blobs | Function app artifacts |

---

## 🔧 Diagnostic Commands

### Check What Roles a Function Has
```powershell
# Get function identity
$FUNC_IDENTITY = az functionapp identity show `
  --name <func-app> `
  --resource-group <rg> `
  --query principalId -o tsv

# List ALL role assignments for this function
az role assignment list `
  --assignee $FUNC_IDENTITY `
  --all `
  -o table
```

### Check Who Has Access to Key Vault
```powershell
# List all role assignments on Key Vault
az role assignment list `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv> `
  -o table
```

### Check Who Has Access to Storage
```powershell
# List all role assignments on Storage Account
az role assignment list `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage> `
  -o table
```

### Verify Key Vault RBAC Mode
```powershell
# Check if Key Vault uses RBAC or Access Policies
az keyvault show `
  --name <kv-name> `
  --resource-group <rg-name> `
  --query "properties.enableRbacAuthorization"

# Output:
# true  = Uses RBAC (modern)
# false = Uses Access Policies (legacy)
```

---

## 📖 Complete Deployment Flow

**Use this as your deployment checklist:**

### 1. Deploy Infrastructure (Bicep)
```powershell
az deployment group create `
  --resource-group <rg> `
  --template-file main.bicep `
  --parameters @params.json
```

### 2. Enable Managed Identity (if not in Bicep)
```powershell
az functionapp identity assign `
  --name <func-app> `
  --resource-group <rg>
```

### 3. Get Function Identity
```powershell
$FUNC_IDENTITY = az functionapp identity show `
  --name <func-app> `
  --resource-group <rg> `
  --query principalId -o tsv
```

### 4. Grant Key Vault Access
```powershell
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv>
```

### 5. Grant Storage Access
```powershell
az role assignment create `
  --role "Storage Table Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>
```

### 6. Configure App Settings
```powershell
az functionapp config appsettings set `
  --name <func-app> `
  --resource-group <rg> `
  --settings `
    SECRETS_MANAGER_URL=https://<kv-name>.vault.azure.net `
    API_BASE_URL=https://api.example.com `
    STORAGE_CONNECTION_STRING="<connection-string>"
```

### 7. Store Secrets in Key Vault
```powershell
az keyvault secret set `
  --vault-name <kv-name> `
  --name api-key `
  --value "<your-api-key>"
```

### 8. Deploy Function Code
```powershell
func azure functionapp publish <func-app>
```

### 9. Wait for RBAC Propagation
```powershell
Start-Sleep -Seconds 300  # 5 minutes
```

### 10. Test Function
```powershell
# Trigger manually or wait for timer
az functionapp function show `
  --name <func-app> `
  --resource-group <rg> `
  --function-name <function-name>
```

### 11. Check Logs
```powershell
az monitor app-insights query `
  --app <app-insights-name> `
  --analytics-query "traces | where timestamp > ago(10m) | order by timestamp desc"
```

---

## 🚀 Copy-Paste Script (All-in-One)

**Save this as `setup-rbac.ps1` and run after deployment:**

```powershell
# Configuration - UPDATE THESE
$RG = "your-rg-name"
$FUNC_APP = "your-function-app-name"
$KV_NAME = "your-keyvault-name"
$STORAGE_NAME = "your-storage-account-name"

# Get subscription ID
$SUB_ID = az account show --query id -o tsv
Write-Host "Subscription: $SUB_ID" -ForegroundColor Green

# Get function identity
Write-Host "`nGetting function app identity..." -ForegroundColor Yellow
$FUNC_IDENTITY = az functionapp identity show `
  --name $FUNC_APP `
  --resource-group $RG `
  --query principalId -o tsv

if (-not $FUNC_IDENTITY) {
    Write-Host "ERROR: Function identity not found. Enabling managed identity..." -ForegroundColor Red
    az functionapp identity assign --name $FUNC_APP --resource-group $RG
    $FUNC_IDENTITY = az functionapp identity show --name $FUNC_APP --resource-group $RG --query principalId -o tsv
}

Write-Host "Function Identity: $FUNC_IDENTITY" -ForegroundColor Green

# Grant Key Vault access
Write-Host "`nGranting Key Vault access..." -ForegroundColor Yellow
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $FUNC_IDENTITY `
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.KeyVault/vaults/$KV_NAME"

# Grant Table Storage access
Write-Host "Granting Table Storage access..." -ForegroundColor Yellow
az role assignment create `
  --role "Storage Table Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$STORAGE_NAME"

# Grant Blob Storage access
Write-Host "Granting Blob Storage access..." -ForegroundColor Yellow
az role assignment create `
  --role "Storage Blob Data Contributor" `
  --assignee $FUNC_IDENTITY `
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$STORAGE_NAME"

Write-Host "`n✅ All RBAC permissions granted!" -ForegroundColor Green
Write-Host "Wait 5 minutes for propagation, then restart function app:" -ForegroundColor Yellow
Write-Host "az functionapp restart --name $FUNC_APP --resource-group $RG" -ForegroundColor Cyan
```

---

## 💡 Pro Tips

1. **Always wait 5 minutes after role assignments** before testing functions
2. **Restart function app** after granting permissions: `az functionapp restart`
3. **Use RBAC over Access Policies** for new deployments (modern approach)
4. **Store the .\scripts\azure\setup-rbac.ps1 ` script** in your repo for repeatable deployments
5. **Check logs in Application Insights** - 90% of issues show up there first

---

## 📞 Still Stuck?

### Check These First:
1. ✅ Function app has managed identity enabled
2. ✅ RBAC roles assigned (use diagnostic commands above)
3. ✅ Waited 5+ minutes after role assignment
4. ✅ Function app restarted after permissions granted
5. ✅ Secrets exist in Key Vault with correct names
6. ✅ App settings reference correct Key Vault URL

### Get Help:
- Check Application Insights logs
- Run diagnostic commands from this guide
- Verify role assignments with `az role assignment list`
- Post in GitHub Discussions with error message + logs

---

**Save this document.** You'll need it every deployment. 🎯