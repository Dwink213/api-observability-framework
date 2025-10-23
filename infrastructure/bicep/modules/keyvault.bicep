// Key Vault Module
// Creates Azure Key Vault with RBAC authorization

@description('Key Vault name')
param keyVaultName string

@description('Location for resources')
param location string

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Outputs
output keyVaultName string = keyVault.name
output keyVaultUrl string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id