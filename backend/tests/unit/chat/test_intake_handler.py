from uuid import uuid4

from app.chat.context import WorkingContext
from app.chat.intake_handler import IntakeHandler
from app.models.idea_profile import IdeaProfile
from app.schemas.intake import (
    ClarificationQuestion,
    IntakeExtraction,
    IntakeHandlerStatus,
    IntakeProvenance,
    ProfileField,
    ProfileFieldUpdate,
)


class FakeDb:
    def __init__(
        self,
        profile: IdeaProfile,
    ) -> None:
        self.profile = profile
        self.added = []
        self.flush_count = 0

    def scalar(
        self,
        statement,
    ):
        return self.profile

    def add(
        self,
        value,
    ) -> None:
        self.added.append(
            value
        )

    def flush(
        self,
    ) -> None:
        self.flush_count += 1


class FakeExtractionService:
    def __init__(
        self,
        extraction: IntakeExtraction,
    ) -> None:
        self.extraction = extraction
        self.calls = []

    def extract(
        self,
        context,
    ):
        self.calls.append(
            context
        )

        return self.extraction


class FakeClarificationService:
    def __init__(self) -> None:
        self.calls = []

    def compose(
        self,
        **kwargs,
    ) -> ClarificationQuestion:
        self.calls.append(
            kwargs
        )

        target = kwargs[
            "target"
        ]

        return ClarificationQuestion(
            field=target.field,
            question=(
                "What should we clarify next?"
            ),
            suggested_options=[],
            is_assumption_prompt=(
                target
                .is_assumption_prompt
            ),
        )


def make_context(
    idea_id,
    *,
    message: str = (
        "I want to build gym "
        "management software"
    ),
) -> WorkingContext:
    return WorkingContext(
        idea_id=idea_id,
        idea_title="Gym platform",
        idea_state="DRAFT",
        current_user_message=message,
        current_message_id=uuid4(),
        profile_version=1,
        profile_readiness="NOT_READY",
        profile_data={},
        recent_messages=[],
    )


def make_user_update(
    *,
    field: ProfileField,
    value,
) -> ProfileFieldUpdate:
    return ProfileFieldUpdate(
        field=field,
        value=value,
        provenance=(
            IntakeProvenance.USER
        ),
        confidence=0.95,
    )


def test_handler_persists_update_then_asks_next_clarification():
    idea_id = uuid4()

    current_profile = IdeaProfile(
        idea_id=idea_id,
        version=1,
        readiness="NOT_READY",
        profile_data={},
        profile_metadata={},
        unknown_fields=[],
    )

    extraction_service = (
        FakeExtractionService(
            IntakeExtraction(
                updates=[
                    make_user_update(
                        field=(
                            ProfileField
                            .IDEA_DESCRIPTION
                        ),
                        value=(
                            "Gym management "
                            "software"
                        ),
                    ),
                ],
            )
        )
    )

    clarification_service = (
        FakeClarificationService()
    )

    db = FakeDb(
        current_profile
    )

    handler = IntakeHandler(
        extraction_service=(
            extraction_service
        ),
        clarification_service=(
            clarification_service
        ),
    )

    result = handler.handle(
        db=db,
        context=make_context(
            idea_id
        ),
    )

    assert (
        result.status
        == (
            IntakeHandlerStatus
            .CLARIFICATION_REQUIRED
        )
    )

    assert result.profile_version == 2

    assert (
        result.clarification
        is not None
    )

    assert (
        result.clarification.field
        == (
            ProfileField
            .TARGET_CUSTOMERS
        )
    )

    assert len(
        extraction_service.calls
    ) == 1

    assert len(
        clarification_service.calls
    ) == 1

    assert len(
        db.added
    ) == 1

    new_profile = db.added[0]

    assert (
        new_profile.profile_data[
            "idea_description"
        ]
        == "Gym management software"
    )

    assert new_profile.version == 2


def test_handler_returns_ready_when_minimum_profile_is_complete():
    idea_id = uuid4()

    current_profile = IdeaProfile(
        idea_id=idea_id,
        version=1,
        readiness="NOT_READY",
        profile_data={},
        profile_metadata={},
        unknown_fields=[],
    )

    extraction_service = (
        FakeExtractionService(
            IntakeExtraction(
                updates=[
                    make_user_update(
                        field=(
                            ProfileField
                            .IDEA_DESCRIPTION
                        ),
                        value=(
                            "Gym management SaaS"
                        ),
                    ),
                    make_user_update(
                        field=(
                            ProfileField
                            .TARGET_CUSTOMERS
                        ),
                        value=(
                            "Independent gyms"
                        ),
                    ),
                    make_user_update(
                        field=(
                            ProfileField
                            .TARGET_COUNTRY
                        ),
                        value="Egypt",
                    ),
                ],
            )
        )
    )

    clarification_service = (
        FakeClarificationService()
    )

    db = FakeDb(
        current_profile
    )

    handler = IntakeHandler(
        extraction_service=(
            extraction_service
        ),
        clarification_service=(
            clarification_service
        ),
    )

    result = handler.handle(
        db=db,
        context=make_context(
            idea_id
        ),
    )

    assert (
        result.status
        == (
            IntakeHandlerStatus
            .READY_FOR_ANALYSIS
        )
    )

    assert result.profile_version == 2

    assert result.clarification is None

    assert (
        clarification_service.calls
        == []
    )

    assert len(
        db.added
    ) == 1

    new_profile = db.added[0]

    assert (
        new_profile.readiness
        == "READY_FOR_ANALYSIS"
    )


def test_handler_does_not_persist_conflicting_update():
    idea_id = uuid4()

    current_profile = IdeaProfile(
        idea_id=idea_id,
        version=1,
        readiness="NOT_READY",
        profile_data={
            "target_country": "Egypt",
        },
        profile_metadata={
            "target_country": {
                "provenance": "USER",
                "value_kind": "FACT",
                "confidence": 1.0,
                "source_message_id": None,
            },
        },
        unknown_fields=[],
    )

    extraction_service = (
        FakeExtractionService(
            IntakeExtraction(
                updates=[
                    make_user_update(
                        field=(
                            ProfileField
                            .TARGET_COUNTRY
                        ),
                        value="Saudi Arabia",
                    ),
                ],
            )
        )
    )

    clarification_service = (
        FakeClarificationService()
    )

    db = FakeDb(
        current_profile
    )

    handler = IntakeHandler(
        extraction_service=(
            extraction_service
        ),
        clarification_service=(
            clarification_service
        ),
    )

    result = handler.handle(
        db=db,
        context=make_context(
            idea_id,
            message=(
                "Actually I want to "
                "target Saudi Arabia"
            ),
        ),
    )

    assert (
        result.status
        == (
            IntakeHandlerStatus
            .CONFLICT_REQUIRES_CONFIRMATION
        )
    )

    assert result.profile_version == 1

    assert len(
        result.conflicts
    ) == 1

    assert (
        result.conflicts[0].field
        == (
            ProfileField
            .TARGET_COUNTRY
        )
    )

    assert (
        result.conflicts[0]
        .current_value
        == "Egypt"
    )

    assert (
        result.conflicts[0]
        .proposed_value
        == "Saudi Arabia"
    )

    assert db.added == []

    assert (
        clarification_service.calls
        == []
    )


def test_handler_persists_unknown_field_and_offers_assumption():
    idea_id = uuid4()

    current_profile = IdeaProfile(
        idea_id=idea_id,
        version=1,
        readiness="NOT_READY",
        profile_data={
            "idea_description": (
                "Gym management software"
            ),
            "target_country": "Egypt",
        },
        profile_metadata={
            "idea_description": {
                "provenance": "USER",
                "value_kind": "FACT",
                "confidence": 1.0,
                "source_message_id": None,
            },
            "target_country": {
                "provenance": "USER",
                "value_kind": "FACT",
                "confidence": 1.0,
                "source_message_id": None,
            },
        },
        unknown_fields=[],
    )

    extraction_service = (
        FakeExtractionService(
            IntakeExtraction(
                unknown_fields=[
                    ProfileField
                    .TARGET_CUSTOMERS
                ],
            )
        )
    )

    clarification_service = (
        FakeClarificationService()
    )

    db = FakeDb(
        current_profile
    )

    handler = IntakeHandler(
        extraction_service=(
            extraction_service
        ),
        clarification_service=(
            clarification_service
        ),
    )

    result = handler.handle(
        db=db,
        context=make_context(
            idea_id,
            message=(
                "I don't know the "
                "customers yet"
            ),
        ),
    )

    assert (
        result.status
        == (
            IntakeHandlerStatus
            .CLARIFICATION_REQUIRED
        )
    )

    assert result.profile_version == 2

    assert (
        result.clarification
        is not None
    )

    assert (
        result.clarification.field
        == (
            ProfileField
            .TARGET_CUSTOMERS
        )
    )

    assert (
        result.clarification
        .is_assumption_prompt
        is True
    )

    assert len(
        db.added
    ) == 1

    new_profile = db.added[0]

    assert (
        "target_customers"
        in new_profile.unknown_fields
    )


def test_handler_answer_to_unknown_field_removes_unknown_marker():
    idea_id = uuid4()

    current_profile = IdeaProfile(
        idea_id=idea_id,
        version=2,
        readiness="NOT_READY",
        profile_data={
            "idea_description": (
                "Gym management software"
            ),
            "target_country": "Egypt",
        },
        profile_metadata={
            "idea_description": {
                "provenance": "USER",
                "value_kind": "FACT",
                "confidence": 1.0,
                "source_message_id": None,
            },
            "target_country": {
                "provenance": "USER",
                "value_kind": "FACT",
                "confidence": 1.0,
                "source_message_id": None,
            },
        },
        unknown_fields=[
            "target_customers",
        ],
    )

    extraction_service = (
        FakeExtractionService(
            IntakeExtraction(
                updates=[
                    make_user_update(
                        field=(
                            ProfileField
                            .TARGET_CUSTOMERS
                        ),
                        value=(
                            "Independent gyms"
                        ),
                    ),
                ],
            )
        )
    )

    clarification_service = (
        FakeClarificationService()
    )

    db = FakeDb(
        current_profile
    )

    handler = IntakeHandler(
        extraction_service=(
            extraction_service
        ),
        clarification_service=(
            clarification_service
        ),
    )

    result = handler.handle(
        db=db,
        context=make_context(
            idea_id,
            message=(
                "Let's assume "
                "independent gyms"
            ),
        ),
    )

    assert (
        result.status
        == (
            IntakeHandlerStatus
            .READY_FOR_ANALYSIS
        )
    )

    assert result.profile_version == 3

    new_profile = db.added[0]

    assert (
        new_profile.profile_data[
            "target_customers"
        ]
        == "Independent gyms"
    )

    assert (
        "target_customers"
        not in new_profile.unknown_fields
    )