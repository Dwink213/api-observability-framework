// API Observability Framework - Main Deployment
// Deploys Function App, Storage, Key Vault, and Monitoring

targetScope = 'resourceGroup'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Base name for resources (will be suffixed)')
param baseName string = 'api-obs'

@description('Environment (dev, staging, prod)')
param environment string = 'dev'

@description('Enable Azure OpenAI for AI analysis')
param enableOpenAI bool = false

// Generate unique suffix for globally unique resources
var uniqueSuffix = uniqueString(resourceGroup().id)

// Resource names
var functionAppName = '${baseName}-func-${environment}'
var keyVaultName = '${baseName}-kv-${uniqueSuffix}'
var storageAccountName = toLower('${baseName}st${uniqueSuffix}')
var appInsightsName = '${baseName}-insights-${environment}'

// Deploy Storage Account
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    storageAccountName: storageAccountName
    location: location
  }
}

// Deploy Key Vault
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    keyVaultName: keyVaultName
    location: location
  }
}

// Deploy Application Insights
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-deployment'
  params: {
    appInsightsName: appInsightsName
    location: location
  }
}

// Deploy Function App
module functionApp 'modules/function-app.bicep' = {
  name: 'functionapp-deployment'
  params: {
    functionAppName: functionAppName
    location: location
    storageAccountName: storage.outputs.storageAccountName
    appInsightsInstrumentationKey: monitoring.outputs.instrumentationKey
    appInsightsConnectionString: monitoring.outputs.connectionString
  }
}

// Grant Function App access to Key Vault
resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionApp.outputs.principalId, keyVault.outputs.keyVaultId, 'Key Vault Secrets User')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grant Function App access to Storage Tables
resource storageTableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionApp.outputs.principalId, storage.outputs.storageAccountId, 'Storage Table Data Contributor')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3') // Storage Table Data Contributor
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grant Function App access to Storage Blobs
resource storageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionApp.outputs.principalId, storage.outputs.storageAccountId, 'Storage Blob Data Contributor')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output functionAppUrl string = functionApp.outputs.functionAppUrl
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUrl string = keyVault.outputs.keyVaultUrl
output storageAccountName string = storage.outputs.storageAccountName
output appInsightsName string = monitoring.outputs.appInsightsName
output storageConnectionString string = storage.outputs.connectionString