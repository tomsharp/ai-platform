.PHONY: db-up db-down db-reset db-seed

# Absolute path to this Makefile's directory (gateway/)
GATEWAY_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
# Parent directory (repo root)
ROOT_DIR := $(abspath $(GATEWAY_DIR)/..)

db-up:
	docker run --name gateway-postgres \
		-e POSTGRES_USER=gateway \
		-e POSTGRES_PASSWORD=gateway \
		-e POSTGRES_DB=gateway \
		-p 5432:5432 \
		-d postgres:16 || true
	@echo "Waiting for Postgres to be ready..."
	@until docker exec gateway-postgres pg_isready -U gateway -d gateway >/dev/null 2>&1; do \
		sleep 1; \
	done
	cd $(ROOT_DIR) && python -m gateway.seed

db-down:
	docker stop gateway-postgres || true
	docker rm gateway-postgres || true
	docker volume prune -f
