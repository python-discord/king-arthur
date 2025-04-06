.PHONY: all install lock lint precommit start format

all: install precommit

install:
	uv sync --frozen --all-groups

lock:
	uv lock --upgrade
	uv sync --frozen --all-groups

outdated:
	uv tree --outdated

lint:
	uv run pre-commit run --all-files

precommit:
	uv run pre-commit install

start:
	uv run python -m arthur

format:
	uv run ruff format arthur
