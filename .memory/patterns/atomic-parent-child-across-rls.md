# Pattern: Atomically create an RLS-free parent + RLS-forced child

To create a tenant (RLS-free `tenants`) and its owner (RLS-forced `staff_users`)
in ONE transaction: generate the tenant UUID client-side (`tenant_id = uuid4()`),
open `tenant_session(session_factory, tenant_id)` to bind the RLS context up
front, then insert the parent `Tenant(id=tenant_id, …)` and the child
`StaffUser(tenant_id=tenant_id, …)` in that session. The child's `WITH CHECK`
sees the context = its tenant_id and passes; both commit together or roll back
together. Any exception before the `async with` exits triggers `session.begin()`'s
rollback → no orphan parent.

Test the rollback explicitly: monkeypatch the child insert to raise, then assert
(via a superuser connection) that no parent row survives.

**Origin (2026-07-22, Feature 6 provisioning).** Reuse for E6 (roles) and E10
(offboarding). Exploits that the parent table is RLS-free while the child is
RLS-forced.
