from uuid import UUID, uuid4

from app.chat.context import (
    WorkingContext,
    WorkingMessage,
)
from app.chat.intake_handler import (
    IntakeHandler,
)
from app.models.idea_profile import (
    IdeaProfile,
)
from app.schemas.intake import (
    ClarificationDraft,
    IntakeExtraction,
    IntakeHandlerStatus,
    IntakeProvenance,
    ProfileField,
    ProfileFieldUpdate,
    ProfileValueKind,
)
from app.services.intake_clarification import (
    IntakeClarificationService,
)
from app.services.intake_extraction import (
    IntakeExtractionService,
)


class QueueGateway:
    def __init__(
        self,
        outputs: list,
    ) -> None:
        self.outputs = list(
            outputs
        )
        self.calls = []

    def generate_structured(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        if not self.outputs:
            raise AssertionError(
                "Fake gateway received more "
                "calls than expected"
            )

        return self.outputs.pop(0)


class StatefulFakeDb:
    def __init__(
        self,
        profile: IdeaProfile,
    ) -> None:
        self.current_profile = profile
        self.added_profiles = []
        self.flush_count = 0

    def scalar(
        self,
        statement,
    ):
        return self.current_profile

    def add(
        self,
        value,
    ) -> None:
        self.added_profiles.append(
            value
        )

        self.current_profile = value

    def flush(
        self,
    ) -> None:
        self.flush_count += 1


def make_update(
    *,
    field: ProfileField,
    value,
    value_kind: ProfileValueKind = (
        ProfileValueKind.FACT
    ),
) -> ProfileFieldUpdate:
    return ProfileFieldUpdate(
        field=field,
        value=value,
        provenance=(
            IntakeProvenance.USER
        ),
        value_kind=value_kind,
        confidence=0.95,
    )


def make_metadata(
    *,
    value_kind: ProfileValueKind = (
        ProfileValueKind.FACT
    ),
) -> dict:
    return {
        "provenance": (
            IntakeProvenance.USER.value
        ),
        "value_kind": (
            value_kind.value
        ),
        "confidence": 1.0,
        "source_message_id": None,
    }


def make_context(
    *,
    db: StatefulFakeDb,
    message: str,
    message_id: UUID,
    recent_messages: list[
        WorkingMessage
    ] | None = None,
) -> WorkingContext:
    profile = db.current_profile

    return WorkingContext(
        idea_id=profile.idea_id,
        idea_title="Gym platform",
        idea_state="DRAFT",
        current_user_message=message,
        current_message_id=message_id,
        profile_version=profile.version,
        profile_readiness=(
            profile.readiness
        ),
        profile_data=dict(
            profile.profile_data
        ),
        recent_messages=(
            recent_messages
            or []
        ),
    )


def test_vague_idea_progresses_to_ready_across_multiple_turns():
    idea_id = uuid4()

    initial_profile = IdeaProfile(
        idea_id=idea_id,
        version=1,
        readiness="NOT_READY",
        profile_data={},
        profile_metadata={},
        unknown_fields=[],
    )

    db = StatefulFakeDb(
        initial_profile
    )

    extraction_gateway = QueueGateway(
        outputs=[
            IntakeExtraction(
                updates=[
                    make_update(
                        field=(
                            ProfileField
                            .IDEA_DESCRIPTION
                        ),
                        value=(
                            "Gym management software"
                        ),
                    ),
                ],
            ),
            IntakeExtraction(
                updates=[
                    make_update(
                        field=(
                            ProfileField
                            .TARGET_CUSTOMERS
                        ),
                        value=(
                            "Independent gyms"
                        ),
                    ),
                ],
            ),
            IntakeExtraction(
                updates=[
                    make_update(
                        field=(
                            ProfileField
                            .TARGET_COUNTRY
                        ),
                        value="Egypt",
                    ),
                ],
            ),
        ],
    )

    clarification_gateway = QueueGateway(
        outputs=[
            ClarificationDraft(
                question=(
                    "مين أول نوع جيمات "
                    "عايز تستهدفه؟"
                ),
                suggested_options=[
                    "الجيمات المستقلة",
                    "سلاسل الجيمات",
                ],
            ),
            ClarificationDraft(
                question=(
                    "هتبدأ في أنهي دولة؟"
                ),
                suggested_options=[
                    "مصر",
                    "السعودية",
                ],
            ),
        ],
    )

    handler = IntakeHandler(
        extraction_service=(
            IntakeExtractionService(
                gateway=(
                    extraction_gateway
                ),
                model="test-model",
            )
        ),
        clarification_service=(
            IntakeClarificationService(
                gateway=(
                    clarification_gateway
                ),
                model="test-model",
            )
        ),
    )

    first_message_id = uuid4()

    first_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message=(
                "عايز أعمل software "
                "لإدارة الجيمات"
            ),
            message_id=(
                first_message_id
            ),
        ),
    )

    assert (
        first_result.status
        == (
            IntakeHandlerStatus
            .CLARIFICATION_REQUIRED
        )
    )

    assert (
        first_result.profile_version
        == 2
    )

    assert (
        first_result.clarification
        is not None
    )

    assert (
        first_result
        .clarification
        .field
        == (
            ProfileField
            .TARGET_CUSTOMERS
        )
    )

    assert (
        db.current_profile
        .profile_data[
            "idea_description"
        ]
        == "Gym management software"
    )

    second_message_id = uuid4()

    second_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message=(
                "الجيمات المستقلة"
            ),
            message_id=(
                second_message_id
            ),
            recent_messages=[
                WorkingMessage(
                    role="assistant",
                    content=(
                        first_result
                        .clarification
                        .question
                    ),
                ),
            ],
        ),
    )

    assert (
        second_result.status
        == (
            IntakeHandlerStatus
            .CLARIFICATION_REQUIRED
        )
    )

    assert (
        second_result.profile_version
        == 3
    )

    assert (
        second_result.clarification
        is not None
    )

    assert (
        second_result
        .clarification
        .field
        == (
            ProfileField
            .TARGET_COUNTRY
        )
    )

    assert (
        db.current_profile
        .profile_data[
            "target_customers"
        ]
        == "Independent gyms"
    )

    third_message_id = uuid4()

    third_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message="مصر",
            message_id=(
                third_message_id
            ),
            recent_messages=[
                WorkingMessage(
                    role="assistant",
                    content=(
                        second_result
                        .clarification
                        .question
                    ),
                ),
            ],
        ),
    )

    assert (
        third_result.status
        == (
            IntakeHandlerStatus
            .READY_FOR_ANALYSIS
        )
    )

    assert (
        third_result.profile_version
        == 4
    )

    assert (
        third_result.clarification
        is None
    )

    final_profile = (
        db.current_profile
    )

    assert (
        final_profile.readiness
        == "READY_FOR_ANALYSIS"
    )

    assert (
        final_profile.profile_data
        == {
            "idea_description": (
                "Gym management software"
            ),
            "target_customers": (
                "Independent gyms"
            ),
            "target_country": "Egypt",
        }
    )

    assert [
        profile.version
        for profile
        in db.added_profiles
    ] == [
        2,
        3,
        4,
    ]

    assert (
        final_profile
        .profile_metadata[
            "idea_description"
        ][
            "source_message_id"
        ]
        == str(first_message_id)
    )

    assert (
        final_profile
        .profile_metadata[
            "target_customers"
        ][
            "source_message_id"
        ]
        == str(second_message_id)
    )

    assert (
        final_profile
        .profile_metadata[
            "target_country"
        ][
            "source_message_id"
        ]
        == str(third_message_id)
    )

    assert (
        len(
            extraction_gateway.calls
        )
        == 3
    )

    assert (
        len(
            clarification_gateway.calls
        )
        == 2
    )


def test_unknown_field_then_user_assumption_can_reach_ready():
    idea_id = uuid4()

    initial_profile = IdeaProfile(
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
            "idea_description": (
                make_metadata()
            ),
            "target_country": (
                make_metadata()
            ),
        },
        unknown_fields=[],
    )

    db = StatefulFakeDb(
        initial_profile
    )

    extraction_gateway = QueueGateway(
        outputs=[
            IntakeExtraction(
                unknown_fields=[
                    ProfileField
                    .TARGET_CUSTOMERS
                ],
            ),
            IntakeExtraction(
                updates=[
                    make_update(
                        field=(
                            ProfileField
                            .TARGET_CUSTOMERS
                        ),
                        value=(
                            "Independent gyms"
                        ),
                        value_kind=(
                            ProfileValueKind
                            .ASSUMPTION
                        ),
                    ),
                ],
            ),
        ],
    )

    clarification_gateway = QueueGateway(
        outputs=[
            ClarificationDraft(
                question=(
                    "بما إن شريحة العملاء "
                    "لسه مش محسومة، تحب "
                    "نستخدم أي شريحة "
                    "كافتراض مبدئي؟"
                ),
                suggested_options=[
                    "الجيمات المستقلة",
                    "السلاسل الصغيرة",
                ],
            ),
        ],
    )

    handler = IntakeHandler(
        extraction_service=(
            IntakeExtractionService(
                gateway=(
                    extraction_gateway
                ),
                model="test-model",
            )
        ),
        clarification_service=(
            IntakeClarificationService(
                gateway=(
                    clarification_gateway
                ),
                model="test-model",
            )
        ),
    )

    unknown_message_id = uuid4()

    unknown_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message=(
                "لسه مش عارف "
                "العملاء بالظبط"
            ),
            message_id=(
                unknown_message_id
            ),
        ),
    )

    assert (
        unknown_result.status
        == (
            IntakeHandlerStatus
            .CLARIFICATION_REQUIRED
        )
    )

    assert (
        unknown_result.profile_version
        == 2
    )

    assert (
        "target_customers"
        in (
            db.current_profile
            .unknown_fields
        )
    )

    assert (
        unknown_result.clarification
        is not None
    )

    assert (
        unknown_result
        .clarification
        .field
        == (
            ProfileField
            .TARGET_CUSTOMERS
        )
    )

    assert (
        unknown_result
        .clarification
        .is_assumption_prompt
        is True
    )

    assumption_message_id = uuid4()

    assumption_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message=(
                "خلينا نفترض مؤقتًا "
                "الجيمات المستقلة"
            ),
            message_id=(
                assumption_message_id
            ),
            recent_messages=[
                WorkingMessage(
                    role="assistant",
                    content=(
                        unknown_result
                        .clarification
                        .question
                    ),
                ),
            ],
        ),
    )

    assert (
        assumption_result.status
        == (
            IntakeHandlerStatus
            .READY_FOR_ANALYSIS
        )
    )

    assert (
        assumption_result.profile_version
        == 3
    )

    final_profile = (
        db.current_profile
    )

    assert (
        final_profile.profile_data[
            "target_customers"
        ]
        == "Independent gyms"
    )

    assert (
        "target_customers"
        not in final_profile.unknown_fields
    )

    metadata = (
        final_profile
        .profile_metadata[
            "target_customers"
        ]
    )

    assert (
        metadata["provenance"]
        == IntakeProvenance.USER.value
    )

    assert (
        metadata["value_kind"]
        == (
            ProfileValueKind
            .ASSUMPTION
            .value
        )
    )

    assert (
        metadata[
            "source_message_id"
        ]
        == str(
            assumption_message_id
        )
    )


def test_conflict_during_conversation_does_not_partially_mutate_profile():
    idea_id = uuid4()

    initial_profile = IdeaProfile(
        idea_id=idea_id,
        version=1,
        readiness="NOT_READY",
        profile_data={},
        profile_metadata={},
        unknown_fields=[],
    )

    db = StatefulFakeDb(
        initial_profile
    )

    extraction_gateway = QueueGateway(
        outputs=[
            IntakeExtraction(
                updates=[
                    make_update(
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
            ),
            IntakeExtraction(
                updates=[
                    make_update(
                        field=(
                            ProfileField
                            .IDEA_DESCRIPTION
                        ),
                        value=(
                            "Restaurant delivery "
                            "platform"
                        ),
                    ),
                    make_update(
                        field=(
                            ProfileField
                            .TARGET_COUNTRY
                        ),
                        value="Egypt",
                    ),
                ],
            ),
        ],
    )

    clarification_gateway = QueueGateway(
        outputs=[
            ClarificationDraft(
                question=(
                    "مين أول شريحة "
                    "عملاء؟"
                ),
            ),
        ],
    )

    handler = IntakeHandler(
        extraction_service=(
            IntakeExtractionService(
                gateway=(
                    extraction_gateway
                ),
                model="test-model",
            )
        ),
        clarification_service=(
            IntakeClarificationService(
                gateway=(
                    clarification_gateway
                ),
                model="test-model",
            )
        ),
    )

    first_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message=(
                "عايز أعمل software "
                "لإدارة الجيمات"
            ),
            message_id=uuid4(),
        ),
    )

    assert (
        first_result.profile_version
        == 2
    )

    assert (
        db.current_profile
        .profile_data[
            "idea_description"
        ]
        == "Gym management software"
    )

    profile_before_conflict = (
        db.current_profile
    )

    added_count_before = len(
        db.added_profiles
    )

    conflict_result = handler.handle(
        db=db,
        context=make_context(
            db=db,
            message=(
                "غيرت الفكرة لمطاعم "
                "وهبدأ في مصر"
            ),
            message_id=uuid4(),
        ),
    )

    assert (
        conflict_result.status
        == (
            IntakeHandlerStatus
            .CONFLICT_REQUIRES_CONFIRMATION
        )
    )

    assert (
        conflict_result.profile_version
        == 2
    )

    assert len(
        conflict_result.conflicts
    ) == 1

    assert (
        conflict_result
        .conflicts[0]
        .field
        == (
            ProfileField
            .IDEA_DESCRIPTION
        )
    )

    assert (
        db.current_profile
        is profile_before_conflict
    )

    assert (
        len(
            db.added_profiles
        )
        == added_count_before
    )

    assert (
        db.current_profile
        .profile_data
        == {
            "idea_description": (
                "Gym management software"
            ),
        }
    )

    assert (
        "target_country"
        not in (
            db.current_profile
            .profile_data
        )
    )