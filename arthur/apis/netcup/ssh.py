import asyncssh

from arthur.config import CONFIG


async def rce_as_a_service(command: str) -> asyncssh.SSHCompletedProcess:
    """Run the given command on the configured server."""
    async with asyncssh.connect(
        username=CONFIG.ssh_username,
        host=CONFIG.ssh_host,
    ) as conn:
        result = await conn.run(command)
    return result
