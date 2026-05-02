"""APIs for working with Kubernetes deployments."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from kubernetes_asyncio import client

from arthur.apis.kubernetes import get_api_client

if TYPE_CHECKING:
    from kubernetes_asyncio.client.models import V1DeploymentList


async def restart_deployment(deployment: str, namespace: str) -> None:
    """Patch a deployment with a custom annotation to trigger redeployment."""
    api = client.AppsV1Api(get_api_client())
    await api.patch_namespaced_deployment(
        name=deployment,
        namespace=namespace,
        body={
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "king-arthur.pydis.com/restartedAt": datetime.now(UTC).isoformat()
                        }
                    }
                }
            }
        },
        field_manager="King Arthur The Terrible",
    )


async def list_deployments(namespace: str) -> V1DeploymentList:
    """Query the Kubernetes API for a list of deployments in the provided namespace."""
    api = client.AppsV1Api(get_api_client())
    return await api.list_namespaced_deployment(namespace=namespace)
