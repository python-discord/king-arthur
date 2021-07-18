"""APIs for interacting with Kubernetes nodes."""
from kubernetes_asyncio import client
from kubernetes_asyncio.client.api_client import ApiClient
from kubernetes_asyncio.client.models import V1NodeList


async def list_nodes() -> V1NodeList:
    """List Kubernetes nodes."""
    async with ApiClient() as api:
        api = client.CoreV1Api(api)
        return await api.list_node()


async def _change_cordon(node: str, cordon: bool) -> None:
    async with ApiClient() as api:
        api = client.CoreV1Api(api)
        await api.patch_node(
            node,
            body={"spec": {"unschedulable": cordon}},
        )


async def cordon_node(node: str) -> None:
    """Cordon a Kubernetes node."""
    await _change_cordon(node, True)


async def uncordon_node(node: str) -> None:
    """Uncordon a Kubernetes node."""
    await _change_cordon(node, False)
