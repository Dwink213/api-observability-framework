"""
Environment variable validation and configuration management.
Validates required configuration at startup to fail fast.
"""

import os
import logging
from typing import List, Dict, Optional


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


# Core required variables for all functions
CORE_REQUIRED = [
    "KEY_VAULT_URL",
]

# Required for API data collection (F4, F6)
API_REQUIRED = [
    "API_BASE_URL",
    "API_AUTH_TYPE",
    "API_DATA_ENDPOINT",
    "API_ID_FIELD",
]

# Required for storage operations (F5, F6, F7, F8)
STORAGE_REQUIRED = [
    # At least ONE of these must be set:
    # "STORAGE_ACCOUNT_NAME",  # For managed identity
    # "STORAGE_CONNECTION_STRING",  # For connection string
]

# Required based on API_AUTH_TYPE
AUTH_TYPE_REQUIREMENTS = {
    "oauth2": [
        "API_CLIENT_ID_SECRET_NAME",
        "API_CLIENT_SECRET_SECRET_NAME",
        "API_TOKEN_URL",
    ],
    "apikey": [
        "API_KEY_SECRET_NAME",
    ],
    "bearer": [
        "API_KEY_SECRET_NAME",
    ],
}


def validate_environment(function_name: str = "unknown") -> None:
    """
    Validate that required environment variables are set.

    Args:
        function_name: Name of function being validated (for logging)

    Raises:
        ConfigurationError: If required variables are missing
    """
    logging.info(f"Validating configuration for: {function_name}")

    errors = []

    # Check core requirements
    missing_core = _check_required_vars(CORE_REQUIRED)
    if missing_core:
        errors.append(f"Missing core config: {', '.join(missing_core)}")

    # Check storage authentication (at least one method required)
    has_managed_identity = os.environ.get("STORAGE_ACCOUNT_NAME")
    has_connection_string = os.environ.get("STORAGE_CONNECTION_STRING")

    if not has_managed_identity and not has_connection_string:
        errors.append(
            "Missing storage authentication. Set either:\n"
            "  - STORAGE_ACCOUNT_NAME (for managed identity), OR\n"
            "  - STORAGE_CONNECTION_STRING (for connection string)"
        )

    # Check API authentication type requirements
    auth_type = os.environ.get("API_AUTH_TYPE", "apikey")
    auth_requirements = AUTH_TYPE_REQUIREMENTS.get(auth_type, [])

    if auth_requirements:
        missing_auth = _check_required_vars(auth_requirements)
        if missing_auth:
            errors.append(
                f"Missing config for API_AUTH_TYPE='{auth_type}': {', '.join(missing_auth)}"
            )

    if errors:
        error_msg = f"\n❌ Configuration errors in {function_name}:\n" + "\n".join(f"  • {e}" for e in errors)
        logging.error(error_msg)
        raise ConfigurationError(error_msg)

    logging.info(f"✓ Configuration valid for: {function_name}")


def validate_api_collection_config() -> None:
    """
    Validate configuration specific to API data collection (Functions 4 & 6).

    Raises:
        ConfigurationError: If required variables are missing
    """
    missing = _check_required_vars(API_REQUIRED)

    if missing:
        raise ConfigurationError(
            f"Missing API collection config: {', '.join(missing)}"
        )

    logging.info("✓ API collection configuration valid")


def validate_ai_analysis_config() -> Dict[str, Optional[str]]:
    """
    Validate configuration for AI analysis (Function 7).
    Returns config dict if valid, or dict with None values if not configured.

    Returns:
        Dict with OpenAI configuration or None values if not configured
    """
    endpoint = os.environ.get("OPENAI_ENDPOINT")

    if not endpoint:
        logging.info("OpenAI not configured (optional feature)")
        return {
            "endpoint": None,
            "api_key": None,
            "deployment": None,
            "temperature": 0.3,
            "max_tokens": 2500,
        }

    # OpenAI is configured, validate we have credentials
    api_key_secret = os.environ.get("OPENAI_API_KEY_SECRET_NAME")
    api_key_env = os.environ.get("OPENAI_API_KEY")

    if not api_key_secret and not api_key_env:
        raise ConfigurationError(
            "OPENAI_ENDPOINT set but no API key configured. Set either:\n"
            "  - OPENAI_API_KEY_SECRET_NAME (recommended), OR\n"
            "  - OPENAI_API_KEY (environment variable)"
        )

    return {
        "endpoint": endpoint,
        "api_key_secret_name": api_key_secret,
        "deployment": os.environ.get("OPENAI_DEPLOYMENT_NAME", "gpt-4"),
        "temperature": float(os.environ.get("AI_TEMPERATURE", "0.3")),
        "max_tokens": int(os.environ.get("AI_MAX_TOKENS", "2500")),
        "sample_size": int(os.environ.get("ANALYSIS_SAMPLE_SIZE", "100")),
    }


def get_storage_config() -> Dict[str, str]:
    """
    Get storage configuration (account name or connection string).

    Returns:
        Dict with storage configuration
    """
    return {
        "account_name": os.environ.get("STORAGE_ACCOUNT_NAME"),
        "connection_string": os.environ.get("STORAGE_CONNECTION_STRING"),
        "table_name": os.environ.get("STORAGE_TABLE_NAME", "ApiData"),
    }


def get_api_config() -> Dict[str, str]:
    """
    Get API configuration for data collection.

    Returns:
        Dict with API configuration
    """
    return {
        "base_url": os.environ.get("API_BASE_URL"),
        "auth_type": os.environ.get("API_AUTH_TYPE", "apikey"),
        "data_endpoint": os.environ.get("API_DATA_ENDPOINT"),
        "query_type": os.environ.get("API_QUERY_TYPE", "rest"),
        "id_field": os.environ.get("API_ID_FIELD", "id"),
        "timestamp_field": os.environ.get("API_TIMESTAMP_FIELD", "timestamp"),
        "response_path": os.environ.get("API_RESPONSE_PATH", "items"),
        "pagination_enabled": os.environ.get("API_PAGINATION_ENABLED", "false").lower() == "true",
        "page_size": os.environ.get("API_PAGE_SIZE", "100"),
        "max_pages": int(os.environ.get("API_MAX_PAGES", "100")),
    }


def _check_required_vars(var_list: List[str]) -> List[str]:
    """
    Check which required variables are missing.

    Args:
        var_list: List of environment variable names

    Returns:
        List of missing variable names
    """
    return [var for var in var_list if not os.environ.get(var)]


def log_configuration_summary() -> None:
    """
    Log a summary of the current configuration (without sensitive values).
    Useful for debugging.
    """
    logging.info("=" * 60)
    logging.info("CONFIGURATION SUMMARY")
    logging.info("=" * 60)

    # Storage
    storage_config = get_storage_config()
    if storage_config["account_name"]:
        logging.info(f"Storage: Managed Identity ({storage_config['account_name']})")
    elif storage_config["connection_string"]:
        logging.info("Storage: Connection String")
    else:
        logging.warning("Storage: NOT CONFIGURED")

    # API
    api_config = get_api_config()
    logging.info(f"API: {api_config['base_url']}")
    logging.info(f"Auth: {api_config['auth_type']}")
    logging.info(f"Query Type: {api_config['query_type']}")

    # AI (optional)
    ai_config = validate_ai_analysis_config()
    if ai_config["endpoint"]:
        logging.info(f"AI: Enabled ({ai_config['deployment']})")
    else:
        logging.info("AI: Not configured")

    logging.info("=" * 60)
