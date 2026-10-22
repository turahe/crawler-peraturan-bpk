# Development

## Repository layout

```text
src/playright_peraturan_bpk/  crawler package, database setup, ORM models
migrations/                   Alembic environment and schema revisions
tests/                        crawler and persistence tests
docs/                         project documentation
.github/workflows/ci.yml      continuous integration workflow
Dockerfile                    multi-stage Python image build
compose.yml                   PostgreSQL, RustFS, migration, and app services
pyproject.toml                package metadata, runtime dependencies, tool configuration
uv.lock                       locked dependency resolution
```

`__main__.py` enables `python -m playright_peraturan_bpk`. `main.py` contains the crawler behavior; `database.py` owns engine/session configuration; `models.py` owns ORM mappings. Keep schema changes synchronized between models and new Alembic revisions.

## Dependencies and packaging

Runtime dependencies are declared in `pyproject.toml` and resolved in `uv.lock`. The Docker build installs the project into a Python 3.14 runtime image. The console script is named `playright-peraturan-bpk`.

Development tooling lives in the `dev` dependency group and is installed with `uv sync --group dev`. It pins `ruff`, `mypy`, `pytest`, and `pytest-cov`; update `uv.lock` whenever the group changes.

## Quality gates

Run the same checks as CI before pushing:

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

`ruff` and `mypy` settings live in `pyproject.toml`, so the rules are identical locally and in CI. The `migrations/versions/` directory and the vendored `.specify/` scripts are excluded from linting because Alembic and Spec Kit generate them.

## Tests

Tests are under `tests/` and use SQLite and HTTP response fixtures/mocks for crawler behavior. Run the project test suite with the repository's selected Python environment, for example:

```sh
uv run pytest
```

The tests do not require a live BPK site, PostgreSQL, or RustFS when external requests and persistence are isolated by fixtures.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main`, on pull requests, and on demand. It has three jobs:

- `quality`: lint, format check, type check, and the test suite with coverage.
- `migrations`: applies the Alembic migrations against a PostgreSQL 18 service, runs `alembic check` to detect model drift, and verifies the revisions downgrade and re-apply cleanly.
- `docker`: validates the Compose file, builds the container image, and smoke tests the packaged runtime.

The workflow installs dependencies with `uv sync --group dev --frozen`, so a stale `uv.lock` fails the build instead of silently resolving new versions.

## Change checklist

1. Update implementation and ORM mappings.
2. Add a migration for schema changes and ensure its downgrade is coherent.
3. Add or update focused tests for behavior changes.
4. Update the relevant docs when configuration, workflow, schema, or operations change.
5. Run the quality gates listed above.
6. Check Compose configuration with `cp .env.example .env && docker compose config --quiet` when changing `compose.yml`.
