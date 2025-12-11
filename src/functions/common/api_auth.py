"""
External API authentication module.
Handles OAuth2, API Key, and Bearer token authentication.
"""

import os
import logging
import requests
from typing import Dict
from .keyvault import get_api_credentials


def get_auth_headers(auth_type: str = None) -> Dict[str, str]:
    """
    Get authentication headers for external API requests.

    Args:
        auth_type: Override auth type (default: reads from API_AUTH_TYPE env var)

    Returns:
        Dict of HTTP headers with authentication

    Raises:
        ValueError: If auth_type is invalid or authentication fails
    """
    if auth_type is None:
        auth_type = os.environ.get("API_AUTH_TYPE", "apikey")

    headers = {"Content-Type": "application/json"}

    try:
        credentials = get_api_credentials(auth_type)

        if auth_type == "oauth2":
            token = _get_oauth2_token(credentials["client_id"], credentials["client_secret"])
            headers["Authorization"] = f"Bearer {token}"
            logging.info("✓ OAuth2 token acquired")

        elif auth_type == "apikey":
            api_key = credentials["api_key"]
            # Note: Adjust header format based on your API's requirements
            # Common formats: "Bearer {key}", "ApiKey {key}", "X-API-Key: {key}"
            headers["Authorization"] = f"Bearer {api_key}"
            logging.info("✓ API key authentication configured")

        elif auth_type == "bearer":
            bearer_token = credentials["api_key"]  # Reuses same secret name
            headers["Authorization"] = f"Bearer {bearer_token}"
            logging.info("✓ Bearer token authentication configured")

        return headers

    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        raise


def _get_oauth2_token(client_id: str, client_secret: str) -> str:
    """
    Acquire OAuth2 access token using client credentials flow.

    Args:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret

    Returns:
        Access token string

    Raises:
        requests.HTTPError: If token acquisition fails
        ValueError: If token not in response
    """
    token_url = os.environ.get("API_TOKEN_URL")

    if not token_url:
        raise ValueError("API_TOKEN_URL not configured for OAuth2 authentication")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"  # Standard OAuth2 flow
    }

    try:
        response = requests.post(
            token_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise ValueError(f"No access_token in response: {token_data.keys()}")

        logging.info(f"OAuth2 token acquired (length: {len(access_token)})")
        return access_token

    except requests.RequestException as e:
        logging.error(f"OAuth2 token request failed: {e}")
        raise


def test_api_authentication() -> bool:
    """
    Test that API authentication works by making a test request.

    Returns:
        True if authentication successful, False otherwise
    """
    try:
        api_base_url = os.environ.get("API_BASE_URL")
        test_endpoint = os.environ.get("API_TEST_ENDPOINT", "/")

        if not api_base_url:
            logging.error("API_BASE_URL not configured")
            return False

        headers = get_auth_headers()
        url = f"{api_base_url}{test_endpoint}"

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        logging.info(f"✓ API authentication test passed (status: {response.status_code})")
        return True

    except Exception as e:
        logging.error(f"✗ API authentication test failed: {e}")
        return False


def make_api_request(
    endpoint: str,
    method: str = "GET",
    query_params: str = "",
    json_payload: dict = None
) -> requests.Response:
    """
    Make an authenticated request to the external API.

    Args:
        endpoint: API endpoint path (e.g., "/v1/data")
        method: HTTP method ("GET" or "POST")
        query_params: Query string (e.g., "?limit=100")
        json_payload: JSON body for POST requests

    Returns:
        Response object

    Raises:
        requests.HTTPError: If request fails
    """
    api_base_url = os.environ.get("API_BASE_URL")

    if not api_base_url:
        raise ValueError("API_BASE_URL not configured")

    headers = get_auth_headers()
    url = f"{api_base_url}{endpoint}{query_params}"

    if method == "POST":
        response = requests.post(url, json=json_payload, headers=headers, timeout=60)
    else:
        response = requests.get(url, headers=headers, timeout=60)

    response.raise_for_status()
    return response
