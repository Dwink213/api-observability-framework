"""
Refactored Function 6: Production Data Collector
Demonstrates modular approach with clean separation of concerns.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict
import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError

# Import modular components
from common import (
    validate_environment,
    validate_api_collection_config,
    get_table_client,
    get_auth_headers,
    get_api_config,
)


def api_data_collector(timer: func.TimerRequest) -> None:
    """
    Collect data from target API and store in Azure Table Storage.

    Uses modular components for authentication, API requests, and storage.
    Much cleaner and easier to test than the original monolithic version.
    """
    logging.info("=" * 60)
    logging.info("PRODUCTION: Data Collector Started")

    try:
        # Step 1: Validate configuration (fails fast if misconfigured)
        validate_environment("api_data_collector")
        validate_api_collection_config()

        # Step 2: Get configuration
        api_config = get_api_config()

        # Step 3: Fetch data from API
        records = fetch_all_records(api_config)
        logging.info(f"Fetched {len(records)} total records from API")

        # Step 4: Store in Table Storage
        new_count, update_count = store_records(records, api_config)

        logging.info(f"Stored {new_count} new records, {update_count} updated")
        logging.info("PRODUCTION: Data collection completed successfully")

    except Exception as e:
        logging.error(f"PRODUCTION: Data collector failed - {str(e)}", exc_info=True)
        raise

    logging.info("=" * 60)


def fetch_all_records(api_config: Dict) -> List[Dict]:
    """
    Fetch all records from API with pagination support.

    Args:
        api_config: API configuration dict

    Returns:
        List of all fetched records
    """
    import requests

    all_records = []
    has_next_page = True
    cursor = None
    page_count = 0

    headers = get_auth_headers(api_config["auth_type"])
    full_url = f"{api_config['base_url']}{api_config['data_endpoint']}"

    while has_next_page and page_count < api_config["max_pages"]:
        page_count += 1

        # Make API request based on query type
        if api_config["query_type"] == "graphql":
            records, cursor = fetch_graphql_page(full_url, headers, cursor, api_config)
        else:
            records, cursor = fetch_rest_page(full_url, headers, cursor, api_config)

        if not records:
            logging.info("No more records to fetch")
            break

        all_records.extend(records)
        logging.info(f"Page {page_count}: fetched {len(records)} records. Total: {len(all_records)}")

        # Check if pagination is enabled
        if not api_config["pagination_enabled"]:
            break

        has_next_page = bool(cursor)

    return all_records


def fetch_rest_page(url: str, headers: Dict, cursor: str, config: Dict) -> tuple:
    """
    Fetch one page of REST API results.

    Returns:
        Tuple of (records, next_cursor)
    """
    import requests

    query_params = f"?limit={config['page_size']}"
    if cursor:
        query_params += f"&cursor={cursor}"

    response = requests.get(f"{url}{query_params}", headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    # Extract records using response path
    records = extract_records_from_response(data, config["response_path"])

    # Extract next cursor (API-specific, may need customization)
    next_cursor = data.get("nextCursor") or data.get("next") or data.get("pagination", {}).get("cursor")

    return records, next_cursor


def fetch_graphql_page(url: str, headers: Dict, cursor: str, config: Dict) -> tuple:
    """
    Fetch one page of GraphQL results.

    Returns:
        Tuple of (records, next_cursor)
    """
    import requests

    # Build GraphQL query with cursor
    query = config.get("full_query", config.get("sample_query", ""))

    if cursor:
        # Fix: Proper cursor injection for GraphQL
        # Assumes query format: { items(first: 100) { ... } }
        query = inject_graphql_cursor(query, cursor, config['page_size'])

    response = requests.post(url, json={"query": query}, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    # Extract records
    records = extract_records_from_response(data, config["response_path"])

    # Extract pageInfo cursor (standard GraphQL pagination)
    page_info = data.get("data", {}).get("pageInfo", {})
    next_cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None

    return records, next_cursor


def inject_graphql_cursor(query: str, cursor: str, page_size: str) -> str:
    """
    Inject cursor into GraphQL query.

    Handles common GraphQL pagination patterns.
    """
    # If query has $cursor variable placeholder
    if "$cursor" in query:
        return query.replace("$cursor", cursor)

    # If query needs cursor added after first: N
    if "first:" in query and "after:" not in query:
        return query.replace("first:", f'first: {page_size}, after: "{cursor}",')

    # Otherwise return as-is (might need custom logic for specific APIs)
    logging.warning(f"Could not inject cursor into GraphQL query. Query: {query[:100]}...")
    return query


def extract_records_from_response(data: Dict, response_path: str) -> List[Dict]:
    """
    Extract records from API response using dot notation path.

    Args:
        data: API response JSON
        response_path: Dot notation path (e.g., "data.items")

    Returns:
        List of records
    """
    records = data

    for key in response_path.split('.'):
        if isinstance(records, dict):
            records = records.get(key, [])
        else:
            break

    if not isinstance(records, list):
        records = [records] if records else []

    return records


def store_records(records: List[Dict], api_config: Dict) -> tuple:
    """
    Store records in Azure Table Storage with upsert (prevents duplicates).

    Args:
        records: List of API records
        api_config: API configuration

    Returns:
        Tuple of (new_count, update_count)
    """
    import os

    table_name = os.environ.get("STORAGE_TABLE_NAME", "ApiData")
    table_client = get_table_client(table_name, create_if_not_exists=True)

    # Get field mapping
    field_mapping_str = os.environ.get("FIELD_MAPPING", "{}")
    field_mapping = json.loads(field_mapping_str) if field_mapping_str else {}

    partition_key = os.environ.get("PARTITION_KEY_VALUE", "api_data")
    id_field = api_config["id_field"]

    new_count = 0
    update_count = 0

    for record in records:
        try:
            entity = transform_record_to_entity(
                record,
                partition_key,
                id_field,
                field_mapping
            )

            # Check if exists (for counting)
            try:
                table_client.get_entity(
                    partition_key=entity['PartitionKey'],
                    row_key=entity['RowKey']
                )
                update_count += 1
            except ResourceNotFoundError:
                new_count += 1

            # Upsert (create or update)
            table_client.upsert_entity(entity)

        except Exception as e:
            logging.error(f"Error storing record {record.get(id_field)}: {str(e)}", exc_info=True)

    return new_count, update_count


def transform_record_to_entity(
    record: Dict,
    partition_key: str,
    id_field: str,
    field_mapping: Dict
) -> Dict:
    """
    Transform API record to Table Storage entity.

    Args:
        record: API record
        partition_key: Partition key value
        id_field: Name of ID field
        field_mapping: Field name mapping

    Returns:
        Table Storage entity dict
    """
    entity = {
        'PartitionKey': partition_key,
        'RowKey': str(record.get(id_field, "unknown")),
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }

    # Map fields based on configuration
    if field_mapping:
        for api_field, storage_field in field_mapping.items():
            value = record.get(api_field, "")
            entity[storage_field] = str(value) if value is not None else ""
    else:
        # Store all fields if no mapping specified
        for key, value in record.items():
            # Table Storage has limits on field names
            safe_key = key.replace('.', '_').replace('/', '_')
            entity[safe_key] = str(value) if value is not None else ""

    return entity
