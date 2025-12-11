"""
Storage authentication and client management.
Supports both managed identity (production) and connection strings (local dev).
"""

import os
import logging
from typing import Optional
from azure.data.tables import TableServiceClient, TableClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ClientAuthenticationError


def get_table_service_client() -> TableServiceClient:
    """
    Get Table Storage service client using best available authentication.

    Priority:
    1. Managed Identity (production, most secure)
    2. Connection String (local dev, fallback)

    Returns:
        TableServiceClient: Authenticated client

    Raises:
        ValueError: If no valid authentication method is configured
    """

    # Try Managed Identity (production)
    storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")

    if storage_account_name:
        try:
            credential = DefaultAzureCredential()
            endpoint = f"https://{storage_account_name}.table.core.windows.net"

            # Test the credential works
            client = TableServiceClient(endpoint=endpoint, credential=credential)

            logging.info(f"✓ Using Managed Identity for storage: {storage_account_name}")
            return client

        except ClientAuthenticationError as e:
            logging.warning(f"Managed Identity auth failed: {e}")
            logging.warning("Falling back to connection string...")
        except Exception as e:
            logging.warning(f"Managed Identity setup failed: {e}")
            logging.warning("Falling back to connection string...")

    # Fall back to Connection String (local dev)
    connection_string = os.environ.get("STORAGE_CONNECTION_STRING")

    if not connection_string:
        raise ValueError(
            "No storage authentication configured. Set either:\n"
            "  - STORAGE_ACCOUNT_NAME (for managed identity), OR\n"
            "  - STORAGE_CONNECTION_STRING (for connection string)"
        )

    logging.info("✓ Using connection string for storage")
    return TableServiceClient.from_connection_string(connection_string)


def get_table_client(table_name: str, create_if_not_exists: bool = False) -> TableClient:
    """
    Get authenticated Table Storage client for a specific table.

    Args:
        table_name: Name of the table
        create_if_not_exists: Create table if it doesn't exist (default: False)

    Returns:
        TableClient: Authenticated client for the specified table
    """
    service_client = get_table_service_client()
    table_client = service_client.get_table_client(table_name)

    if create_if_not_exists:
        try:
            service_client.create_table(table_name)
            logging.info(f"Created table: {table_name}")
        except Exception as e:
            # Table likely already exists
            if "already exists" not in str(e).lower():
                logging.warning(f"Table creation note: {e}")

    return table_client


def get_blob_service_client():
    """
    Get Blob Storage service client using best available authentication.
    Used for dashboard generation (Function 8).

    Returns:
        BlobServiceClient: Authenticated client
    """
    from azure.storage.blob import BlobServiceClient

    # Try Managed Identity
    storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")

    if storage_account_name:
        try:
            credential = DefaultAzureCredential()
            endpoint = f"https://{storage_account_name}.blob.core.windows.net"
            client = BlobServiceClient(endpoint=endpoint, credential=credential)

            logging.info(f"✓ Using Managed Identity for blob storage: {storage_account_name}")
            return client

        except Exception as e:
            logging.warning(f"Managed Identity failed for blobs: {e}")

    # Fall back to Connection String
    connection_string = os.environ.get("STORAGE_CONNECTION_STRING")

    if not connection_string:
        raise ValueError("No storage authentication configured for blobs")

    logging.info("✓ Using connection string for blob storage")
    return BlobServiceClient.from_connection_string(connection_string)
