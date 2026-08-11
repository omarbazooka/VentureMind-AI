from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class Intent(StrEnum):
    NEW_IDEA = "NEW_IDEA"
    ANSWER_CLARIFICATION = "ANSWER_CLARIFICATION"
    UPLOAD_FILE = "UPLOAD_FILE"
    START_ANALYSIS = "START_ANALYSIS"
    ASK_REPORT_QUESTION = "ASK_REPORT_QUESTION"
    EXPLAIN_REPORT_SELECTION = "EXPLAIN_REPORT_SELECTION"
    SHOW_EVIDENCE = "SHOW_EVIDENCE"
    SHOW_SOURCES = "SHOW_SOURCES"
    EXPLAIN_CALCULATION = "EXPLAIN_CALCULATION"
    CHALLENGE_CONCLUSION = "CHALLENGE_CONCLUSION"
    CHANGE_ASSUMPTION = "CHANGE_ASSUMPTION"
    RUN_SCENARIO = "RUN_SCENARIO"
    REANALYZE = "REANALYZE"
    GENERAL_CHAT = "GENERAL_CHAT"


class ExecutionMode(StrEnum):
    SINGLE = "SINGLE"
    PARALLEL = "PARALLEL"
    SEQUENTIAL = "SEQUENTIAL"
    HYBRID = "HYBRID"


class SubRequest(BaseModel):
    id: str = Field(
        min_length=1,
        max_length=50,
    )

    intent: Intent

    payload: dict[str, Any] = Field(
        default_factory=dict,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    depends_on: list[str] = Field(
        default_factory=list,
    )


class TurnUnderstanding(BaseModel):
    sub_requests: list[SubRequest] = Field(
        min_length=1,
        max_length=5, # can change this in future
    )

    execution_mode: ExecutionMode

    overall_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    clarification_needed: bool

    @model_validator(mode="after")
    def validate_turn_structure(self) -> Self:
        request_ids = [
            request.id
            for request in self.sub_requests
        ]
        # delete any duplicate
        if len(request_ids) != len(set(request_ids)):
            raise ValueError(
                "SubRequest ids must be unique"
            )

        known_ids = set(request_ids)

        # cannot depend on itself
        for request in self.sub_requests:
            if request.id in request.depends_on:
                raise ValueError(
                    f"{request.id} cannot depend on itself"
                )

            unknown_dependencies = (
                set(request.depends_on) - known_ids
            )

            if unknown_dependencies:
                raise ValueError(
                    f"{request.id} has unknown dependencies: "
                    f"{sorted(unknown_dependencies)}"
                )
        # Single have many requests not 1
        if (
            self.execution_mode == ExecutionMode.SINGLE
            and len(self.sub_requests) != 1
        ):
            raise ValueError(
                "SINGLE execution requires exactly one SubRequest"
            )
        # if parallel you donn't need the depends on
        if (
            self.execution_mode == ExecutionMode.PARALLEL
            and any(
                request.depends_on
                for request in self.sub_requests
            )
        ):
            raise ValueError(
                "PARALLEL SubRequests cannot have dependencies"
            )

        return self