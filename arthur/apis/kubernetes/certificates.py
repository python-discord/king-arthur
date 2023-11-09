"""APIs for interacting with TLS certificates through cert-manager.io CRDs."""

from typing import Any

from kubernetes_asyncio import client
from kubernetes_asyncio.client.api_client import ApiClient


async def list_certificates(namespace: str) -> dict[str, Any]:
    """List certificate objects created through cert-manager."""
    async with ApiClient() as api:
        api = client.CustomObjectsApi(api)
        return await api.list_namespaced_custom_object(
            "cert-manager.io", "v1", namespace, "certificates"
        )
