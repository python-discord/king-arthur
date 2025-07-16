import aiohttp

from arthur.apis.github import GitHubError, HEADERS, HTTP_403, HTTP_404
from arthur.config import CONFIG


async def remove_org_member(username: str) -> None:
    """Remove a user from the GitHub organisation."""
    async with aiohttp.ClientSession() as session:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/members/{username}"

        async with session.delete(endpoint, headers=HEADERS) as resp:
            try:
                resp.raise_for_status()
                return await resp.json()
            except aiohttp.ClientResponseError as e:
                if e.status == HTTP_404:
                    msg = f"Team or user not found in the org: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTP_403:
                    msg = f"Forbidden: {e.message}"
                    raise GitHubError(msg)

                msg = f"Unexpected error: {e.message}"
                raise GitHubError(msg)
