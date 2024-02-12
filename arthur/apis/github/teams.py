import aiohttp

from arthur.config import CONFIG

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {CONFIG.github_token.get_secret_value()}",
}
BASE_URL = "https://api.github.com"


class GithubTeamNotFoundError(aiohttp.ClientResponseError):
    """Raised when a github team could not be found."""


async def list_team_members(team_slug: str, session: aiohttp.ClientSession) -> list[dict[str, str]]:
    """List all Github teams."""
    endpoint = BASE_URL + f"/orgs/{CONFIG.github_org}/teams/{team_slug}/members"
    async with session.get(endpoint, headers=HEADERS) as response:
        response.raise_for_status()
        return await response.json()
