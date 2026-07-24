from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import get_current_staff
from app.auth.service import StaffContext
from app.boutique.schemas import (
    AppointmentTypeResponse,
    AvailabilityExceptionResponse,
    AvailabilityResponse,
    AvailabilityRuleResponse,
    CreateAppointmentTypeRequest,
    CreateAvailabilityExceptionRequest,
    CreateTermsRequest,
    OkResponse,
    ReplaceWeeklyRulesRequest,
    SettingsResponse,
    TermsHistoryResponse,
    TermsVersionResponse,
    UpdateAppointmentTypeRequest,
    UpdateSettingsRequest,
)
from app.boutique.service import TERMS_HISTORY_DEFAULT_LIMIT, BoutiqueSettingsService
from app.boutique.validation import WeeklyRuleInput
from app.tenancy.middleware import get_current_tenant

router = APIRouter(prefix="/manage")

Staff = Annotated[StaffContext, Depends(get_current_staff)]


def get_boutique_service(request: Request) -> BoutiqueSettingsService:
    return request.app.state.boutique_service


Service = Annotated[BoutiqueSettingsService, Depends(get_boutique_service)]


# --- profile + toggles ---


@router.get("/settings")
async def get_settings(request: Request, staff: Staff, service: Service) -> SettingsResponse:
    tenant = get_current_tenant(request)
    result = await service.get_settings(tenant.id)
    return SettingsResponse(profile=result.profile, toggles=result.toggles)


@router.put("/settings")
async def update_settings(
    request: Request, staff: Staff, service: Service, body: UpdateSettingsRequest
) -> SettingsResponse:
    tenant = get_current_tenant(request)
    # exclude_unset: the JSONB merge replaces whole top-level keys, so only
    # fields the client actually sent may enter the patch.
    profile = body.profile.model_dump(exclude_unset=True) if body.profile is not None else None
    toggles = body.toggles.model_dump(exclude_unset=True) if body.toggles is not None else None
    result = await service.update_settings(tenant.id, profile=profile, toggles=toggles)
    return SettingsResponse(profile=result.profile, toggles=result.toggles)


# --- appointment types ---


@router.get("/appointment-types")
async def list_appointment_types(
    request: Request, staff: Staff, service: Service
) -> list[AppointmentTypeResponse]:
    tenant = get_current_tenant(request)
    rows = await service.list_appointment_types(tenant.id)
    return [AppointmentTypeResponse.model_validate(row) for row in rows]


@router.post("/appointment-types")
async def create_appointment_type(
    request: Request, staff: Staff, service: Service, body: CreateAppointmentTypeRequest
) -> AppointmentTypeResponse:
    tenant = get_current_tenant(request)
    row = await service.create_appointment_type(
        tenant.id,
        name=body.name,
        duration_minutes=body.duration_minutes,
        audience=body.audience,
        deposit_required=body.deposit_required,
        deposit_amount_agorot=body.deposit_amount_agorot,
        sort_order=body.sort_order,
    )
    return AppointmentTypeResponse.model_validate(row)


@router.patch("/appointment-types/{type_id}")
async def update_appointment_type(
    request: Request,
    staff: Staff,
    service: Service,
    type_id: UUID,
    body: UpdateAppointmentTypeRequest,
) -> AppointmentTypeResponse:
    tenant = get_current_tenant(request)
    row = await service.update_appointment_type(
        tenant.id,
        type_id,
        name=body.name,
        duration_minutes=body.duration_minutes,
        audience=body.audience,
        deposit_required=body.deposit_required,
        deposit_amount_agorot=body.deposit_amount_agorot,
        sort_order=body.sort_order,
    )
    return AppointmentTypeResponse.model_validate(row)


@router.delete("/appointment-types/{type_id}")
async def archive_appointment_type(
    request: Request, staff: Staff, service: Service, type_id: UUID
) -> OkResponse:
    tenant = get_current_tenant(request)
    await service.archive_appointment_type(tenant.id, type_id)
    return OkResponse()


# --- availability ---


@router.get("/availability")
async def get_availability(
    request: Request, staff: Staff, service: Service
) -> AvailabilityResponse:
    tenant = get_current_tenant(request)
    result = await service.get_availability(tenant.id)
    return AvailabilityResponse(
        rules=[AvailabilityRuleResponse.model_validate(rule) for rule in result.rules],
        exceptions=[AvailabilityExceptionResponse.model_validate(row) for row in result.exceptions],
    )


@router.put("/availability/rules")
async def replace_weekly_rules(
    request: Request, staff: Staff, service: Service, body: ReplaceWeeklyRulesRequest
) -> list[AvailabilityRuleResponse]:
    tenant = get_current_tenant(request)
    inputs = [
        WeeklyRuleInput(
            day_of_week=rule.day_of_week,
            open_time=rule.open_time,
            close_time=rule.close_time,
            capacity=rule.capacity,
        )
        for rule in body.rules
    ]
    rows = await service.replace_weekly_rules(tenant.id, inputs)
    return [AvailabilityRuleResponse.model_validate(row) for row in rows]


@router.post("/availability/exceptions")
async def add_availability_exception(
    request: Request, staff: Staff, service: Service, body: CreateAvailabilityExceptionRequest
) -> AvailabilityExceptionResponse:
    tenant = get_current_tenant(request)
    row = await service.add_availability_exception(
        tenant.id,
        date=body.date,
        open_time=body.open_time,
        close_time=body.close_time,
        note=body.note,
    )
    return AvailabilityExceptionResponse.model_validate(row)


@router.delete("/availability/exceptions/{exception_id}")
async def remove_availability_exception(
    request: Request, staff: Staff, service: Service, exception_id: UUID
) -> OkResponse:
    tenant = get_current_tenant(request)
    await service.remove_availability_exception(tenant.id, exception_id)
    return OkResponse()


# --- cancellation-policy terms ---


@router.get("/terms")
async def get_terms_history(
    request: Request,
    staff: Staff,
    service: Service,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=TERMS_HISTORY_DEFAULT_LIMIT)] = (
        TERMS_HISTORY_DEFAULT_LIMIT
    ),
) -> TermsHistoryResponse:
    tenant = get_current_tenant(request)
    result = await service.get_terms_history(tenant.id, offset=offset, limit=limit)
    current = (
        TermsVersionResponse.model_validate(result.current) if result.current is not None else None
    )
    return TermsHistoryResponse(
        current=current,
        versions=[TermsVersionResponse.model_validate(row) for row in result.versions],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.post("/terms")
async def create_terms_version(
    request: Request, staff: Staff, service: Service, body: CreateTermsRequest
) -> TermsVersionResponse:
    tenant = get_current_tenant(request)
    row = await service.create_terms_version(
        tenant.id,
        terms_text=body.terms_text,
        refundable_until_hours_before=body.refundable_until_hours_before,
        forfeit_percent=body.forfeit_percent,
        created_by=staff.id,
    )
    return TermsVersionResponse.model_validate(row)
