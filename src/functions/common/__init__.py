"""
Common utilities for API Observability Framework.
Provides reusable authentication, configuration, and client management.
"""

from .storage import get_table_client, get_blob_service_client
from .keyvault import get_secret, get_api_credentials, get_openai_credentials
from .api_auth import get_auth_headers, make_api_request, test_api_authentication
from .config import (
    validate_environment,
    validate_api_collection_config,
    validate_ai_analysis_config,
    get_storage_config,
    get_api_config,
    log_configuration_summary,
    ConfigurationError
)

__all__ = [
    # Storage
    "get_table_client",
    "get_blob_service_client",
    # Key Vault
    "get_secret",
    "get_api_credentials",
    "get_openai_credentials",
    # API Auth
    "get_auth_headers",
    "make_api_request",
    "test_api_authentication",
    # Config
    "validate_environment",
    "validate_api_collection_config",
    "validate_ai_analysis_config",
    "get_storage_config",
    "get_api_config",
    "log_configuration_summary",
    "ConfigurationError",
]
