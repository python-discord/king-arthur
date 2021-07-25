"""APIs for managing Cloudflare zones."""
from typing import Optional

import aiohttp

from arthur.config import CONFIG

AUTH_HEADER = {
    "Authorization": f"Bearer {CONFIG.cloudflare_token}"
}


async def list_zones(zone_name: Optional[str] = None) -> dict[str, str]:
    """List all Cloudflare zones."""
    endpoint = "https://api.cloudflare.com/client/v4/zones"

    if zone_name is not None:
        endpoint += f"?name={zone_name}"

    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, headers=AUTH_HEADER) as response:
            info = await response.json()

    zones = info["result"]

    return {zone["name"]: zone["id"] for zone in zones}


async def purge_zone(zone_identifier: str) -> dict:
    """Purge the cache for a Cloudflare zone."""
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_identifier}"

    request_body = {
        "purge_everything": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, headers=AUTH_HEADER, json=request_body) as response:
            info = await response.json()

    return {"success": info["success"], "errors": info["errors"]}
