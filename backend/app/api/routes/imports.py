from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.ingestion.client import CricClubsClient
from app.ingestion.service import CricClubsImportService
from app.models.schemas import CricClubsImportRequest, ImportResultRead

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/cricclubs", response_model=ImportResultRead)
async def import_cricclubs_scorecards(
    request: CricClubsImportRequest,
    session: Session = Depends(get_session),
):
    settings = get_settings()
    client = CricClubsClient(user_agent=settings.cricclubs_user_agent)
    return await CricClubsImportService(session, client).import_scorecards(request)

