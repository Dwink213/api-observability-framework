"""
API Observability Framework - Production Functions
Three production functions for data collection, AI analysis, and reporting.
Enabled by default - run on schedule after validation passes.
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from openai import AzureOpenAI

app = func.FunctionApp()

# ============================================================================
# FUNCTION 6: Production Data Collector
# Purpose: Fetch all API data and store in Azure Table Storage
# Dependencies: All test functions (F1-F5) must pass first
# Schedule: Hourly by default (adjust as needed)
# ============================================================================
@app.timer_trigger(schedule="0 0 */1 * * *", arg_name="timer", run_on_startup=False, use_monitor=False)
def api_data_collector(timer: func.TimerRequest) -> None:
    """Collect data from target API and store in Azure Table Storage."""
    logging.info("=" * 60)
    logging.info("PRODUCTION: Data Collector Started")
    
    try:
        # Read configuration
        key_vault_url = os.environ["KEY_VAULT_URL"]
        api_base_url = os.environ["API_BASE_URL"]
        data_endpoint = os.environ["API_DATA_ENDPOINT"]
        storage_connection_string = os.environ["STORAGE_CONNECTION_STRING"]
        table_name = os.environ.get("STORAGE_TABLE_NAME", "ApiData")
        auth_type = os.environ.get("API_AUTH_TYPE", "apikey")
        query_type = os.environ.get("API_QUERY_TYPE", "rest")
        
        # Field mapping configuration
        id_field = os.environ.get("API_ID_FIELD", "id")
        timestamp_field = os.environ.get("API_TIMESTAMP_FIELD", "timestamp")
        field_mapping = json.loads(os.environ.get("FIELD_MAPPING", "{}"))
        
        # Get credentials from Key Vault
        credential = DefaultAzureCredential()
        kv_client = SecretClient(vault_url=key_vault_url, credential=credential)
        
        # Build authentication header
        headers = {"Content-Type": "application/json"}
        
        if auth_type == "oauth2":
            logging.info("Acquiring OAuth2 token...")
            token_url = os.environ["API_TOKEN_URL"]
            client_id = kv_client.get_secret(os.environ["API_CLIENT_ID_SECRET_NAME"]).value
            client_secret = kv_client.get_secret(os.environ["API_CLIENT_SECRET_SECRET_NAME"]).value
            
            response = requests.post(token_url, json={"client_id": client_id, "client_secret": client_secret}, timeout=30)
            response.raise_for_status()
            token = response.json()["access_token"]
            headers["Authorization"] = f"Bearer {token}"
        else:
            api_key = kv_client.get_secret(os.environ["API_KEY_SECRET_NAME"]).value
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Fetch data from API with pagination support
        logging.info("Fetching data from API...")
        all_records = []
        has_next_page = True
        cursor = None
        page_count = 0
        max_pages = int(os.environ.get("API_MAX_PAGES", "100"))
        
        full_url = f"{api_base_url}{data_endpoint}"
        
        while has_next_page and page_count < max_pages:
            page_count += 1
            
            if query_type == "graphql":
                # GraphQL pagination
                full_query = os.environ.get("API_FULL_QUERY", "{ items { id timestamp } }")
                if cursor:
                    full_query = full_query.replace("first:", f'first:, after: "{cursor}",')
                
                response = requests.post(full_url, json={"query": full_query}, headers=headers, timeout=60)
            else:
                # REST pagination
                page_size = os.environ.get("API_PAGE_SIZE", "100")
                query_params = f"?limit={page_size}"
                if cursor:
                    query_params += f"&cursor={cursor}"
                
                response = requests.get(f"{full_url}{query_params}", headers=headers, timeout=60)
            
            response.raise_for_status()
            data = response.json()
            
            # Extract records from response
            response_path = os.environ.get("API_RESPONSE_PATH", "items")
            records = data
            for key in response_path.split('.'):
                records = records.get(key, [])
            
            if not isinstance(records, list):
                records = [records]
            
            if not records or len(records) == 0:
                logging.info("No more records to fetch")
                break
            
            all_records.extend(records)
            logging.info(f"Fetched {len(records)} records. Total: {len(all_records)}")
            
            # Check pagination
            pagination_enabled = os.environ.get("API_PAGINATION_ENABLED", "false").lower() == "true"
            if not pagination_enabled:
                break
            
            # Get next cursor (adjust based on your API's pagination structure)
            cursor = data.get("nextCursor") or data.get("next")
            has_next_page = bool(cursor)
        
        # Store in Table Storage
        logging.info(f"Storing {len(all_records)} records in Table Storage...")
        table_service = TableServiceClient.from_connection_string(storage_connection_string)
        table_client = table_service.get_table_client(table_name)
        
        # Create table if needed
        try:
            table_service.create_table(table_name)
            logging.info(f"Created table {table_name}")
        except:
            pass
        
        # Write records
        new_count = 0
        update_count = 0
        
        for record in all_records:
            try:
                # Build entity with field mapping
                entity = {
                    'PartitionKey': os.environ.get("PARTITION_KEY_VALUE", "api_data"),
                    'RowKey': str(record.get(id_field, "unknown")),
                    'fetched_at': datetime.utcnow().isoformat() + 'Z'
                }
                
                # Map fields based on configuration
                if field_mapping:
                    for api_field, storage_field in field_mapping.items():
                        entity[storage_field] = str(record.get(api_field, ""))
                else:
                    # Store all fields if no mapping specified
                    for key, value in record.items():
                        entity[key] = str(value) if value is not None else ""
                
                # Check if entity exists (for tracking new vs updated)
                try:
                    table_client.get_entity(partition_key=entity['PartitionKey'], row_key=entity['RowKey'])
                    update_count += 1
                except ResourceNotFoundError:
                    new_count += 1
                
                # Upsert (create or update)
                table_client.upsert_entity(entity)
                
            except Exception as e:
                logging.error(f"Error storing record {record.get(id_field)}: {str(e)}")
        
        logging.info(f"Stored {new_count} new records, {update_count} updated")
        logging.info("PRODUCTION: Data collection completed successfully")
        
    except Exception as e:
        logging.error(f"PRODUCTION: Data collector failed - {str(e)}", exc_info=True)
        raise
    
    logging.info("=" * 60)


# ============================================================================
# FUNCTION 7: AI-Powered Data Analyzer
# Purpose: Analyze collected data using Azure OpenAI
# Dependencies: Function 6 must have run at least once (data exists)
# Schedule: Daily by default
# ============================================================================
@app.timer_trigger(schedule="0 0 9 * * *", arg_name="timer", run_on_startup=False, use_monitor=False)
def ai_data_analyzer(timer: func.TimerRequest) -> None:
    """Analyze collected data using AI to identify patterns and insights."""
    logging.info("=" * 60)
    logging.info("PRODUCTION: AI Analyzer Started")
    
    try:
        # Read configuration
        storage_connection_string = os.environ["STORAGE_CONNECTION_STRING"]
        table_name = os.environ.get("STORAGE_TABLE_NAME", "ApiData")
        lookback_days = int(os.environ.get("ANALYSIS_LOOKBACK_DAYS", "7"))
        
        # OpenAI configuration
        openai_endpoint = os.environ.get("OPENAI_ENDPOINT")
        openai_key = os.environ.get("OPENAI_API_KEY")
        openai_deployment = os.environ.get("OPENAI_DEPLOYMENT_NAME", "gpt-4")
        
        if not openai_endpoint or not openai_key:
            logging.warning("OpenAI not configured - skipping analysis")
            return
        
        # Connect to Table Storage
        table_service = TableServiceClient.from_connection_string(storage_connection_string)
        table_client = table_service.get_table_client(table_name)
        
        # Calculate cutoff date
        cutoff_date = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat() + 'Z'
        logging.info(f"Analyzing data from last {lookback_days} days...")
        
        # Query entities based on filter field
        filter_field = os.environ.get("ANALYSIS_FILTER_FIELD", "Status")
        filter_values = os.environ.get("ANALYSIS_FILTER_VALUES", "Error,Warning,Critical").split(',')
        
        # Collect records for analysis
        records_to_analyze = []
        total_records = 0
        
        try:
            entities = table_client.list_entities()
            for entity in entities:
                total_records += 1
                
                # Check if record matches filter criteria
                timestamp_value = entity.get(os.environ.get("API_TIMESTAMP_FIELD", "timestamp"), '')
                if timestamp_value >= cutoff_date:
                    field_value = entity.get(filter_field, '')
                    if any(fv.strip() in str(field_value) for fv in filter_values):
                        records_to_analyze.append(dict(entity))
        
        except Exception as e:
            logging.error(f"Error querying data: {str(e)}", exc_info=True)
            return
        
        logging.info(f"Total records: {total_records}")
        logging.info(f"Records matching criteria: {len(records_to_analyze)}")
        
        if len(records_to_analyze) == 0:
            logging.info("No records to analyze - all clear!")
            return
        
        # Prepare data for AI analysis (limit to 100 records for token efficiency)
        analysis_sample = records_to_analyze[:100]
        
        # Build AI prompt
        ai_prompt_template = os.environ.get("AI_PROMPT_TEMPLATE", """
Analyze the following data and provide:
1. Summary statistics
2. Key patterns identified
3. Top issues by frequency
4. Recommended actions

Data:
{data}
""")
        
        prompt = ai_prompt_template.replace("{data}", json.dumps(analysis_sample, indent=2))
        
        # Call Azure OpenAI
        logging.info("Sending data to OpenAI for analysis...")
        client = AzureOpenAI(
            azure_endpoint=openai_endpoint,
            api_key=openai_key,
            api_version="2024-02-15-preview"
        )
        
        response = client.chat.completions.create(
            model=openai_deployment,
            messages=[
                {"role": "system", "content": "You are a data analyst expert. Analyze the provided data and identify patterns, issues, and actionable insights."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2500
        )
        
        analysis = response.choices[0].message.content
        
        # Log analysis
        logging.info("\n" + "=" * 60)
        logging.info("AI ANALYSIS REPORT")
        logging.info("=" * 60)
        logging.info(analysis)
        logging.info("=" * 60)
        
        # Store analysis in table for dashboard
        try:
            analysis_entity = {
                'PartitionKey': 'AI_ANALYSIS',
                'RowKey': datetime.utcnow().isoformat(),
                'analysis': analysis,
                'records_analyzed': len(analysis_sample),
                'generated_at': datetime.utcnow().isoformat() + 'Z'
            }
            table_client.upsert_entity(analysis_entity)
            logging.info("Stored analysis in table")
        except Exception as e:
            logging.error(f"Failed to store analysis: {str(e)}")
        
        logging.info("PRODUCTION: Analysis completed")
        
    except Exception as e:
        logging.error(f"PRODUCTION: Analyzer failed - {str(e)}", exc_info=True)
        raise
    
    logging.info("=" * 60)


# ============================================================================
# FUNCTION 8: Dashboard Generator
# Purpose: Generate HTML dashboard with data and AI analysis
# Dependencies: Functions 6 and 7 must have run
# Schedule: Daily, shortly after analysis
# ============================================================================
@app.timer_trigger(schedule="0 30 9 * * *", arg_name="timer", run_on_startup=False, use_monitor=False)
def generate_dashboard(timer: func.TimerRequest) -> None:
    """Generate HTML dashboard showing data summary and AI analysis."""
    logging.info("=" * 60)
    logging.info("PRODUCTION: Dashboard Generator Started")
    
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
        
        # Read configuration
        storage_connection_string = os.environ["STORAGE_CONNECTION_STRING"]
        table_name = os.environ.get("STORAGE_TABLE_NAME", "ApiData")
        lookback_days = int(os.environ.get("ANALYSIS_LOOKBACK_DAYS", "7"))
        
        # Connect to Table Storage
        table_service = TableServiceClient.from_connection_string(storage_connection_string)
        table_client = table_service.get_table_client(table_name)
        
        cutoff_date = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat() + 'Z'
        
        # Collect summary statistics
        total_records = 0
        error_records = 0
        timestamp_field = os.environ.get("API_TIMESTAMP_FIELD", "timestamp")
        
        entities = table_client.list_entities()
        for entity in entities:
            if entity.get(timestamp_field, '') >= cutoff_date:
                total_records += 1
                if 'error' in str(entity).lower() or 'fail' in str(entity).lower():
                    error_records += 1
        
        success_rate = round((total_records - error_records) / total_records * 100, 1) if total_records > 0 else 0
        
        # Get latest AI analysis
        ai_analysis = "No analysis available yet."
        try:
            # Get most recent analysis
            analysis_entities = table_client.query_entities("PartitionKey eq 'AI_ANALYSIS'")
            latest = None
            for entity in analysis_entities:
                if latest is None or entity.get('generated_at', '') > latest.get('generated_at', ''):
                    latest = entity
            if latest:
                ai_analysis = latest.get('analysis', ai_analysis)
        except:
            pass
        
        # Generate HTML dashboard
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Observability Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 40px;
        }}
        h1 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}
        .last-updated {{
            color: #666;
            margin-bottom: 30px;
            font-size: 0.9em;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 3em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .stat-label {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .analysis-box {{
            background: #f8f9fa;
            padding: 25px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            white-space: pre-wrap;
            font-family: 'Consolas', monospace;
            line-height: 1.6;
        }}
        footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 API Observability Dashboard</h1>
        <div class="last-updated">Last Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Period: Last {lookback_days} Days</div>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{total_records:,}</div>
                <div class="stat-label">Total Records</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{error_records:,}</div>
                <div class="stat-label">Issues Detected</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{success_rate}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🤖 AI-Powered Analysis</h2>
            <div class="analysis-box">{ai_analysis}</div>
        </div>
        
        <footer>
            Powered by Azure Functions + Azure OpenAI | Updates Automatically
        </footer>
    </div>
</body>
</html>"""
        
        # Upload to Blob Storage ($web container for static website hosting)
        blob_service = BlobServiceClient.from_connection_string(storage_connection_string)
        container_name = "$web"
        
        try:
            blob_service.create_container(container_name, public_access='blob')
            logging.info(f"Created {container_name} container")
        except:
            pass
        
        blob_client = blob_service.get_blob_client(container=container_name, blob="index.html")
        blob_client.upload_blob(
            html_content, 
            overwrite=True, 
            content_settings=ContentSettings(content_type='text/html')
        )
        
        logging.info(f"Dashboard uploaded successfully")
        logging.info("PRODUCTION: Dashboard generation completed")
        
    except Exception as e:
        logging.error(f"PRODUCTION: Dashboard generation failed - {str(e)}", exc_info=True)
        raise
    
    logging.info("=" * 60)