"""APIs for interacting with TLS certificates through cert-manager.io CRDs."""

from typing import Any

from kubernetes_asyncio import client

from arthur.apis.kubernetes import get_api_client


async def list_certificates(namespace: str) -> dict[str, Any]:
    """List certificate objects created through cert-manager."""
    api = client.CustomObjectsApi(get_api_client())
    return await api.list_namespaced_custom_object(
        "cert-manager.io", "v1", namespace, "certificates"
    )
