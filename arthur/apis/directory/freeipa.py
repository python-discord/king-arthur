"""API utilities for modifying data via FreeIPA."""

from functools import cache
from secrets import token_urlsafe
from typing import Any

try:
    from bonsai import LDAPDN

    BONSAI_AVAILABLE = True
except ImportError:
    BONSAI_AVAILABLE = False

from python_freeipa import ClientMeta
from python_freeipa.exceptions import Unauthorized

from arthur.config import CONFIG
from arthur.constants import LDAP_ROLE_MAPPING

PW_LENGTH = 20


@cache
def _login() -> ClientMeta:
    """Create a new client and login to FreeIPA."""
    username = LDAPDN(CONFIG.ldap_bind_user).rdns[0][0][1]

    client = ClientMeta(
        CONFIG.ldap_host.host, verify_ssl=CONFIG.ldap_certificate_location.as_posix()
    )

    client.login(username, CONFIG.ldap_bind_password.get_secret_value())

    return client


class _RetryingClient:
    """
    Proxy for the cached FreeIPA client.

    FreeIPA sessions expire after a while, which turns into ``Unauthorized`` errors on the
    long-lived cached client. Retry once with a freshly logged-in client when that happens.
    """

    def __getattr__(self, name: str) -> Any:
        def method(*args: Any, **kwargs: Any) -> Any:
            try:
                return getattr(_login(), name)(*args, **kwargs)
            except Unauthorized:
                _login.cache_clear()
                return getattr(_login(), name)(*args, **kwargs)

        return method


client = _RetryingClient()


def get_user(username: str) -> dict:
    """Fetch a user from FreeIPA."""
    return client.user_show(username)


def set_user_groups(username: str, groups: list[str]) -> None:
    """
    Update a members groups to the provided list.

    Any managed groups not specified will be removed from the user.
    """
    user = get_user(username)

    memberof_groups = user.get("result", {}).get("memberof_group", [])

    add_groups = [group for group in groups if group not in memberof_groups]
    remove_groups = [
        group for group in memberof_groups if group not in groups and group in LDAP_ROLE_MAPPING
    ]

    for group in add_groups:
        client.group_add_member(group, o_user=[username])

    for group in remove_groups:
        client.group_remove_member(group, o_user=[username])


def deactivate_user(username: str) -> None:
    """Deactivate a user in FreeIPA."""
    client.user_mod(username, o_nsaccountlock=True)


def activate_user(username: str) -> None:
    """Activate a user in FreeIPA."""
    client.user_mod(username, o_nsaccountlock=False)


def create_user(username: str, display_name: str, groups: list[str], discord_id: int) -> str:
    """
    Create a new user in FreeIPA. If the user exists, the password is reset and returned.

    Returns the new user password on success.
    """
    pw = token_urlsafe(PW_LENGTH)

    client.user_add(
        username,
        o_givenname=display_name,
        o_cn=display_name,
        o_sn=display_name,
        o_displayname=display_name,
        o_userpassword=pw,
        o_employeenumber=discord_id,
    )

    for group in groups:
        client.group_add_member(group, o_user=[username])

    return pw


def delete_user(username: str) -> None:
    """Delete a user from FreeIPA."""
    client.user_del(username)
