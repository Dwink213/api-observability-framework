"""
Key Vault authentication and secret management.
Uses Managed Identity for secure, credential-free access.
"""

import os
import logging
from typing import Optional
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError


_secret_client: Optional[SecretClient] = None


def get_keyvault_client() -> SecretClient:
    """
    Get authenticated Key Vault client (singleton pattern).

    Returns:
        SecretClient: Authenticated client

    Raises:
        ValueError: If KEY_VAULT_URL not configured
    """
    global _secret_client

    if _secret_client is not None:
        return _secret_client

    key_vault_url = os.environ.get("KEY_VAULT_URL")

    if not key_vault_url:
        raise ValueError(
            "KEY_VAULT_URL environment variable not set. "
            "Should be: https://your-keyvault.vault.azure.net"
        )

    try:
        credential = DefaultAzureCredential()
        _secret_client = SecretClient(vault_url=key_vault_url, credential=credential)

        logging.info(f"✓ Connected to Key Vault: {key_vault_url}")
        return _secret_client

    except Exception as e:
        logging.error(f"Failed to connect to Key Vault: {e}")
        raise


def get_secret(secret_name: str, required: bool = True) -> Optional[str]:
    """
    Retrieve a secret from Key Vault.

    Args:
        secret_name: Name of the secret in Key Vault
        required: Raise exception if secret not found (default: True)

    Returns:
        Secret value, or None if not found and not required

    Raises:
        ResourceNotFoundError: If secret not found and required=True
    """
    client = get_keyvault_client()

    try:
        secret = client.get_secret(secret_name)
        logging.info(f"✓ Retrieved secret: {secret_name} (length: {len(secret.value)})")
        return secret.value

    except ResourceNotFoundError:
        if required:
            logging.error(f"✗ Secret not found: {secret_name}")
            raise
        else:
            logging.warning(f"Optional secret not found: {secret_name}")
            return None


def get_api_credentials(auth_type: str) -> dict:
    """
    Retrieve API credentials from Key Vault based on authentication type.

    Args:
        auth_type: Authentication type ("oauth2", "apikey", or "bearer")

    Returns:
        Dict with credential keys depending on auth_type:
        - oauth2: {"client_id": str, "client_secret": str}
        - apikey: {"api_key": str}
        - bearer: {"bearer_token": str}

    Raises:
        ValueError: If auth_type is unsupported
    """
    if auth_type == "oauth2":
        client_id_name = os.environ.get("API_CLIENT_ID_SECRET_NAME", "oauth-client-id")
        client_secret_name = os.environ.get("API_CLIENT_SECRET_SECRET_NAME", "oauth-client-secret")

        return {
            "client_id": get_secret(client_id_name),
            "client_secret": get_secret(client_secret_name)
        }

    elif auth_type in ["apikey", "bearer"]:
        api_key_name = os.environ.get("API_KEY_SECRET_NAME", "api-key")

        return {
            "api_key": get_secret(api_key_name)
        }

    else:
        raise ValueError(f"Unsupported auth type: {auth_type}. Use 'oauth2', 'apikey', or 'bearer'")


def get_openai_credentials() -> dict:
    """
    Retrieve Azure OpenAI credentials from Key Vault.

    Returns:
        Dict with {"endpoint": str, "api_key": str, "deployment": str}
        Returns None values if OpenAI not configured (optional feature)
    """
    # Check if OpenAI is configured
    endpoint = os.environ.get("OPENAI_ENDPOINT")

    if not endpoint:
        logging.info("OpenAI not configured (optional feature)")
        return {"endpoint": None, "api_key": None, "deployment": None}

    # Try to get API key from Key Vault first, fall back to env var
    api_key_name = os.environ.get("OPENAI_API_KEY_SECRET_NAME")

    if api_key_name:
        api_key = get_secret(api_key_name, required=False)
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            logging.warning("⚠️  Using OPENAI_API_KEY from environment. Consider moving to Key Vault.")

    deployment = os.environ.get("OPENAI_DEPLOYMENT_NAME", "gpt-4")

    return {
        "endpoint": endpoint,
        "api_key": api_key,
        "deployment": deployment
    }
