.PHONY: help up status verify check test seed-export seed-import stop

help:
	@echo "up          Build and start the local stack (DAILY schedule follows .env)"
	@echo "status      Show Compose services"
	@echo "verify      Read-only PostgreSQL verification"
	@echo "check       Python syntax, Svelte/TypeScript and frontend lint"
	@echo "test        Offline Python tests and frontend integration tests"
	@echo "seed-export Export an offline Parquet snapshot to a new directory"
	@echo "seed-import Restore the bundled snapshot into an empty schema only"
	@echo "stop        Stop services without deleting volumes"

up:
	docker compose up -d --build

status:
	docker compose ps

verify:
	docker compose run --rm --no-deps pipeline python -m backend.flow verify

check:
	docker compose run --rm --no-deps pipeline python -m compileall -q backend
	npm --prefix frontend run check
	npm --prefix frontend run lint

test:
	docker compose run --rm --no-deps pipeline python -m unittest discover -s backend/tests -q
	DASHBOARD_TEST_URL=http://127.0.0.1:3000 npm --prefix frontend run test:integration

seed-export:
	docker compose run --rm --no-deps pipeline python -m backend.flow seed-export --seed-dir data/seed/$(shell date +%Y-%m-%d-%H%M%S)

seed-import:
	docker compose run --rm --no-deps pipeline python -m backend.flow seed-import

stop:
	docker compose stop
