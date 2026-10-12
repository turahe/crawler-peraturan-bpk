# Development

## Repository layout

```text
src/playright_peraturan_bpk/  crawler package, database setup, ORM models
migrations/                   Alembic environment and schema revisions
tests/                        crawler and persistence tests
docs/                         project documentation
Dockerfile                    multi-stage Python image build
compose.yml                   PostgreSQL, RustFS, migration, and app services
pyproject.toml                package metadata and runtime dependencies
uv.lock                       locked dependency resolution
```

`__main__.py` enables `python -m playright_peraturan_bpk`. `main.py` contains the crawler behavior; `database.py` owns engine/session configuration; `models.py` owns ORM mappings. Keep schema changes synchronized between models and new Alembic revisions.

## Dependencies and packaging

Runtime dependencies are declared in `pyproject.toml` and resolved in `uv.lock`. The Docker build installs the project into a Python 3.14 runtime image. The console script is named `playright-peraturan-bpk`.

## Tests

Tests are under `tests/` and use SQLite and HTTP response fixtures/mocks for crawler behavior. Run the project test suite with the repository's selected Python environment, for example:

```sh
pytest
```

The tests do not require a live BPK site, PostgreSQL, or RustFS when external requests and persistence are isolated by fixtures.

## Change checklist

1. Update implementation and ORM mappings.
2. Add a migration for schema changes and ensure its downgrade is coherent.
3. Add or update focused tests for behavior changes.
4. Update the relevant docs when configuration, workflow, schema, or operations change.
5. Check Compose configuration with `docker compose config --quiet` when changing `compose.yml`.
