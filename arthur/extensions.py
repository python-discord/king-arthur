"""Utilities for working with extensions."""
from pathlib import Path
from typing import Generator


def find_extensions() -> Generator[tuple[Path, str], None, None]:
    """Search the exts directory to find cogs to load."""
    for path in Path("arthur/exts").rglob("**/*.py"):
        # Convert a path like "arthur/exts/foo/bar.py" to "arthur.exts.foo.bar"
        yield path, path_to_module(path)


def path_to_module(path: Path) -> str:
    """Convert a path like "arthur/exts/foo/bar.py" to "arthur.exts.foo.bar"."""
    return str(path.parent.as_posix()).replace("/", ".") + f".{path.stem}"
