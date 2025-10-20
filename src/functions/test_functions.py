"""
API Observability Framework - Test Functions
Five validation functions that progressively test each capability.
All disabled by default - enable one at a time during setup.
"""

import os
import logging
import requests
from datetime import datetime
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

app = func.FunctionApp()

# ============================================================================
# FUNCTION 1: Test Timer and Logging
# Purpose: Verify timer triggers fire and logs reach Application Insights
# Dependencies: None
# Schedule: Disabled by default
# Enable: Change schedule to "*/10 * * * *" for testing
# ============================================================================
@app.timer_trigger(schedule="0 0 1 1 1 2099", arg_name="timer", run_on_startup=False, use_monitor=False)
def test_timer_and_logging(timer: func.TimerRequest) -> None:
    """Test that timer triggers execute and logs appear in Application Insights."""
    logging.info("=" * 60)
    logging.info("TEST 1: Timer trigger executed successfully")
    logging.info("TEST 1: Logging to Application Insights works")
    logging.info("=" * 60)


# ============================================================================
# FUNCTION 2: Test Key Vault Access
# Purpose: Verify managed identity can read API credentials from Key Vault
# Dependencies: Function 1 must pass
# Schedule: Disabled by default
# Enable: Change schedule to "*/10 * * * *" for testing
# ============================================================================
@app.timer_trigger(schedule="0 0 1 1 1 2099", arg_name="timer", run_on_startup=False, use_monitor=False)
def test_keyvault_access(timer: func.TimerRequest) -> None:
    """Test that function can retrieve secrets from Azure Key Vault via managed identity."""
    logging.info("=" * 60)
    logging.info("TEST 2: Key Vault Access Test Started")
    
    try:
        # Read Key Vault configuration
        key_vault_url = os.environ["KEY_VAULT_URL"]
        auth_type = os.environ.get("API_AUTH_TYPE", "apikey")
        
        # Authenticate as managed identity
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=key_vault_url, credential=credential)
        
        # Retrieve credentials based on auth type
        if auth_type == "oauth2":
            client_id_secret = os.environ["API_CLIENT_ID_SECRET_NAME"]
            client_secret_secret = os.environ["API_CLIENT_SECRET_SECRET_NAME"]
            
            client_id = client.get_secret(client_id_secret).value
            client_secret = client.get_secret(client_secret_secret).value
            
            logging.info(f"Retrieved client_id (length: {len(client_id)})")
            logging.info(f"Retrieved client_secret (length: {len(client_secret)})")
            
        elif auth_type in ["apikey", "bearer"]:
            api_key_secret = os.environ["API_KEY_SECRET_NAME"]
            api_key = client.get_secret(api_key_secret).value
            
            logging.info(f"Retrieved API key (length: {len(api_key)})")
        
        else:
            raise ValueError(f"Unsupported auth type: {auth_type}")
        
        logging.info("TEST 2: PASSED - Key Vault access works")
        
    except Exception as e:
        logging.error(f"TEST 2: FAILED - {str(e)}", exc_info=True)
        return
    
    logging.info("=" * 60)


# ============================================================================
# FUNCTION 3: Test API Authentication
# Purpose: Verify API credentials can successfully authenticate
# Dependencies: Function 2 must pass
# Schedule: Disabled by default
# Enable: Change schedule to "*/10 * * * *" for testing
# ============================================================================
@app.timer_trigger(schedule="0 0 1 1 1 2099", arg_name="timer", run_on_startup=False, use_monitor=False)
def test_api_auth(timer: func.TimerRequest) -> None:
    """Test that API authentication works (OAuth2, API Key, or Bearer token)."""
    logging.info("=" * 60)
    logging.info("TEST 3: API Authentication Test Started")
    
    try:
        # Read configuration
        key_vault_url = os.environ["KEY_VAULT_URL"]
        api_base_url = os.environ["API_BASE_URL"]
        auth_type = os.environ.get("API_AUTH_TYPE", "apikey")
        
        # Retrieve credentials from Key Vault
        credential = DefaultAzureCredential()
        kv_client = SecretClient(vault_url=key_vault_url, credential=credential)
        
        # Test authentication based on type
        if auth_type == "oauth2":
            # OAuth2 token acquisition
            token_url = os.environ["API_TOKEN_URL"]
            client_id = kv_client.get_secret(os.environ["API_CLIENT_ID_SECRET_NAME"]).value
            client_secret = kv_client.get_secret(os.environ["API_CLIENT_SECRET_SECRET_NAME"]).value
            
            payload = {"client_id": client_id, "client_secret": client_secret}
            response = requests.post(token_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            response.raise_for_status()
            
            token = response.json().get("access_token")
            if not token:
                raise ValueError("No access_token in response")
            
            logging.info(f"OAuth2 token acquired (length: {len(token)})")
            
        elif auth_type == "apikey":
            # API Key authentication - test with simple GET
            api_key = kv_client.get_secret(os.environ["API_KEY_SECRET_NAME"]).value
            test_endpoint = os.environ.get("API_TEST_ENDPOINT", "/")
            
            headers = {"Authorization": f"Bearer {api_key}"}  # Adjust header format as needed
            response = requests.get(f"{api_base_url}{test_endpoint}", headers=headers, timeout=30)
            response.raise_for_status()
            
            logging.info(f"API key validated (status: {response.status_code})")
            
        elif auth_type == "bearer":
            # Bearer token authentication
            bearer_token = kv_client.get_secret(os.environ["API_KEY_SECRET_NAME"]).value
            test_endpoint = os.environ.get("API_TEST_ENDPOINT", "/")
            
            headers = {"Authorization": f"Bearer {bearer_token}"}
            response = requests.get(f"{api_base_url}{test_endpoint}", headers=headers, timeout=30)
            response.raise_for_status()
            
            logging.info(f"Bearer token validated (status: {response.status_code})")
        
        logging.info("TEST 3: PASSED - API authentication works")
        
    except Exception as e:
        logging.error(f"TEST 3: FAILED - {str(e)}", exc_info=True)
        return
    
    logging.info("=" * 60)


# ============================================================================
# FUNCTION 4: Test API Data Fetch
# Purpose: Verify API returns actual data using authenticated requests
# Dependencies: Function 3 must pass
# Schedule: Disabled by default
# Enable: Change schedule to "*/10 * * * *" for testing
# ============================================================================
@app.timer_trigger(schedule="0 0 1 1 1 2099", arg_name="timer", run_on_startup=False, use_monitor=False)
def test_api_fetch(timer: func.TimerRequest) -> None:
    """Test that API returns data and we can parse it correctly."""
    logging.info("=" * 60)
    logging.info("TEST 4: API Data Fetch Test Started")
    
    try:
        # Read configuration
        key_vault_url = os.environ["KEY_VAULT_URL"]
        api_base_url = os.environ["API_BASE_URL"]
        data_endpoint = os.environ["API_DATA_ENDPOINT"]
        auth_type = os.environ.get("API_AUTH_TYPE", "apikey")
        query_type = os.environ.get("API_QUERY_TYPE", "rest")
        
        # Get credentials and authenticate
        credential = DefaultAzureCredential()
        kv_client = SecretClient(vault_url=key_vault_url, credential=credential)
        
        headers = {"Content-Type": "application/json"}
        
        # Build authentication header
        if auth_type == "oauth2":
            token_url = os.environ["API_TOKEN_URL"]
            client_id = kv_client.get_secret(os.environ["API_CLIENT_ID_SECRET_NAME"]).value
            client_secret = kv_client.get_secret(os.environ["API_CLIENT_SECRET_SECRET_NAME"]).value
            
            response = requests.post(token_url, json={"client_id": client_id, "client_secret": client_secret}, timeout=30)
            response.raise_for_status()
            token = response.json()["access_token"]
            headers["Authorization"] = f"Bearer {token}"
            
        else:  # apikey or bearer
            api_key = kv_client.get_secret(os.environ["API_KEY_SECRET_NAME"]).value
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Make API request
        full_url = f"{api_base_url}{data_endpoint}"
        
        if query_type == "graphql":
            # GraphQL query
            sample_query = os.environ.get("API_SAMPLE_QUERY", "{ items { id name } }")
            response = requests.post(full_url, json={"query": sample_query}, headers=headers, timeout=30)
        else:
            # REST query
            sample_query = os.environ.get("API_SAMPLE_QUERY", "?limit=5")
            response = requests.get(f"{full_url}{sample_query}", headers=headers, timeout=30)
        
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        response_path = os.environ.get("API_RESPONSE_PATH", "items")
        
        # Navigate to data array using dot notation
        records = data
        for key in response_path.split('.'):
            records = records.get(key, [])
        
        if not isinstance(records, list):
            records = [records]
        
        logging.info(f"Retrieved {len(records)} records from API")
        
        # Log first 3 records
        id_field = os.environ.get("API_ID_FIELD", "id")
        for i, record in enumerate(records[:3]):
            record_id = record.get(id_field, "unknown")
            logging.info(f"  Record {i+1}: ID={record_id}")
        
        logging.info("TEST 4: PASSED - API data fetch works")
        
    except Exception as e:
        logging.error(f"TEST 4: FAILED - {str(e)}", exc_info=True)
        return
    
    logging.info("=" * 60)


# ============================================================================
# FUNCTION 5: Test Table Storage
# Purpose: Verify function can write to and read from Azure Table Storage
# Dependencies: Function 1 must pass
# Schedule: Disabled by default
# Enable: Change schedule to "*/10 * * * *" for testing
# ============================================================================
@app.timer_trigger(schedule="0 0 1 1 1 2099", arg_name="timer", run_on_startup=False, use_monitor=False)
def test_table_storage(timer: func.TimerRequest) -> None:
    """Test that function can create table, write entity, and read it back."""
    logging.info("=" * 60)
    logging.info("TEST 5: Table Storage Test Started")
    
    try:
        # Read storage configuration
        storage_connection_string = os.environ["STORAGE_CONNECTION_STRING"]
        
        # Connect to Table Storage
        table_service = TableServiceClient.from_connection_string(storage_connection_string)
        table_client = table_service.get_table_client("TestTable")
        
        # Create table if it doesn't exist
        try:
            table_service.create_table("TestTable")
            logging.info("Created TestTable")
        except:
            logging.info("TestTable already exists")
        
        # Create test entity
        test_entity = {
            'PartitionKey': 'test',
            'RowKey': datetime.utcnow().isoformat(),
            'testMessage': 'Storage test successful',
            'testTimestamp': datetime.utcnow().isoformat()
        }
        
        # Write entity
        table_client.upsert_entity(test_entity)
        logging.info("Test entity written to storage")
        
        # Read entity back
        retrieved_entity = table_client.get_entity(
            partition_key=test_entity['PartitionKey'], 
            row_key=test_entity['RowKey']
        )
        logging.info(f"Test entity read from storage: {retrieved_entity['testMessage']}")
        
        logging.info("TEST 5: PASSED - Table Storage works")
        
    except Exception as e:
        logging.error(f"TEST 5: FAILED - {str(e)}", exc_info=True)
        return
    
    logging.info("=" * 60)