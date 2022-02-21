"""APIs for interacting with Kubernetes Jobs & Cronjobs."""
from typing import Any, Optional

from kubernetes_asyncio import client
from kubernetes_asyncio.client.api_client import ApiClient
from kubernetes_asyncio.client.models import V1beta1CronJob, V1beta1CronJobList, V1Job


async def list_cronjobs(namespace: Optional[str] = None) -> V1beta1CronJobList:
    """Query the Kubernetes API for a list of cronjobss in the provided namespace."""
    async with ApiClient() as api:
        api = client.BatchV1beta1Api(api)
        if namespace:
            return await api.list_namespaced_cron_job(namespace)
        else:
            return await api.list_cron_job_for_all_namespaces()


async def get_cronjob(namespace: str, cronjob_name: str) -> V1beta1CronJob:
    """Fetch a cronjob given the name and namespace."""
    async with ApiClient() as api:
        api = client.BatchV1beta1Api(api)
        return await api.read_namespaced_cron_job(cronjob_name, namespace)


async def create_job(namespace: str, job_name: str, cron_spec: dict[str, Any]) -> V1Job:
    """Create a job in the specified namespace with the given specification and name."""
    async with ApiClient() as api:
        api = client.BatchV1Api(api)
        return await api.create_namespaced_job(
            namespace, V1Job(metadata={"name": job_name}, spec=cron_spec)
        )
