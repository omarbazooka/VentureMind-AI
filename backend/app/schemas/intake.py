from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class IntakeProvenance(StrEnum):
    USER = "USER"
    AI_ASSUMPTION = "AI_ASSUMPTION"


class ProfileValueKind(StrEnum):
    FACT = "FACT"
    ASSUMPTION = "ASSUMPTION"


class ProfileField(StrEnum):
    IDEA_NAME = "idea_name"
    IDEA_DESCRIPTION = "idea_description"
    PROBLEM = "problem"
    PROPOSED_SOLUTION = "proposed_solution"
    INDUSTRY = "industry"
    BUSINESS_TYPE = "business_type"
    TARGET_CUSTOMERS = "target_customers"
    CUSTOMER_TYPE = "customer_type"
    TARGET_COUNTRY = "target_country"
    TARGET_CITY = "target_city"
    BUDGET = "budget"
    CURRENCY = "currency"
    REVENUE_MODEL = "revenue_model"
    FOUNDER_EXPERIENCE = "founder_experience"
    EXISTING_TEAM = "existing_team"
    LAUNCH_TIMELINE = "launch_timeline"
    KNOWN_COMPETITORS = "known_competitors"
    CURRENT_STAGE = "current_stage"
    USER_GOAL = "user_goal"


class ProfileFieldMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provenance: IntakeProvenance
    value_kind: ProfileValueKind
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    source_message_id: UUID | None = None


ProfileValue = (
    str
    | int
    | float
    | bool
    | list[str]
)


class ProfileFieldUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: ProfileField
    value: ProfileValue
    provenance: IntakeProvenance
    value_kind: ProfileValueKind = ProfileValueKind.FACT
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class ProfileConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: ProfileField
    current_value: Any
    proposed_value: ProfileValue


class ProfileMergePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted_updates: list[ProfileFieldUpdate] = Field(
        default_factory=list,
    )
    conflicts: list[ProfileConflict] = Field(
        default_factory=list,
    )
    unchanged_fields: list[ProfileField] = Field(
        default_factory=list,
    )
    candidate_profile_data: dict[str, Any]


class IntakeExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updates: list[ProfileFieldUpdate] = Field(
        default_factory=list,
        max_length=20,
    )
    unknown_fields: list[ProfileField] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_extraction(self) -> "IntakeExtraction":
        updated_fields = [
            update.field
            for update in self.updates
        ]

        if len(updated_fields) != len(set(updated_fields)):
            raise ValueError(
                "Each profile field can only be "
                "updated once per extraction"
            )

        overlap = (
            set(updated_fields)
            & set(self.unknown_fields)
        )

        if overlap:
            names = sorted(
                field.value
                for field in overlap
            )
            raise ValueError(
                "A field cannot be both updated "
                f"and unknown: {names}"
            )

        return self


class ProfileReadinessStatus(StrEnum):
    NOT_READY = "NOT_READY"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"


class ProfileReadinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness: ProfileReadinessStatus
    missing_critical_fields: list[ProfileField] = Field(
        default_factory=list,
    )
    missing_optional_fields: list[ProfileField] = Field(
        default_factory=list,
    )
    unknown_critical_fields: list[ProfileField] = Field(
        default_factory=list,
    )


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: ProfileField

    question: str = Field(
        min_length=1,
    )

    is_assumption_prompt: bool = False
