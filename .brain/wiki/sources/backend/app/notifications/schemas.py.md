---
tags: [backend, notifications, otp, python, pydantic, api, schemas]
sources: [backend/app/notifications/schemas.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/schemas.py
blob: a942530f55f90c96c9ab5972ba118d7715405141
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/schemas.py

**Role.** The three Pydantic models on the public OTP wire — send request, verify request, verify response — plus the two length ceilings that stop an oversized body from ever reaching the service layer.

**Module.** [[backend/app/notifications/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MAX_PHONE_INPUT_LENGTH` | const | `32` |
| `MAX_CODE_INPUT_LENGTH` | const | `16` |
| `OtpSendRequest` | model | `phone: str` (1–32) |
| `OtpVerifyRequest` | model | `phone: str` (1–32), `code: str` (1–16) |
| `OtpVerifyResponse` | model | `verification_token: str`, `expires_at: datetime` |

## Behavior

The length bounds are **ceilings, not formats**. Real validation — charset, Israeli-mobile shape, E.164 normalization — happens once in [[backend/app/notifications/validation.py#normalize_israeli_mobile]], and the database never stores a raw value; these `Field` constraints exist only so a megabyte `phone` cannot be handed to the regex engine on an unauthenticated endpoint. `MAX_CODE_INPUT_LENGTH` is 16 rather than 6 for the same reason: rejecting a wrong-length code here would leak the code length and would also break the staging `otp_dev_code` escape hatch, which need not be six digits.

None of these subclass a manage-side schema, per the F10 rule: the public wire is defined by narrow models, never by inheritance from a richer one, so a field added to an internal model can never quietly become publicly writable or publicly readable.

`OtpVerifyResponse` is the only place a `verification_token` crosses the wire, which is why the router pins `cache-control: no-store` on it.

## Depends On

- [[Pydantic]] — `BaseModel`, `Field`

## Depended On By

- [[backend/app/notifications/router.py]] — request/response models for both endpoints
- [[backend/app/booking/schemas.py]] — imports `MAX_PHONE_INPUT_LENGTH` so the booking-create phone field shares one ceiling

## Concepts

- [[Public Wire Schemas]]

## Tests

- [[backend/tests/test_notifications_api.py]] — `test_malformed_body_is_a_house_shape_400`, `test_invalid_phone_maps_to_validation_error`, `test_verify_returns_the_token_once`

## Notes

A Pydantic length rejection produces the house-shaped 422→400 envelope from [[backend/app/main.py]]'s validation handler, whereas a phone that passes the ceiling but fails normalization produces a `DomainValidationError` 400 — two different code paths, one indistinguishable-enough outcome for the caller.
