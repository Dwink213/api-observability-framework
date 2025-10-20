# setup-rbac.ps1
# Configures RBAC permissions for Azure Function App to access Key Vault and Storage
# Run this AFTER deploying infrastructure but BEFORE deploying function code

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$FunctionAppName,
    
    [Parameter(Mandatory=$true)]
    [string]$KeyVaultName,
    
    [Parameter(Mandatory=$true)]
    [string]$StorageAccountName,
    
    [Parameter(Mandatory=$false)]
    [switch]$WaitForPropagation
)

# Color functions
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Command { Write-Host $args -ForegroundColor Cyan }

Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "  Azure RBAC Setup Script" -ForegroundColor Magenta
Write-Host "========================================`n" -ForegroundColor Magenta

# Validate Azure CLI is installed
Write-Info "Checking Azure CLI..."
try {
    $azVersion = az version --output json | ConvertFrom-Json
    Write-Success "✓ Azure CLI version: $($azVersion.'azure-cli')"
} catch {
    Write-Error "✗ Azure CLI not found. Install from: https://aka.ms/installazurecli"
    exit 1
}

# Check if logged in
Write-Info "`nChecking Azure login status..."
try {
    $account = az account show --output json | ConvertFrom-Json
    Write-Success "✓ Logged in as: $($account.user.name)"
    Write-Success "✓ Subscription: $($account.name) ($($account.id))"
    $SUB_ID = $account.id
} catch {
    Write-Error "✗ Not logged in to Azure. Run: az login"
    exit 1
}

# Verify resources exist
Write-Info "`nVerifying resources exist..."

Write-Info "Checking Resource Group..."
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Error "✗ Resource Group '$ResourceGroup' not found"
    exit 1
}
Write-Success "✓ Resource Group exists"

Write-Info "Checking Function App..."
try {
    $funcApp = az functionapp show --name $FunctionAppName --resource-group $ResourceGroup --output json 2>$null | ConvertFrom-Json
    if (-not $funcApp) { throw }
    Write-Success "✓ Function App exists"
} catch {
    Write-Error "✗ Function App '$FunctionAppName' not found in Resource Group '$ResourceGroup'"
    exit 1
}

Write-Info "Checking Key Vault..."
try {
    $kv = az keyvault show --name $KeyVaultName --resource-group $ResourceGroup --output json 2>$null | ConvertFrom-Json
    if (-not $kv) { throw }
    Write-Success "✓ Key Vault exists"
} catch {
    Write-Error "✗ Key Vault '$KeyVaultName' not found in Resource Group '$ResourceGroup'"
    exit 1
}

Write-Info "Checking Storage Account..."
try {
    $storage = az storage account show --name $StorageAccountName --resource-group $ResourceGroup --output json 2>$null | ConvertFrom-Json
    if (-not $storage) { throw }
    Write-Success "✓ Storage Account exists"
} catch {
    Write-Error "✗ Storage Account '$StorageAccountName' not found in Resource Group '$ResourceGroup'"
    exit 1
}

# Get or create managed identity
Write-Info "`nConfiguring Managed Identity..."
$identity = az functionapp identity show --name $FunctionAppName --resource-group $ResourceGroup --output json 2>$null | ConvertFrom-Json

if (-not $identity.principalId) {
    Write-Info "Managed Identity not enabled. Enabling..."
    az functionapp identity assign --name $FunctionAppName --resource-group $ResourceGroup --output none
    Start-Sleep -Seconds 10
    $identity = az functionapp identity show --name $FunctionAppName --resource-group $ResourceGroup --output json | ConvertFrom-Json
}

$PRINCIPAL_ID = $identity.principalId
Write-Success "✓ Managed Identity Principal ID: $PRINCIPAL_ID"

# Build resource scopes
$kvScope = "/subscriptions/$SUB_ID/resourceGroups/$ResourceGroup/providers/Microsoft.KeyVault/vaults/$KeyVaultName"
$storageScope = "/subscriptions/$SUB_ID/resourceGroups/$ResourceGroup/providers/Microsoft.Storage/storageAccounts/$StorageAccountName"

Write-Info "`nGranting RBAC Permissions..."
Write-Host "This may take a moment...`n"

# Grant Key Vault Secrets User role
Write-Info "[1/3] Key Vault Secrets User..."
try {
    az role assignment create `
        --role "Key Vault Secrets User" `
        --assignee $PRINCIPAL_ID `
        --scope $kvScope `
        --output none 2>$null
    Write-Success "✓ Key Vault Secrets User role granted"
} catch {
    # Check if role already exists
    $existing = az role assignment list --assignee $PRINCIPAL_ID --scope $kvScope --role "Key Vault Secrets User" --output json | ConvertFrom-Json
    if ($existing.Count -gt 0) {
        Write-Success "✓ Key Vault Secrets User role already assigned"
    } else {
        Write-Error "✗ Failed to assign Key Vault Secrets User role"
        Write-Error $_.Exception.Message
    }
}

# Grant Storage Table Data Contributor role
Write-Info "[2/3] Storage Table Data Contributor..."
try {
    az role assignment create `
        --role "Storage Table Data Contributor" `
        --assignee $PRINCIPAL_ID `
        --scope $storageScope `
        --output none 2>$null
    Write-Success "✓ Storage Table Data Contributor role granted"
} catch {
    $existing = az role assignment list --assignee $PRINCIPAL_ID --scope $storageScope --role "Storage Table Data Contributor" --output json | ConvertFrom-Json
    if ($existing.Count -gt 0) {
        Write-Success "✓ Storage Table Data Contributor role already assigned"
    } else {
        Write-Error "✗ Failed to assign Storage Table Data Contributor role"
        Write-Error $_.Exception.Message
    }
}

# Grant Storage Blob Data Contributor role (for function artifacts)
Write-Info "[3/3] Storage Blob Data Contributor..."
try {
    az role assignment create `
        --role "Storage Blob Data Contributor" `
        --assignee $PRINCIPAL_ID `
        --scope $storageScope `
        --output none 2>$null
    Write-Success "✓ Storage Blob Data Contributor role granted"
} catch {
    $existing = az role assignment list --assignee $PRINCIPAL_ID --scope $storageScope --role "Storage Blob Data Contributor" --output json | ConvertFrom-Json
    if ($existing.Count -gt 0) {
        Write-Success "✓ Storage Blob Data Contributor role already assigned"
    } else {
        Write-Error "✗ Failed to assign Storage Blob Data Contributor role"
        Write-Error $_.Exception.Message
    }
}

# Verify role assignments
Write-Info "`nVerifying role assignments..."
$roles = az role assignment list --assignee $PRINCIPAL_ID --all --output json | ConvertFrom-Json
$kvRole = $roles | Where-Object { $_.roleDefinitionName -eq "Key Vault Secrets User" -and $_.scope -eq $kvScope }
$tableRole = $roles | Where-Object { $_.roleDefinitionName -eq "Storage Table Data Contributor" -and $_.scope -eq $storageScope }
$blobRole = $roles | Where-Object { $_.roleDefinitionName -eq "Storage Blob Data Contributor" -and $_.scope -eq $storageScope }

if ($kvRole) { Write-Success "✓ Key Vault Secrets User verified" } else { Write-Error "✗ Key Vault role not found" }
if ($tableRole) { Write-Success "✓ Storage Table Data Contributor verified" } else { Write-Error "✗ Storage Table role not found" }
if ($blobRole) { Write-Success "✓ Storage Blob Data Contributor verified" } else { Write-Error "✗ Storage Blob role not found" }

# RBAC propagation warning
Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "  ⚠️  IMPORTANT" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Magenta
Write-Info "`nRBAC permissions can take 5-10 minutes to propagate."

if ($WaitForPropagation) {
    Write-Info "Waiting 5 minutes for propagation..."
    Write-Info "You can press Ctrl+C to skip waiting (at your own risk)"
    Start-Sleep -Seconds 300
    Write-Success "✓ Wait complete"
    
    Write-Info "`nRestarting function app to pick up new permissions..."
    az functionapp restart --name $FunctionAppName --resource-group $ResourceGroup --output none
    Write-Success "✓ Function app restarted"
} else {
    Write-Info "To wait for propagation, re-run with -WaitForPropagation flag"
    Write-Info "Or manually wait 5 minutes and restart the function app:"
    Write-Command "`naz functionapp restart --name $FunctionAppName --resource-group $ResourceGroup"
}

# Next steps
Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "  ✅ RBAC Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Magenta

Write-Info "`nNext Steps:"
Write-Host "1. Wait 5 minutes (if you haven't already)" -ForegroundColor White
Write-Host "2. Configure app settings (.env → Function App Configuration)" -ForegroundColor White
Write-Host "3. Store secrets in Key Vault" -ForegroundColor White
Write-Host "4. Deploy function code" -ForegroundColor White
Write-Host "5. Test Function 1 (timer validation)" -ForegroundColor White

Write-Info "`nUseful Commands:"
Write-Command "# Check role assignments"
Write-Host "az role assignment list --assignee $PRINCIPAL_ID --all -o table`n"

Write-Command "# Restart function app"
Write-Host "az functionapp restart --name $FunctionAppName --resource-group $ResourceGroup`n"

Write-Command "# View function logs"
Write-Host "az monitor app-insights query --app <insights-name> --analytics-query 'traces | where timestamp > ago(10m)'`n"

Write-Success "`n✨ Setup complete! Check docs/azure-troubleshooting.md if you encounter issues.`n"