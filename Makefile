# Quote-safe: repo path contains spaces. Always use $(CURDIR).
BACKEND := $(CURDIR)/backend
FRONTEND := $(CURDIR)/frontend

.PHONY: bootstrap dev worker test test-db test-all lint fmt fe-dev fe-build \
        brain-scan brain-index brain-check brain-lint

bootstrap:
	cd "$(BACKEND)" && uv sync
	cd "$(FRONTEND)" && pnpm install

dev:
	cd "$(BACKEND)" && uv run uvicorn app.main:app --reload --port 8000

worker:
	cd "$(BACKEND)" && uv run python -m app.worker

test:
	cd "$(BACKEND)" && uv run pytest -m "not db" -q

test-db:
	cd "$(BACKEND)" && uv run pytest -m db -q

test-all:
	cd "$(BACKEND)" && uv run pytest -q

lint:
	cd "$(BACKEND)" && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd "$(FRONTEND)" && pnpm -r lint && pnpm -r typecheck

fmt:
	cd "$(BACKEND)" && uv run ruff check --fix . && uv run ruff format .

fe-dev:
	cd "$(FRONTEND)" && pnpm --filter storefront dev

fe-build:
	cd "$(FRONTEND)" && pnpm -r build

# --- .brain code wiki ---------------------------------------------------------
brain-scan:
	bash "$(CURDIR)/.brain/scripts/brain-scan.sh" --summary

brain-index:
	bash "$(CURDIR)/.brain/scripts/brain-index.sh"

brain-lint:
	bash "$(CURDIR)/.brain/scripts/brain-scan.sh" --lint

# Fails if any page has drifted from the file it documents. Wired into CI.
brain-check:
	bash "$(CURDIR)/.brain/scripts/brain-scan.sh" --check
