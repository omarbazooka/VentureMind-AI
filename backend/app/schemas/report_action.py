from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ReportActionType(StrEnum):
    EXPLAIN = "EXPLAIN"
    EXPLAIN_SIMPLY = "EXPLAIN_SIMPLY"
    SHOW_EVIDENCE = "SHOW_EVIDENCE"
    SHOW_SOURCES = "SHOW_SOURCES"
    EXPLAIN_CALCULATION = "EXPLAIN_CALCULATION"
    EXPLAIN_CHART = "EXPLAIN_CHART"
    CHALLENGE_CONCLUSION = "CHALLENGE_CONCLUSION"
    WHAT_COULD_CHANGE = "WHAT_COULD_CHANGE"
    ASK_VENTUREMIND = "ASK_VENTUREMIND"


class ReportActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReportActionType
    target_section: str | None = None
    target_metric: str | None = None
    question: str | None = None


class ReportActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReportActionType
    title: str
    content: str
    grounding_references: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
