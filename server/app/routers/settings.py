from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.deps import DbSession, SettingsDep, require_token
from app.schemas import SettingsModel
from app.settings_store import read_max_versions, write_max_versions

log = logging.getLogger("savesync.settings")

router = APIRouter(dependencies=[Depends(require_token)])


@router.get("/settings", response_model=SettingsModel)
def get_server_settings(db: DbSession, settings: SettingsDep) -> SettingsModel:
    return SettingsModel(max_versions=read_max_versions(db, settings.default_max_versions))


@router.put("/settings", response_model=SettingsModel)
def put_server_settings(body: SettingsModel, db: DbSession) -> SettingsModel:
    write_max_versions(db, body.max_versions)
    log.info("max_versions set to %d", body.max_versions)
    return body
