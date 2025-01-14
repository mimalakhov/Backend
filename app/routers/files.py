import pathlib
from uuid import UUID

from fastapi import APIRouter, Depends, Path, UploadFile, status
from fastapi.responses import FileResponse

from app.auth.oauth2 import member
from app.core.download import downloader
from app.core.exceptions import WorkplaceFileNotFoundException
from app.schemas.documents import UserAssignedWorkplace
from app.schemas.models import FileModelOut

router = APIRouter(tags=["Files"])


@router.post("/workplaces/{workplace_id}/file", status_code=status.HTTP_201_CREATED, response_model=FileModelOut)
async def add_file(
    file_to_upload: UploadFile,
    workplace_id: UUID = Path(...),
    user: UserAssignedWorkplace = Depends(member),
):
    filename: str = await downloader(file_to_upload, workplace_id)
    file_url = f"/workplaces/{workplace_id}/file/{filename}"
    return FileModelOut(url=file_url)


@router.get("/workplaces/{workplace_id}/file/{filename}", status_code=status.HTTP_200_OK, response_class=FileResponse)
async def get_file(
    workplace_id: UUID = Path(...), filename: str = Path(...), user: UserAssignedWorkplace = Depends(member)
):
    local_storage = pathlib.Path(__file__).parent.parent.parent.resolve()
    path_file = local_storage.joinpath(pathlib.Path(f"assets/{workplace_id}/{filename}"))
    if not pathlib.Path.is_file(path_file):
        raise WorkplaceFileNotFoundException("Файл не найден")
    return FileResponse(path_file)
