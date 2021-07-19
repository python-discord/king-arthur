import aiohttp

async def purge_zone(zone_identifier: str, api_token: str) -> dict:

    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_identifier}/purge_cache?purge_everything=true"
    request_headers = {
        "X-Auth-User-Service-Key": api_token
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, headers=request_headers) as response:
            info = await response.json()
    
    return {
        "success": info["success"],
        "errors": info["errors"],
        "messages": info["messages"]
    }

