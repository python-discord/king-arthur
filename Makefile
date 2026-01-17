.PHONY: all install just-lock lock outdated lint precommit start format

all: install prek

install:
	uv sync --frozen --all-groups

just-lock:
	uv lock --upgrade

lock: just-lock install

outdated:
	uv tree --outdated --all-groups

lint:
	uv run prek run --all-files

prek:
	uv run prek install

start:
	uv run python -m arthur

format:
	uv run ruff format arthur
