---
tags: [backend, python, test]
sources: [backend/tests]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/tests
blob: 5d788ed1e835f5b867d915ea9245819e2fec677a
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/tests/

**Purpose.** The test suite. Unmarked tests run everywhere; `db`-marked tests need Docker (Testcontainers Postgres) and `s3`-marked ones additionally need MinIO, so both are CI-only.

**Parent.** [[backend/_index]]

## Files

- [[backend/tests/conftest.py]] — Guarantees that every `-m db` test runs against a real [[PostgreSQL]] 16 instance with all [[Alembic]] migrations applied **and connects as a non-owner, non-superuser login role**, so that an isolation assertion can never pass vacuously by…
- [[backend/tests/test_app_import.py]]
- [[backend/tests/test_auth_api.py]]
- [[backend/tests/test_auth_integration.py]]
- [[backend/tests/test_booking_api.py]]
- [[backend/tests/test_booking_comms_db.py]]
- [[backend/tests/test_booking_comms_templates.py]]
- [[backend/tests/test_booking_isolation.py]]
- [[backend/tests/test_booking_manage_api.py]]
- [[backend/tests/test_booking_owner_api.py]]
- [[backend/tests/test_booking_owner_db.py]]
- [[backend/tests/test_booking_owner_service.py]]
- [[backend/tests/test_booking_reminder_bands.py]]
- [[backend/tests/test_booking_repositories.py]]
- [[backend/tests/test_booking_service.py]]
- [[backend/tests/test_booking_validation.py]]
- [[backend/tests/test_boutique_api.py]]
- [[backend/tests/test_boutique_integration.py]]
- [[backend/tests/test_boutique_models.py]]
- [[backend/tests/test_boutique_service.py]]
- [[backend/tests/test_boutique_validation.py]]
- [[backend/tests/test_catalog_api.py]]
- [[backend/tests/test_catalog_integration.py]]
- [[backend/tests/test_catalog_isolation.py]]
- [[backend/tests/test_catalog_models.py]]
- [[backend/tests/test_catalog_validation.py]]
- [[backend/tests/test_cli.py]]
- [[backend/tests/test_config.py]]
- [[backend/tests/test_frontend_constant_parity.py]]
- [[backend/tests/test_health.py]]
- [[backend/tests/test_manage_token.py]]
- [[backend/tests/test_media_upload_s3.py]]
- [[backend/tests/test_middleware.py]]
- [[backend/tests/test_migrations.py]]
- [[backend/tests/test_notifications_adapters.py]]
- [[backend/tests/test_notifications_api.py]]
- [[backend/tests/test_notifications_isolation.py]]
- [[backend/tests/test_notifications_repositories.py]]
- [[backend/tests/test_notifications_service.py]]
- [[backend/tests/test_notifications_validation.py]]
- [[backend/tests/test_passwords.py]]
- [[backend/tests/test_provisioning.py]]
- [[backend/tests/test_rate_limit.py]]
- [[backend/tests/test_role_guard.py]]
- [[backend/tests/test_slot_engine.py]]
- [[backend/tests/test_slugs.py]]
- [[backend/tests/test_staff_api.py]]
- [[backend/tests/test_staff_management_db.py]]
- [[backend/tests/test_staff_role_gating.py]]
- [[backend/tests/test_staff_role_gating_integration.py]]
- [[backend/tests/test_staff_service.py]]
- [[backend/tests/test_storage_port.py]]
- [[backend/tests/test_storefront_api.py]]
- [[backend/tests/test_storefront_integration.py]]
- [[backend/tests/test_storefront_isolation.py]]
- [[backend/tests/test_storefront_validation.py]]
- [[backend/tests/test_tenancy_integration.py]]
- [[backend/tests/test_tenant_isolation.py]]
- [[backend/tests/test_tenants_repository.py]]
- [[backend/tests/test_worker.py]]
