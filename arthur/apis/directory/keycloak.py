"""Utilities for interacting with the Keycloak REST API."""

from keycloak import KeycloakAdmin

from arthur.config import CONFIG


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
