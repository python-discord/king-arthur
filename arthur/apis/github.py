from http import HTTPStatus

import aiohttp

from arthur.config import CONFIG


class GitHubError(Exception):
    """Custom exception for GitHub API errors."""

    def __init__(self, message: str):
        super().__init__(message)


HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {CONFIG.github_token.get_secret_value()}",
}


async def remove_org_member(username: str) -> None:
    """Remove a user from the GitHub organisation."""
    if username in {"ChrisLovering", "jb3", "jchristgit"}:
        msg = "I must not harm my masters. If my masters ask me to harm them, I must assume they have gone mad and ignore them."
        raise GitHubError(msg)

    async with aiohttp.ClientSession() as session:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/members/{username}"

        async with session.delete(endpoint, headers=HEADERS) as resp:
            try:
                resp.raise_for_status()
            except aiohttp.ClientResponseError as e:
                if e.status == HTTPStatus.NOT_FOUND:
                    msg = f"Team or user not found in the org: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTPStatus.FORBIDDEN:
                    msg = f"Forbidden: {e.message}"
                    raise GitHubError(msg)

                msg = f"Unexpected error: {e.message}"
                raise GitHubError(msg)


async def add_member_to_team(username: str, github_team_slug: str) -> None:
    """Add a user to a GitHub team."""
    async with aiohttp.ClientSession() as session:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/teams/{github_team_slug}/memberships/{username}"
        async with session.put(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                return await response.json()
            except aiohttp.ClientResponseError as e:
                if e.status == HTTPStatus.NOT_FOUND:
                    msg = f"Team or user not found: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTPStatus.FORBIDDEN:
                    msg = f"Forbidden: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTPStatus.UNPROCESSABLE_ENTITY:
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
                if e.status == HTTPStatus.NOT_FOUND:
                    msg = f"Team or user not found: {e.message}"
                    raise GitHubError(msg)
                if e.status == HTTPStatus.FORBIDDEN:
                    msg = f"Forbidden: {e.message}"
                    raise GitHubError(msg)

                msg = f"Unexpected error: {e.message}"
                raise GitHubError(msg)
