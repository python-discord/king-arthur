import aiohttp

from arthur.config import CONFIG
from arthur.log import logger

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {CONFIG.github_token.get_secret_value()}",
}
BASE_URL = "https://api.github.com"
MEMBERS_PER_PAGE = 100


class GithubTeamNotFoundError(aiohttp.ClientResponseError):
    """Raised when a github team could not be found."""


async def list_team_members(team_slug: str, session: aiohttp.ClientSession) -> list[dict[str, str]]:
    """List all Github teams."""
    endpoint = f"{BASE_URL}/orgs/{CONFIG.github_org}/teams/{team_slug}/members"
    params = {"per_page": MEMBERS_PER_PAGE}
    async with session.get(endpoint, headers=HEADERS, params=params) as response:
        response.raise_for_status()
        teams_resp = await response.json()
        if len(teams_resp) == MEMBERS_PER_PAGE:
            logger.warning(
                "Max number (%d) of members returned when fetching members of %s. Some members may have been missed.",
                MEMBERS_PER_PAGE,
                team_slug,
            )
        return teams_resp
