.PHONY: docs docs-serve all test build format check lint clean

all: test lint

check: lint

lint:
	uv run --active ruff check
	uv run --active ruff format --check
	uv run --active ty check
	uv run --active pyrefly check
	uv run --active zuban check
	uv run --active mypy src
	# uv run --active mypy --strict src

format:
	uv run --active ruff format src tests
	uv run --active ruff check src tests --fix
	uv run --active ruff format src tests

# astero's own suite, then each worked example's. The examples are the
# library's only consumers here, so a change that breaks one shows up in the
# same command.
test:
	uv run pytest
	$(MAKE) -C examples test

test-cov:
	uv run pytest --cov=astero --cov-report=html --cov-report=term tests

clean:
	rm -rf .pytest_cache .ruff_cache dist build __pycache__ .mypy_cache \
		.coverage htmlcov .coverage.* *.egg-info
	adt clean

build: clean
	uv build

publish: build
	uv publish

# `--python 3.13`: the docs group is marked for 3.13+, so on the project's
# own interpreter uv installs none of it and falls through to whatever
# `zensical` happens to be on PATH. That built the site without mkdocstrings
# and so without the API reference, silently.
docs:
	uv run --group docs --python 3.13 zensical build -f docs/zensical.toml --strict

docs-serve:
	uv run --group docs --python 3.13 zensical serve -f docs/zensical.toml
