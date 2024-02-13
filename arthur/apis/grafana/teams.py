import aiohttp

from arthur.config import CONFIG

AUTH_HEADER = {"Authorization": f"Bearer {CONFIG.grafana_token.get_secret_value()}"}


async def list_teams(session: aiohttp.ClientSession) -> dict[str, str]:
    """List all Grafana teams."""
    endpoint = CONFIG.grafana_url + "/api/teams/search"
    async with session.get(endpoint, headers=AUTH_HEADER) as response:
        response.raise_for_status()
        teams = await response.json()
    return teams["teams"]


async def list_team_members(team_id: int, session: aiohttp.ClientSession) -> list[dict[str, str]]:
    """List all members within a team."""
    endpoint = CONFIG.grafana_url + f"/api/teams/{team_id}/members"
    async with session.get(endpoint, headers=AUTH_HEADER) as response:
        response.raise_for_status()
        return await response.json()


async def add_user_to_team(
    user_id: int,
    team_id: int,
    session: aiohttp.ClientSession,
) -> dict[str, str]:
    """Add a Grafana user to a team."""
    endpoint = CONFIG.grafana_url + f"/api/teams/{team_id}/members"
    payload = {"userId": user_id}
    async with session.post(endpoint, headers=AUTH_HEADER, json=payload) as response:
        response.raise_for_status()
        return await response.json()


async def remove_user_from_team(
    user_id: int,
    team_id: int,
    session: aiohttp.ClientSession,
) -> dict[str, str]:
    """AdRemove a Grafana user from a team."""
    endpoint = CONFIG.grafana_url + f"/api/teams/{team_id}/members/{user_id}"
    async with session.delete(endpoint, headers=AUTH_HEADER) as response:
        response.raise_for_status()
        return await response.json()


async def get_all_users(session: aiohttp.ClientSession) -> list[dict[str, str]]:
    """Get a grafana users."""
    endpoint = CONFIG.grafana_url + "/api/org/users/lookup"
    async with session.get(endpoint, headers=AUTH_HEADER) as response:
        response.raise_for_status()
        return await response.json()
