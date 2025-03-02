.PHONY: all lock lint precommit start format

all: lock precommit

lock:
	uv lock --upgrade
	uv sync --frozen --all-groups

lint:
	uv run pre-commit run --all-files

precommit:
	uv run pre-commit install

start:
	uv run python -m arthur

format:
	uv run ruff format arthur
