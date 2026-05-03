"""Utilities for interacting with the Keycloak REST API."""

import asyncio
from functools import cache

from keycloak import KeycloakAdmin, urls_patterns
from keycloak.exceptions import KeycloakGetError, raise_error_from_response

from arthur.config import CONFIG

MAX_KEYCLOAK_CONCURRENCY = 20


@cache
def create_client() -> KeycloakAdmin:
    """Create a new client for the Keycloak API."""
    return KeycloakAdmin(
        server_url=str(CONFIG.keycloak_address),
        username=CONFIG.keycloak_username,
        password=CONFIG.keycloak_password.get_secret_value(),
        realm_name=CONFIG.keycloak_user_realm,
        user_realm_name="master",
    )


async def force_password_reset(username: str, password: str) -> None:
    """Force a password reset for a user."""
    client = create_client()

    user_id = await client.a_get_user_id(username)

    if not user_id:
        msg = f"User {username} not found in Keycloak."
        raise ValueError(msg)

    await client.a_set_user_password(user_id, password, temporary=True)


async def get_user(user_id: str) -> dict:
    """Fetch a user from Keycloak using their user ID."""
    client = create_client()

    return await client.a_get_user(user_id)


async def get_discord_id(user_id: str) -> int | None:
    """Fetch a user's Discord ID from Keycloak attributes."""
    user = await get_user(user_id)
    discord_ids = user.get("attributes", {}).get("discordId")
    if not isinstance(discord_ids, list) or not discord_ids:
        return None

    try:
        return int(discord_ids[0])
    except TypeError, ValueError:
        return None


async def get_user_id(username: str) -> str | None:
    """Fetch a user's Keycloak ID using their username."""
    client = create_client()

    return await client.a_get_user_id(username)


async def get_user_github_id(username: str) -> str | None:
    """Fetch a users GitHub ID from Keycloak."""
    client = create_client()

    user = await client.a_get_user(username)
    github_id = None
    for ident in user["federatedIdentities"]:
        if ident["identityProvider"] == "github":
            github_id = ident["userId"]
            break

    if not github_id:
        return None

    return github_id


async def _fetch_user_github_identity(
    client: KeycloakAdmin, user: dict, semaphore: asyncio.Semaphore
) -> tuple[str, dict[str, str] | None]:
    """Fetch federated identities for a single user and return their GitHub identity if found."""
    url = urls_patterns.URL_ADMIN_USER_FEDERATED_IDENTITIES.format(
        **{"realm-name": client.connection.realm_name, "id": user["id"]}
    )
    async with semaphore, await client.connection.a_raw_get(url) as response:
        identities = raise_error_from_response(
            response,
            KeycloakGetError,
        )

    for ident in identities:
        if ident["identityProvider"] == "github":
            return user["username"], {
                "user_id": ident.get("userId", ""),
                "user_name": ident.get("userName", ""),
            }
    return user["username"], None


async def all_github_identities() -> dict[str, dict[str, str]]:
    """Fetch Keycloak usernames and their linked GitHub identity information."""
    client = create_client()
    users = await client.a_get_users()

    semaphore = asyncio.Semaphore(MAX_KEYCLOAK_CONCURRENCY)
    tasks = [_fetch_user_github_identity(client, user, semaphore) for user in users]

    results = await asyncio.gather(*tasks)

    return {username: identity for username, identity in results if identity}


async def all_github_ids() -> list[str]:
    """Fetch all GitHub IDs from Keycloak."""
    identities = await all_github_identities()
    return [ident["user_id"] for ident in identities.values() if ident.get("user_id")]
