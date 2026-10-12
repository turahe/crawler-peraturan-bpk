# Setup and running

## Requirements

- Docker Engine with the Docker Compose plugin.
- A copy of this repository.

The container image is built from `Dockerfile` using Python 3.14. Compose starts PostgreSQL, RustFS, a one-shot Alembic migration service, and the crawler app.

## Configure

Copy `.env.example` to `.env` if you want to override defaults. Compose reads this file for the `app` and `migrate` services. The example configures RustFS credentials, bucket, prefix, request delay, and PostgreSQL connection settings.

Inside Compose, the app uses `postgres:5432` and `http://rustfs:9000` for service-to-service connections. From the host, RustFS's S3-compatible API is exposed at `http://localhost:8080`, and its console is exposed at `http://localhost:9001`.

## Run with Compose

```sh
docker compose up -d --build
docker compose logs -f app
```

Compose waits for PostgreSQL's health check, runs `alembic upgrade head` in `migrate`, and starts `app` after the migration succeeds and RustFS starts. The app runs the crawler once. Its restart policy retries failures, while a successful crawl exits normally.

Useful commands:

```sh
docker compose ps -a
docker compose logs --tail=100 app migrate postgres rustfs
docker compose build app
docker compose down
```

`docker compose down` leaves bind-mounted data in `data/`. Removing that directory deletes local database, object-store, and PDF data.

## Local Python execution

The package requires Python 3.14 or newer. Install the project and its dependencies with the repository's Python packaging workflow, then set `DATABASE_URL` or the `POSTGRES_*` variables and run:

```sh
python -m playright_peraturan_bpk
```

The crawler expects a reachable PostgreSQL database and creates downloaded files under `data/pdf`. For DB schema setup use `alembic upgrade head` after setting the database environment. RustFS upload is optional; configure `RUSTFS_ENDPOINT`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, and `RUSTFS_BUCKET` to enable it.
