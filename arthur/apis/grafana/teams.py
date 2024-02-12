import aiohttp

from arthur import logger
from arthur.config import CONFIG

AUTH_HEADER = {"Authorization": f"Bearer {CONFIG.grafana_token.get_secret_value()}"}


async def list_teams(session: aiohttp.ClientSession) -> dict[str, str]:
    """List all Grafana teams."""
    endpoint = CONFIG.grafana_url + "/api/teams/search"
    async with session.get(endpoint, headers=AUTH_HEADER) as response:
        teams = await response.json()
        if not response.ok:
            logger.error(teams)
    return teams["teams"]


async def list_team_members(team_id: int, session: aiohttp.ClientSession) -> list[dict[str, str]]:
    """List all members within a team."""
    endpoint = CONFIG.grafana_url + f"/api/teams/{team_id}/members"
    async with session.get(endpoint, headers=AUTH_HEADER) as response:
        team_members = await response.json()
        if not response.ok:
            logger.error(team_members)
        return team_members


async def add_user_to_team(
    user_id: int,
    team_id: int,
    session: aiohttp.ClientSession,
) -> dict[str, str]:
    """Add a Grafana user to a team."""
    endpoint = CONFIG.grafana_url + f"/api/teams/{team_id}/members"
    payload = {"userId": user_id}
    async with session.post(endpoint, headers=AUTH_HEADER, json=payload) as response:
        add_resp = await response.json()
        if not response.ok:
            logger.error(add_resp)
        return add_resp


async def get_all_users(session: aiohttp.ClientSession) -> list[dict[str, str]]:
    """Get a grafana users."""
    endpoint = CONFIG.grafana_url + "/api/org/users/lookup"
    async with session.get(endpoint, headers=AUTH_HEADER) as response:
        users = await response.json()
        if not response.ok:
            logger.error(users)
        return users
