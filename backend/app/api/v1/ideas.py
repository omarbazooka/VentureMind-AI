from uuid import uuid4
from fastapi import APIRouter, status
from app.schemas.idea import IdeaCreate, IdeaResponse

router = APIRouter(prefix= "/ideas", tags=["ideas"])

@router.post(
    "",
    response_model=IdeaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ideas(payload: IdeaCreate) -> IdeaResponse:
    return IdeaResponse(
        id= uuid4(),
        title= payload.title,
        description= payload.description
    )