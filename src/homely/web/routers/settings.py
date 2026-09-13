from __future__ import annotations

from fastapi import APIRouter, Depends

from homely.web import schemas
from homely.web.deps import Rt, require_auth

router = APIRouter(prefix="/api", tags=["settings"], dependencies=[Depends(require_auth)])


@router.get("/settings", response_model=schemas.SettingsPayload, response_model_by_alias=True)
async def get_settings(rt: Rt) -> schemas.SettingsPayload:
    return rt.settings_payload()


@router.put(
    "/settings",
    response_model=schemas.SettingsPayload,
    response_model_by_alias=True,
    responses={422: {"model": schemas.ApiErrors}},
)
async def put_settings(body: schemas.SettingsUpdate, rt: Rt) -> schemas.SettingsPayload:
    return rt.update_settings(body)


@router.put("/brightness", response_model=schemas.StateInfo)
async def put_brightness(body: schemas.BrightnessUpdate, rt: Rt) -> schemas.StateInfo:
    rt.set_brightness(body.level)
    return rt.state()


@router.get("/hardware", response_model=schemas.HardwarePayload, response_model_by_alias=True)
async def get_hardware(rt: Rt) -> schemas.HardwarePayload:
    return rt.hardware_payload()


@router.put(
    "/hardware",
    response_model=schemas.HardwarePayload,
    response_model_by_alias=True,
    responses={422: {"model": schemas.ApiErrors}},
)
async def put_hardware(body: schemas.HardwareUpdate, rt: Rt) -> schemas.HardwarePayload:
    return rt.update_hardware(body)
