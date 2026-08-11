from pydantic import BaseModel

from app.chat.context import WorkingContext
from app.schemas.turn import Intent, SubRequest


class HandlerResult(BaseModel):
    response_text: str


def handle_general_chat(
    request: SubRequest,
    context: WorkingContext,
) -> HandlerResult:
    if request.intent != Intent.GENERAL_CHAT:
        raise ValueError(
            "General chat handler received unsupported intent"
        )

    return HandlerResult(
        response_text=(
            f"Hi! I’m ready to help with "
            f"{context.idea_title}."
        )
    )