PY ?= .venv/bin/python
UV ?= uv

.PHONY: setup dev dev-api dev-web build-web lint fmt test check dist clean

setup:  ## Create venv, install python + node deps, write dev config
	$(UV) venv --python 3.11 .venv || true
	$(UV) pip install --python $(PY) -e ".[dev]"
	cd web && npm ci
	@test -f dev/config.yaml || HOMELY_CONFIG=dev/config.yaml HOMELY_STATE_DIR=dev/state $(PY) -m homely config init --backend none
	@echo "Done. Run 'make dev' and open http://localhost:5173"

dev:  ## Run API (8080) and Vite (5173) together
	$(MAKE) -j2 dev-api dev-web

dev-api:
	HOMELY_CONFIG=dev/config.yaml HOMELY_STATE_DIR=dev/state $(PY) -m homely run --backend none --port 8080

dev-web:
	cd web && npm run dev -- --host

build-web:  ## Build the Svelte app into src/homely/web/static
	cd web && npm run build

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests
	$(PY) -m mypy

fmt:
	$(PY) -m ruff check --fix src tests
	$(PY) -m ruff format src tests

test:
	$(PY) -m pytest

check: lint test

dist: build-web  ## Build wheel + sdist (includes built frontend)
	$(PY) -m build

clean:
	rm -rf dist build .mypy_cache .ruff_cache .pytest_cache tests/.golden_out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
