.PHONY: all install lock lint precommit start format

all: install precommit

install:
	uv sync --frozen --all-groups

just-lock:
	uv lock --upgrade

lock: just-lock install

outdated:
	uv tree --outdated --all-groups

lint:
	uv run pre-commit run --all-files

precommit:
	uv run pre-commit install

start:
	uv run python -m arthur

format:
	uv run ruff format arthur
