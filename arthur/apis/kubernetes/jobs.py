"""APIs for interacting with Kubernetes Jobs & Cronjobs."""

from typing import Any

from kubernetes_asyncio import client
from kubernetes_asyncio.client.models import V1CronJob, V1CronJobList, V1Job

from arthur.apis.kubernetes import get_api_client


async def list_cronjobs(namespace: str | None = None) -> V1CronJobList:
    """Query the Kubernetes API for a list of cronjobss in the provided namespace."""
    api = client.BatchV1Api(get_api_client())
    if namespace:
        return await api.list_namespaced_cron_job(namespace)
    return await api.list_cron_job_for_all_namespaces()


async def get_cronjob(namespace: str, cronjob_name: str) -> V1CronJob:
    """Fetch a cronjob given the name and namespace."""
    api = client.BatchV1Api(get_api_client())
    return await api.read_namespaced_cron_job(cronjob_name, namespace)


async def create_job(namespace: str, job_name: str, cron_spec: dict[str, Any]) -> V1Job:
    """Create a job in the specified namespace with the given specification and name."""
    api = client.BatchV1Api(get_api_client())
    return await api.create_namespaced_job(
        namespace, V1Job(metadata={"name": job_name}, spec=cron_spec)
    )
