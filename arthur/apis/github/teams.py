import aiohttp

from arthur.apis.github.common import GitHubError, HEADERS, HTTP_403, HTTP_404, HTTP_422
from arthur.config import CONFIG


async def add_member_to_team(username: str, github_team_slug: str) -> None:
    """Add a user to a GitHub team."""
    async with aiohttp.ClientSession() as session:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/teams/{github_team_slug}/memberships/{username}"
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


async def remove_member_from_team(username: str, github_team_slug: str) -> None:
    """Remove a user from a GitHub team."""
    async with aiohttp.ClientSession() as session:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/teams/{github_team_slug}/memberships/{username}"
        async with session.delete(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as e:
                if e.status == HTTP_404:
                    msg = f"Team or user not found: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTP_403:
                    msg = f"Forbidden: {e.message}"
                    raise GitHubError(msg)

                msg = f"Unexpected error: {e.message}"
                raise GitHubError(msg)
