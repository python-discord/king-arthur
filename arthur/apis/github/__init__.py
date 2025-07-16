from arthur.config import CONFIG

from .orgs import remove_org_member
from .teams import add_staff_member


class GitHubError(Exception):
    """Custom exception for GitHub API errors."""

    def __init__(self, message: str):
        super().__init__(message)


__all__ = ("GitHubError", "add_staff_member", "remove_org_member")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {CONFIG.github_token.get_secret_value()}",
}
HTTP_404 = 404
HTTP_403 = 403
HTTP_422 = 422
