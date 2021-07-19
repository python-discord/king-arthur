from typing import Optional

import aiohttp

from arthur.config import CONFIG


CF_TOKEN = CONFIG.cloudflare_token

async def list_zones(zone_name: Optional[str] = None) -> dict[str, str]:

    endpoint = f"https://api.cloudflare.com/client/v4/zones"
    request_headers = {
        "X-Auth-User-Service-Key": CF_TOKEN
    }

    if zone_name is not None:
        endpoint += f"?name={zone_name}"

    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, headers=request_headers) as response:
            info = await response.json()

    zones = info["result"]

    return {zone.name: zone.id for zone in zones}


async def purge_zone(zone_identifier: str) -> dict:

    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_identifier}/purge_cache?purge_everything=true"
    request_headers = {
        "X-Auth-User-Service-Key": CF_TOKEN
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, headers=request_headers) as response:
            info = await response.json()
    
    return {
        "success": info["success"],
        "errors": info["errors"]
    }

