"""Entrypoint for King Arthur."""
from arthur import logger
from arthur.bot import KingArthur
from arthur.config import CONFIG


@logger.catch()
def start() -> None:
    """Entrypoint for King Arthur."""
    arthur = KingArthur()

    arthur.run(CONFIG.token)


if __name__ == "__main__":
    start()
