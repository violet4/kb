"""Small standalone-config endpoints -- currently just display_name, the sender
name Channel/Agent chat views attach to outgoing messages (see
frontend/src/shared/useDisplayName.ts). Extend as more of Settings gains a UI
control; follow the get/patch shape below rather than a new router per field."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_session
from models import Settings

router = APIRouter(prefix="/settings")


class SettingsOut(BaseModel):
    display_name: Optional[str]


class SettingsPatch(BaseModel):
    display_name: Optional[str] = None


@router.get("", response_model=SettingsOut)
def get_settings(session: Session = Depends(get_session)) -> SettingsOut:
    settings = Settings.get(session)
    return SettingsOut(display_name=settings.display_name)


@router.patch("", response_model=SettingsOut)
def patch_settings(patch: SettingsPatch, session: Session = Depends(get_session)) -> SettingsOut:
    settings = Settings.get(session)
    if patch.display_name is not None:
        settings.display_name = patch.display_name or None
    session.commit()
    return SettingsOut(display_name=settings.display_name)
