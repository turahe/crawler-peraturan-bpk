FROM python:3.14-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip setuptools wheel && \
	python -m pip install --no-cache-dir .

FROM python:3.14-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

COPY --from=builder /usr/local /usr/local
COPY . .

CMD ["sh", "-c", "alembic upgrade head && exec python -m playright_peraturan_bpk"]