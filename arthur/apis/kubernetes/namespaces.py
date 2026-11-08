"""APIs for interacting with Kubernetes namespaces."""

from typing import TYPE_CHECKING

from kubernetes_asyncio import client

from arthur.apis.kubernetes import get_api_client

if TYPE_CHECKING:
    from kubernetes_asyncio.client.models import V1NamespaceList


async def list_namespaces() -> V1NamespaceList:
    """List Kubernetes namespaces."""
    api = client.CoreV1Api(get_api_client())
    return await api.list_namespace()
