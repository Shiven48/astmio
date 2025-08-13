.PHONY: format lint lint-fix test install-dev clean pre-commit-install all

install:
	uv sync --extra dev

pre-commit-install:
	uv run pre-commit install

format:
	uv run black astmio tests
	uv run ruff format astmio tests

lint:
	uv run ruff check astmio tests

lint-fix:
	uv run ruff check --fix astmio tests

test:
	uv run pytest tests/

clean:
	rm -rf build/ dist/ *.egg-info/
	rm -rf .venv .uv_cache .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

all: format lint test
