import aiohttp

from arthur.apis.github import GitHubError, HEADERS, HTTP_403, HTTP_404, HTTP_422
from arthur.config import CONFIG


async def add_staff_member(username: str) -> None:
    """Add a user to the default GitHub team."""
    async with aiohttp.ClientSession() as session:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/teams/{CONFIG.github_team}/memberships/{username}"
        async with session.put(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                return await response.json()
            except aiohttp.ClientResponseError as e:
                if e.status == HTTP_404:
                    msg = f"Team or user not found: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTP_403:
                    msg = f"Forbidden: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTP_422:
                    msg = "Cannot add organisation as a team member"
                    raise GitHubError(msg)

                msg = f"Unexpected error: {e.message}"
                raise GitHubError(msg)
