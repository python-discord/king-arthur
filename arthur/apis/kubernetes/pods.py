"""APIs for working with Kubernetes pods."""

from kubernetes_asyncio import client
from kubernetes_asyncio.client.api_client import ApiClient
from kubernetes_asyncio.client.models import V1PodList


async def list_pods(namespace: str) -> V1PodList:
    """Query the Kubernetes API for a list of pods in the provided namespace."""
    async with ApiClient() as api_client:
        api = client.CoreV1Api(api_client)
        return await api.list_namespaced_pod(namespace=namespace)
