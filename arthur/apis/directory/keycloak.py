"""Utilities for interacting with the Keycloak REST API."""

from functools import cache

from keycloak import KeycloakAdmin

from arthur.config import CONFIG


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


def force_password_reset(username: str, password: str) -> None:
    """Force a password reset for a user."""
    client = create_client()

    user_id = client.get_user_id(username)

    if not user_id:
        msg = f"User {username} not found in Keycloak."
        raise ValueError(msg)

    client.set_user_password(user_id, password, temporary=True)


def get_user_github_id(username: str) -> str | None:
    """Fetch a users GitHub ID from Keycloak."""
    client = create_client()

    user = client.get_user(username)
    github_id = None
    for ident in user["federatedIdentities"]:
        if ident["identityProvider"] == "github":
            github_id = ident["userId"]
            break

    if not github_id:
        return None

    return github_id

def all_github_ids() -> list[str]:
    """Fetch all GitHub IDs from Keycloak."""
    client = create_client()

    users = client.get_users({
        "enabled": True,
        "search": "*"
    })

    github_ids = []
    for user in users:
        for ident in user["federatedIdentities"]:
            if ident["identityProvider"] == "github":
                github_ids.append(ident["userId"])
                break

    return github_ids
