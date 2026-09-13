from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from homely.web import schemas
from homely.web.deps import Rt, require_auth
from homely.web.errors import to_api_errors

router = APIRouter(prefix="/api", tags=["modules"], dependencies=[Depends(require_auth)])


@router.get("/modules", response_model=list[schemas.ModuleCatalogEntry], response_model_by_alias=True)
async def list_modules(rt: Rt) -> list[schemas.ModuleCatalogEntry]:
    return rt.catalog()


@router.get("/rotation", response_model=list[schemas.RotationItem])
async def list_rotation(rt: Rt) -> list[schemas.RotationItem]:
    return rt.rotation_items()


@router.post("/rotation", response_model=schemas.RotationItem, status_code=201)
async def add_instance(body: schemas.RotationAdd, rt: Rt) -> schemas.RotationItem:
    try:
        return rt.add_instance(body.module, body.instance_id, body.enabled)
    except KeyError:
        raise HTTPException(404, f"unknown module {body.module!r}") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.put("/rotation/order", response_model=list[schemas.RotationItem])
async def reorder(body: schemas.RotationOrder, rt: Rt) -> list[schemas.RotationItem]:
    try:
        return rt.reorder(body.order)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.get("/rotation/{instance_id}", response_model=schemas.RotationItem)
async def get_instance(instance_id: str, rt: Rt) -> schemas.RotationItem:
    try:
        return rt.rotation_item(instance_id)
    except KeyError:
        raise HTTPException(404, f"unknown instance {instance_id!r}") from None


@router.patch("/rotation/{instance_id}", response_model=schemas.RotationItem)
async def patch_instance(instance_id: str, body: schemas.RotationPatch, rt: Rt) -> schemas.RotationItem:
    try:
        return rt.patch_instance(instance_id, body)
    except KeyError:
        raise HTTPException(404, f"unknown instance {instance_id!r}") from None


@router.delete("/rotation/{instance_id}", status_code=204)
async def remove_instance(instance_id: str, rt: Rt) -> None:
    try:
        rt.remove_instance(instance_id)
    except KeyError:
        raise HTTPException(404, f"unknown instance {instance_id!r}") from None


@router.put(
    "/rotation/{instance_id}/settings",
    response_model=schemas.RotationItem,
    responses={422: {"model": schemas.ApiErrors}},
)
async def update_settings(instance_id: str, body: dict[str, Any], rt: Rt) -> schemas.RotationItem:
    try:
        return rt.update_instance_settings(instance_id, body)
    except KeyError:
        raise HTTPException(404, f"unknown instance {instance_id!r}") from None
    except ValidationError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content=to_api_errors(exc).model_dump())  # type: ignore[return-value]


@router.post("/rotation/{instance_id}/pin", status_code=204)
async def pin(instance_id: str, body: schemas.PinRequest, rt: Rt) -> None:
    try:
        rt.pin(instance_id, body.pinned)
    except KeyError:
        raise HTTPException(404, f"unknown instance {instance_id!r}") from None
