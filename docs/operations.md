# Operations

## Database migrations

Alembic reads `DATABASE_URL` or the `POSTGRES_*` variables through `src/playright_peraturan_bpk/database.py`. In Compose, the `migrate` service runs `alembic upgrade head` after PostgreSQL is healthy; the crawler is gated on successful completion.

To apply migrations manually in Compose:

```sh
docker compose run --build --rm app alembic upgrade head
```

Create a new revision with Alembic's normal revision workflow, inspect the generated upgrade and downgrade functions, and commit the migration with any matching ORM change. Do not edit already-applied migration files.

## Configuration reference

| Variable | Default / example | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | constructed from `POSTGRES_*` | Full SQLAlchemy database URL; overrides individual DB settings |
| `POSTGRES_HOST` | `localhost` in Python; `postgres` in Compose | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `peraturan_bpk` in Python; `mydb` in Compose | Database name |
| `POSTGRES_USER` | `postgres` in Python; `user` in Compose | Database username |
| `POSTGRES_PASSWORD` | `postgres` in Python; `password` in Compose | Database password |
| `RUSTFS_ENDPOINT` | unset in app code; `http://rustfs:9000` in Compose | S3-compatible endpoint; unset disables uploads |
| `RUSTFS_ACCESS_KEY` | `admin` in Compose | RustFS access key |
| `RUSTFS_SECRET_KEY` | `password` in Compose | RustFS secret key |
| `RUSTFS_BUCKET` | `documents` | Bucket used for object uploads |
| `RUSTFS_PREFIX` | `pdf` | Prefix for uploaded PDF object keys |
| `CRAWLER_REQUEST_DELAY_SECONDS` | `0.5` | Minimum interval between HTTP requests |
| `CRAWLER_THREADS` | `4` | Maximum concurrent regulation processors in inline mode |
| `CRAWLER_MODE` | `producer` in Compose; `inline` locally | `producer` dispatches Celery tasks; `inline` runs both stages in one process |
| `RABBITMQ_URL` | `amqp://crawler:crawler-password@localhost:5672/%2F` | RabbitMQ AMQP connection URL |
| `RABBITMQ_QUEUE` | `regulation_crawl` | Durable queue for regulation IDs |
| `RABBITMQ_USER` | `crawler` in Compose | RabbitMQ application user |
| `RABBITMQ_PASSWORD` | `crawler-password` in Compose | RabbitMQ application password |
| `CELERY_CONCURRENCY` | `2` | Number of concurrent Celery worker processes in Compose |

Compose defaults are for local development only; override credentials before using a shared or exposed environment.

## Data locations and ports

- PostgreSQL data: `data/postgres` on the host.
- RustFS objects: `data/rustfs` on the host.
- Downloaded PDFs: `data/pdf` on the host.
- RustFS API: host port `8080` mapped to container port `9000`.
- RustFS console: host port `9001`.
- PostgreSQL: host port `5432`.
- RabbitMQ AMQP: host port `5672`; management UI: host port `15672`.

All three data directories are local bind mounts and are excluded from the Docker build context. Back up data before removing or replacing these directories.

## Troubleshooting

- **App never starts:** check `docker compose ps -a` and logs for `postgres`, `migrate`, and `app`. The app is intentionally held until the migration exits successfully.
- **Migration fails:** verify PostgreSQL health and all `POSTGRES_*` values. Fix the migration or database issue, then rerun the migration service.
- **RustFS upload fails:** check endpoint, credentials, bucket, and RustFS logs. Local PDF downloads are stored separately under `data/pdf`.
- **Container exits with code 0:** the crawl finished. Inspect the app summary and use `docker compose logs app` for its output.
- **Repeated restarts:** the app restarts on failure. Review the last app log before restarting the stack.
