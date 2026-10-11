help:
	@echo "Available targets:"
	@echo "  migrate-db        Apply database migrations (Alembic upgrade head)"
	@echo "  build-docker      Build the Docker Compose app image"
	@echo "  run-docker        Start the Docker Compose services"
	@echo "  run-build-docker  Build and start the Docker Compose services"

migrate-db:
	docker compose run --build --rm app alembic upgrade head

run-docker:
	docker compose up -d

build-docker:
	docker compose build app

run-build-docker: build-docker run-docker