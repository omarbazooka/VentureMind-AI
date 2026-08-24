from typing import Any

from crewai.llms.base_llm import (
    BaseLLM,
)
from pydantic import (
    BaseModel,
    PrivateAttr,
)

from app.llm.gateway import (
    LLMGateway,
)


class CrewAILLMAdapterError(
    RuntimeError
):
    pass


class CrewAIToolUseNotSupportedError(
    CrewAILLMAdapterError
):
    pass


class CrewAILLMGatewayAdapter(
    BaseLLM
):
    _gateway: LLMGateway = PrivateAttr()

    def __init__(
        self,
        *,
        gateway: LLMGateway,
        model: str,
    ) -> None:
        super().__init__(
            model=model,
            provider="venturemind",
        )

        self._gateway = gateway

    def _normalize_messages(
        self,
        messages: (
            str
            | list[dict[str, Any]]
        ),
    ) -> tuple[str, str]:
        if isinstance(messages, str):
            if not messages.strip():
                raise CrewAILLMAdapterError(
                    "CrewAI sent an empty message"
                )

            return "", messages

        system_parts: list[str] = []
        conversation_parts: list[str] = []

        for message in messages:
            role = message.get(
                "role",
                "user",
            )

            content = message.get(
                "content",
                "",
            )

            if not isinstance(content, str):
                content = str(content)

            if not content.strip():
                continue

            if role == "system":
                system_parts.append(
                    content
                )

                continue

            conversation_parts.append(
                f"{str(role).upper()}:\n"
                f"{content}"
            )

        user_prompt = "\n\n".join(
            conversation_parts
        )

        if not user_prompt.strip():
            raise CrewAILLMAdapterError(
                "CrewAI messages contain "
                "no executable conversation"
            )

        system_prompt = "\n\n".join(
            system_parts
        )

        return (
            system_prompt,
            user_prompt,
        )

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ) -> str:
        if tools or available_functions:
            raise (
                CrewAIToolUseNotSupportedError(
                    "CrewAI tool calling is not "
                    "enabled through the "
                    "VentureMind LLM adapter yet"
                )
            )

        (
            system_prompt,
            user_prompt,
        ) = self._normalize_messages(
            messages
        )

        if response_model is not None:
            if not issubclass(
                response_model,
                BaseModel,
            ):
                raise CrewAILLMAdapterError(
                    "CrewAI response model must "
                    "be a Pydantic BaseModel"
                )

            structured_result = (
                self._gateway
                .generate_structured(
                    model=self.model,
                    system_prompt=(
                        system_prompt
                    ),
                    user_prompt=user_prompt,
                    response_model=(
                        response_model
                    ),
                )
            )

            return (
                structured_result
                .model_dump_json()
            )

        output_text = (
            self._gateway
            .generate_text(
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        )

        return self._apply_stop_words(
            output_text
        )