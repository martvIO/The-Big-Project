# Quote-safe: repo path contains spaces. Always use $(CURDIR).
BACKEND := $(CURDIR)/backend
FRONTEND := $(CURDIR)/frontend

.PHONY: bootstrap dev worker test test-db test-all lint fmt fe-dev fe-build fe-test e2e qa-greps \
        brain-scan brain-index brain-check brain-lint

bootstrap:
	cd "$(BACKEND)" && uv sync
	cd "$(FRONTEND)" && pnpm install

dev:
	cd "$(BACKEND)" && uv run uvicorn app.main:app --reload --port 8000

worker:
	cd "$(BACKEND)" && uv run python -m app.worker

# DATABASE_URL points at a CLOSED port on purpose. A `not db` test must never
# open a database connection, but nothing stopped one: the default
# DEV_DATABASE_URL is localhost:5432, so a fast-lane test that accidentally
# reaches a real query passes on any dev box running a local Postgres and fails
# on CI, which has none (Testcontainers binds a random port and is wired in only
# through the `db` fixtures). That exact divergence shipped
# test_hsts_reaches_the_tenant_not_found_404 green and reddened CI. With the
# port closed, the local gate reproduces CI's environment and any such test
# fails here first, with ConnectionRefused pointing straight at the culprit.
# Only this target: `test-db`/`test-all` run the db lane, which needs a real URL.
test:
	cd "$(BACKEND)" && DATABASE_URL="postgresql+asyncpg://boutique:closed@127.0.0.1:1/no-db-in-the-fast-lane" uv run pytest -m "not db" -q

test-db:
	cd "$(BACKEND)" && uv run pytest -m db -q

test-all:
	cd "$(BACKEND)" && uv run pytest -q

lint:
	cd "$(BACKEND)" && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests scripts
	cd "$(FRONTEND)" && pnpm -r lint && pnpm -r typecheck
	bash "$(FRONTEND)/scripts/qa-greps.sh"

# qa-checklist.md §11 mechanical checks. Nothing else runs these.
qa-greps:
	bash "$(FRONTEND)/scripts/qa-greps.sh"

fmt:
	cd "$(BACKEND)" && uv run ruff check --fix . && uv run ruff format .

# 5174, not Vite's default: README documents 5173 as the manage console's, and
# F10 is the first feature that needs both servers up at once.
fe-dev:
	cd "$(FRONTEND)" && pnpm --filter storefront dev --port 5174

fe-build:
	cd "$(FRONTEND)" && pnpm -r build

fe-test:
	cd "$(FRONTEND)" && pnpm -r --if-present test

# Builds both apps and serves them via `vite preview` (see e2e/playwright.config.ts).
e2e:
	cd "$(FRONTEND)" && pnpm -r build && pnpm exec playwright install --with-deps chromium && pnpm e2e

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
