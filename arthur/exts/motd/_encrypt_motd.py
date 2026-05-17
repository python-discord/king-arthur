"""
CLI tool to encrypt a new MOTD image and update _motd.py.

The script reads KING_ARTHUR_MOTD_KEY from the environment.

Usage:
    make encrypt-motd PNG=path/to/motd.png
"""

import argparse
import base64
import secrets
import sys
import textwrap
from pathlib import Path

from loguru import logger

from arthur.config import CONFIG
from arthur.exts.motd._motd_crypto import encrypt_motd

_HERE = Path(__file__).parent
_MOTD_PY = _HERE / "_motd_data.py"
_LINE_WIDTH = 76  # base-64 characters per line inside the bytes literal


def _load_key() -> str:
    if CONFIG.motd_key is None:
        sys.exit("KING_ARTHUR_MOTD_KEY is not set. Run with --generate-key to create one.")
    return CONFIG.motd_key.get_secret_value()


def cmd_generate_key() -> None:
    key_hex = secrets.token_hex(32)
    logger.info(f"Generated key (store this as KING_ARTHUR_MOTD_KEY):\n\n  {key_hex}\n")


def cmd_encrypt(png_path: Path) -> None:

    key = _load_key()
    plaintext = png_path.read_bytes()
    encrypted = encrypt_motd(plaintext, key)
    encoded = base64.b64encode(encrypted).decode()

    # Wrap into 76-char lines so the file stays diff-friendly.
    wrapped = "\n".join(textwrap.wrap(encoded, _LINE_WIDTH))

    _MOTD_PY.write_text(
        '"""Stores the encrypted daily MOTD (AES-256-GCM, HKDF-SHA3-256 key derivation)."""\n\n'
        "# Re-generate with:  make encrypt-motd PNG=path/to/motd.png\n"
        'MOTD = b"""\n'
        f"{wrapped}\n"
        '"""\n',
        encoding="utf-8",
    )
    logger.info(f"Wrote encrypted MOTD to {_MOTD_PY}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MOTD encryption tool")
    parser.add_argument(
        "png",
        nargs="?",
        type=Path,
        help="Path to the PNG file to encrypt.",
    )
    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="Generate a new random 32-byte key and print it.",
    )
    args = parser.parse_args()

    if args.generate_key:
        cmd_generate_key()
        return

    if args.png is None:
        parser.error("Provide a PNG path or use --generate-key.")

    if not args.png.exists():
        sys.exit(f"File not found: {args.png}")

    cmd_encrypt(args.png)


if __name__ == "__main__":
    main()
