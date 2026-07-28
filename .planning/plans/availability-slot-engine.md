# Plan: Feature 12 — Availability & Slot Engine (Epic E3)

**Spec**: `.planning/specs/availability-slot-engine.md` · **Branch**: `feature/availability-slot-engine` · **Created**: 2026-07-28

TDD throughout. Local gate per task: `make lint` + `make test`. No migration in this feature.

## Task 1 — Constants + the Israeli week (fast tests)
`Backend/app/booking/__init__.py`, `validation.py` + `tests/test_slot_engine.py`
- `SLOT_INTERVAL_MINUTES`, `DEFAULT_SLOT_CAPACITY`, `SLOT_WINDOW_DEFAULT_DAYS`, `SLOT_WINDOW_MAX_DAYS`.
- `jerusalem_day_index(date)` + table test over real dates across a year.
- Parity row in `tests/test_frontend_constant_parity.py` against `packages/ui/src/lib/hours.ts`.

## Task 2 — The engine (fast tests, the bulk of the feature)
`Backend/app/booking/slots.py`
- `Slot` frozen dataclass (`starts_at`, `capacity`, `booked`, `remaining`).
- `materialize_slots(...)` per the spec's six ordered rules.
- Tests: grid boundaries, multi-window days, exceptions (closed / replace / open-a-closed-day / capacity inheritance), DST nonexistent + ambiguous, capacity subtraction incl. the `booked > capacity` anomaly, `now` boundary, sort order.

## Task 3 — Service reads (db tests)
`Backend/app/storefront/service.py` (+ `validation.py` for window clamping)
- `list_slots(tenant_id, *, window_start, window_end, now)` — one `tenant_session`, rules + exceptions-in-window reads, `booked={}` with the F13 seam docstring.
- `list_appointment_types(tenant_id)` — reuses `AppointmentTypesRepository.list_active`.
- Window validation: `to < from` → domain 400; clamp to `SLOT_WINDOW_MAX_DAYS`.
- `tests/test_storefront_integration.py` additions + an isolation row in `tests/test_storefront_isolation.py`.

## Task 4 — Routes + schemas (API tests)
`Backend/app/storefront/router.py`, `schemas.py`
- `GET /storefront/slots`, `GET /storefront/appointment-types` on the existing router.
- `SlotRow` (`starts_at`, `remaining` — never `capacity`), `SlotListResponse`, `AppointmentTypeRow`.
- `tests/test_storefront_api.py`: extend the expected route set (deliberate literal), fake-service rows, window validation, the empty-`booked` seam asserted explicitly.

## Task 5 — Review + ship
- `make lint && make test` clean.
- Dual review: phase-reviewer + adversarial security (window abuse/DoS via huge ranges, capacity disclosure, tenant isolation, DST correctness).
- Epic row F12 → building/done; PR `Feature 12: Availability & slot engine (Epic E3)`; watch `gh pr checks`; merge.

## Commit sequence
1. `docs(planning): F12 spec + plan (Gate 1)`
2. `feat(booking): slot constants and the Israeli week conversion (TDD)`
3. `feat(booking): the pure slot materialization engine`
4. `feat(storefront): slot and appointment-type reads`
5. `feat(storefront): public slots and appointment-types endpoints`
6. review fixes, then PR.
