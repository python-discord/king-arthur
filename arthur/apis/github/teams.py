import aiohttp

from arthur.config import CONFIG

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {CONFIG.github_token.get_secret_value()}",
}

HTTP_404 = 404
HTTP_403 = 403
HTTP_422 = 422


class GitHubError(Exception):
    """Custom exception for GitHub API errors."""

    def __init__(self, message: str):
        super().__init__(message)


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
