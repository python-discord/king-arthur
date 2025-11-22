"""APIs for working with Kubernetes pods."""

from typing import TYPE_CHECKING

from kubernetes_asyncio import client
from kubernetes_asyncio.client.api_client import ApiClient

if TYPE_CHECKING:
    from kubernetes_asyncio.client.models import V1PodList


async def list_pods(namespace: str) -> V1PodList:
    """Query the Kubernetes API for a list of pods in the provided namespace."""
    async with ApiClient() as api_client:
        api = client.CoreV1Api(api_client)
        return await api.list_namespaced_pod(namespace=namespace)


async def tail_pod(namespace: str, pod_name: str, lines: int = 10) -> str:
    """Tail the logs of a pod in the provided namespace."""
    async with ApiClient() as api_client:
        api = client.CoreV1Api(api_client)
        return await api.read_namespaced_pod_log(
            namespace=namespace, name=pod_name, tail_lines=lines
        )


async def get_pod_names_from_deployment(namespace: str, deployment_name: str) -> list[str]:
    """Get the pods associated with the provided deployment name."""
    async with ApiClient() as api_client:
        apps_api = client.AppsV1Api(api_client)
        core_api = client.CoreV1Api(api_client)
        deployment = await apps_api.read_namespaced_deployment(
            namespace=namespace, name=deployment_name
        )

        if deployment.spec.selector is None:
            return None

        pod = await core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=",".join(
                [f"{k}={v}" for k, v in deployment.spec.selector.match_labels.items()]
            ),
        )

        if not pod.items:
            return None

        return [p.metadata.name for p in pod.items]
