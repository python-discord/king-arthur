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


async def remove_org_member(username: str, session: aiohttp.ClientSession) -> None:
    """Remove a user from the GitHub organisation."""
    if username.lower() in {"chrislovering", "jb3", "jchristgit"}:
        msg = "I must not harm my masters. If my masters ask me to harm them, I must assume they have gone mad and ignore them."
        raise GitHubError(msg)

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


async def add_org_member(username: str, session: aiohttp.ClientSession) -> None:
    """Add a user to the GitHub organisation."""
    endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/memberships/{username}"
    async with session.put(endpoint, headers=HEADERS, json={"role": "member"}) as response:
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            if e.status == HTTPStatus.NOT_FOUND:
                msg = f"User not found: {e.message}"
                raise GitHubError(msg)
            if e.status == HTTPStatus.FORBIDDEN:
                msg = f"Forbidden: {e.message}"
                raise GitHubError(msg)

            msg = f"Unexpected error: {e.message}"
            raise GitHubError(msg)


async def get_username_for_user_id(user_id: str, session: aiohttp.ClientSession) -> str | None:
    """Resolve a GitHub login from an account ID."""
    endpoint = f"https://api.github.com/user/{user_id}"
    async with session.get(endpoint, headers=HEADERS) as response:
        try:
            response.raise_for_status()
            data = await response.json()
        except aiohttp.ClientResponseError as e:
            if e.status == HTTPStatus.NOT_FOUND:
                return None

            msg = f"Failed to resolve GitHub user ID {user_id}: {e.message}"
            raise GitHubError(msg)

    return data.get("login")


async def list_organisation_member_identities(session: aiohttp.ClientSession) -> dict[str, str]:
    """List all organisation members as a mapping of account ID to login."""
    members = {}
    page = 1
    per_page = 100

    while True:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/members?per_page={per_page}&page={page}"
        async with session.get(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                data = await response.json()
                members.update(
                    {
                        str(member["id"]): member["login"]
                        for member in data
                        if member.get("id") and member.get("login")
                    }
                )
                if len(data) < per_page:
                    break
                page += 1
            except aiohttp.ClientResponseError as e:
                msg = f"Failed to list organisation member identities: {e.message}"
                raise GitHubError(msg)

    return members


async def list_pending_org_invitations(session: aiohttp.ClientSession) -> set[str]:
    """List GitHub logins with pending organisation invitations."""
    pending = set()
    page = 1
    per_page = 100

    while True:
        endpoint = (
            f"https://api.github.com/orgs/{CONFIG.github_org}/invitations"
            f"?per_page={per_page}&page={page}"
        )
        async with session.get(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                data = await response.json()
                for invitation in data:
                    login = invitation.get("login") or invitation.get("invitee", {}).get("login")
                    if login:
                        pending.add(login)

                if len(data) < per_page:
                    break
                page += 1
            except aiohttp.ClientResponseError as e:
                msg = f"Failed to list pending organisation invitations: {e.message}"
                raise GitHubError(msg)

    return pending


async def list_failed_org_invitations(session: aiohttp.ClientSession) -> set[str]:
    """List GitHub logins with failed organisation invitations."""
    failed = set()
    page = 1
    per_page = 100

    while True:
        endpoint = (
            f"https://api.github.com/orgs/{CONFIG.github_org}/failed_invitations"
            f"?per_page={per_page}&page={page}"
        )
        async with session.get(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                data = await response.json()
                for invitation in data:
                    login = invitation.get("login") or invitation.get("invitee", {}).get("login")
                    if login:
                        failed.add(login)

                if len(data) < per_page:
                    break
                page += 1
            except aiohttp.ClientResponseError as e:
                if e.status == HTTPStatus.NOT_FOUND:
                    # Some org/API versions may not expose failed invitations.
                    return failed

                msg = f"Failed to list failed organisation invitations: {e.message}"
                raise GitHubError(msg)

    return failed


def _extract_invitation_id(invitation: dict) -> int | None:
    """Extract a numeric invitation ID from a GitHub invitation payload."""
    raw_id = invitation.get("id")
    if isinstance(raw_id, int):
        return raw_id
    if isinstance(raw_id, str) and raw_id.isdigit():
        return int(raw_id)
    return None


async def _find_failed_org_invitation_id(
    username: str,
    session: aiohttp.ClientSession,
) -> int | None:
    """Find failed org invitation ID for a GitHub login."""
    page = 1
    per_page = 100

    while True:
        endpoint = (
            f"https://api.github.com/orgs/{CONFIG.github_org}/failed_invitations"
            f"?per_page={per_page}&page={page}"
        )
        async with session.get(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                data = await response.json()
            except aiohttp.ClientResponseError as e:
                if e.status == HTTPStatus.NOT_FOUND:
                    # Some org/API versions may not expose failed invitations.
                    return None

                msg = f"Failed to list failed organisation invitations: {e.message}"
                raise GitHubError(msg)

        for invitation in data:
            login = invitation.get("login") or invitation.get("invitee", {}).get("login")
            if login and login.casefold() == username.casefold():
                return _extract_invitation_id(invitation)

        if len(data) < per_page:
            return None

        page += 1


async def remove_failed_org_invitation(username: str, session: aiohttp.ClientSession) -> None:
    """Remove a failed organisation invitation for a GitHub login."""
    invitation_id = await _find_failed_org_invitation_id(username, session)
    if invitation_id is None:
        # Missing failed invitation record is safe to ignore.
        return

    endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/invitations/{invitation_id}"
    async with session.delete(endpoint, headers=HEADERS) as response:
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            if e.status == HTTPStatus.NOT_FOUND:
                # Invitation already removed.
                return
            if e.status == HTTPStatus.FORBIDDEN:
                msg = f"Forbidden: {e.message}"
                raise GitHubError(msg)

            msg = (
                "Failed to remove failed organisation invitation for "
                f"{username} (invitation_id={invitation_id}): {e.message}"
            )
            raise GitHubError(msg)


async def add_member_to_team(
    username: str, github_team_slug: str, session: aiohttp.ClientSession
) -> None:
    """Add a user to a GitHub team."""
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


async def list_team_members(github_team_slug: str, session: aiohttp.ClientSession) -> list[str]:
    """List all members of a GitHub team, and handle pagination."""
    members = []
    page = 1
    per_page = 100

    while True:
        endpoint = (
            f"https://api.github.com/orgs/{CONFIG.github_org}/teams/{github_team_slug}"
            f"/members?per_page={per_page}&page={page}"
        )
        async with session.get(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                data = await response.json()
                members.extend([member["login"] for member in data])
                if len(data) < per_page:
                    break
                page += 1
            except aiohttp.ClientResponseError as e:
                msg = f"Failed to list team members for {github_team_slug}: {e.message}"
                raise GitHubError(msg)

    return members


async def remove_member_from_team(
    username: str, github_team_slug: str, session: aiohttp.ClientSession
) -> None:
    """Remove a user from a GitHub team."""
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


async def list_organisation_members(session: aiohttp.ClientSession) -> list[str]:
    """List all members of the GitHub organisation, and handle pagination."""
    members = []
    page = 1
    per_page = 100

    while True:
        endpoint = f"https://api.github.com/orgs/{CONFIG.github_org}/members?per_page={per_page}&page={page}"
        async with session.get(endpoint, headers=HEADERS) as response:
            try:
                response.raise_for_status()
                data = await response.json()
                members.extend([member["login"] for member in data])
                if len(data) < per_page:
                    break
                page += 1
            except aiohttp.ClientResponseError as e:
                msg = f"Failed to list organisation members: {e.message}"
                raise GitHubError(msg)

    return members
