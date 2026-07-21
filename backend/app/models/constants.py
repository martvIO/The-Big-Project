from enum import StrEnum


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class StaffRole(StrEnum):
    # Owner-only in v1; the real role model gets its first consumer in E6.
    OWNER = "owner"


class AuditAction(StrEnum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"


class PlatformAuditAction(StrEnum):
    TENANT_PROVISIONED = "tenant_provisioned"
    TENANT_PROVISION_FAILED = "tenant_provision_failed"
    TENANT_SUSPENDED = "tenant_suspended"
    OWNER_PASSWORD_RESET = "owner_password_reset"
