"""Shared Kubernetes API client."""

from functools import cache

from kubernetes_asyncio.client.api_client import ApiClient


@cache
def get_api_client() -> ApiClient:
    """Return the shared ApiClient, creating it on first call."""
    return ApiClient()
