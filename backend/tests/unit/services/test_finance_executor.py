from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.finance_executor as executor
from app.schemas.finance import (
    FinanceReadinessResult,
    FinanceReadinessStatus,
    FinancialInputName,
    FinancialScenarioKind,
)
from app.schemas.finance_runtime import (
    FinanceExecutionStatus,
    FinanceInputRequest,
)
from app.services.finance_executor import (
    FinanceExecutionError,
)


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def commit(self) -> None:
        self.commit_count += 1


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


def _claim():
    return SimpleNamespace(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        assumption_context=object(),
    )


def _ready(
    scenario: FinancialScenarioKind,
) -> FinanceReadinessResult:
    return FinanceReadinessResult(
        scenario=scenario,
        status=(
            FinanceReadinessStatus
            .READY_FOR_CALCULATION
        ),
        can_calculate_core=True,
    )


def _missing_price(
    scenario: FinancialScenarioKind,
) -> FinanceReadinessResult:
    return FinanceReadinessResult(
        scenario=scenario,
        status=(
            FinanceReadinessStatus
            .MISSING_CRITICAL_INPUTS
        ),
        can_calculate_core=False,
        missing_critical_inputs=[
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ],
    )


def _patch_common(
    monkeypatch,
    *,
    claim,
    inputs,
):
    monkeypatch.setattr(
        executor,
        "claim_finance_stage",
        Mock(return_value=claim),
    )
    monkeypatch.setattr(
        executor,
        "finalize_financial_assumptions",
        Mock(return_value=inputs),
    )
    monkeypatch.setattr(
        executor,
        "load_answered_finance_inputs",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(
        executor,
        "apply_answered_finance_inputs",
        Mock(return_value=inputs),
    )


def test_executor_pauses_for_missing_base_input(
    monkeypatch,
):
    claim = _claim()
    inputs = SimpleNamespace(
        base=object(),
        upside=object(),
        downside=object(),
    )
    _patch_common(
        monkeypatch,
        claim=claim,
        inputs=inputs,
    )

    monkeypatch.setattr(
        executor,
        "_evaluate_readiness",
        Mock(
            return_value=(
                _missing_price(
                    FinancialScenarioKind.BASE
                ),
                _ready(
                    FinancialScenarioKind.UPSIDE
                ),
                _ready(
                    FinancialScenarioKind.DOWNSIDE
                ),
            )
        ),
    )

    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question="Which price should we model?",
    )
    monkeypatch.setattr(
        executor,
        "build_finance_input_request",
        Mock(return_value=request),
    )

    run_input_id = uuid4()
    pause_mock = Mock(
        return_value=SimpleNamespace(
            id=run_input_id
        )
    )
    monkeypatch.setattr(
        executor,
        "pause_finance_for_user_input",
        pause_mock,
    )

    calculate_mock = Mock()
    complete_mock = Mock()
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "calculate_financial_scenarios",
        calculate_mock,
    )
    monkeypatch.setattr(
        executor,
        "complete_finance_stage",
        complete_mock,
    )
    monkeypatch.setattr(
        executor,
        "fail_finance_stage",
        fail_mock,
    )

    session_factory = FakeSessionFactory()
    assumption_runner = Mock(
        return_value=object()
    )

    outcome = executor.execute_finance_stage(
        session_factory=session_factory,
        stage_run_id=claim.stage_run_id,
        assumption_runner=assumption_runner,
    )

    assert (
        outcome.status
        == FinanceExecutionStatus.PAUSED_FOR_USER
    )
    assert outcome.run_input_id == run_input_id
    assert outcome.request == request
    pause_mock.assert_called_once()
    calculate_mock.assert_not_called()
    complete_mock.assert_not_called()
    fail_mock.assert_not_called()
    assert len(session_factory.sessions) == 3
    assert session_factory.sessions[0].commit_count == 1
    assert session_factory.sessions[1].commit_count == 0
    assert session_factory.sessions[2].commit_count == 1


def test_executor_calculates_and_completes_ready_finance(
    monkeypatch,
):
    claim = _claim()
    inputs = SimpleNamespace(
        base=object(),
        upside=object(),
        downside=object(),
    )
    _patch_common(
        monkeypatch,
        claim=claim,
        inputs=inputs,
    )

    monkeypatch.setattr(
        executor,
        "_evaluate_readiness",
        Mock(
            return_value=(
                _ready(FinancialScenarioKind.BASE),
                _ready(FinancialScenarioKind.UPSIDE),
                _ready(FinancialScenarioKind.DOWNSIDE),
            )
        ),
    )

    result_bundle = object()
    monkeypatch.setattr(
        executor,
        "calculate_financial_scenarios",
        Mock(return_value=result_bundle),
    )

    result_id = uuid4()
    complete_mock = Mock(
        return_value=SimpleNamespace(
            id=result_id
        )
    )
    monkeypatch.setattr(
        executor,
        "complete_finance_stage",
        complete_mock,
    )
    pause_mock = Mock()
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "pause_finance_for_user_input",
        pause_mock,
    )
    monkeypatch.setattr(
        executor,
        "fail_finance_stage",
        fail_mock,
    )

    session_factory = FakeSessionFactory()

    outcome = executor.execute_finance_stage(
        session_factory=session_factory,
        stage_run_id=claim.stage_run_id,
        assumption_runner=Mock(
            return_value=object()
        ),
    )

    assert (
        outcome.status
        == FinanceExecutionStatus.COMPLETED
    )
    assert outcome.result_id == result_id
    complete_mock.assert_called_once()
    pause_mock.assert_not_called()
    fail_mock.assert_not_called()
    assert len(session_factory.sessions) == 3
    assert session_factory.sessions[2].commit_count == 1


def test_executor_does_not_ask_user_for_secondary_scenario_gap(
    monkeypatch,
):
    claim = _claim()
    inputs = SimpleNamespace(
        base=object(),
        upside=object(),
        downside=object(),
    )
    _patch_common(
        monkeypatch,
        claim=claim,
        inputs=inputs,
    )

    monkeypatch.setattr(
        executor,
        "_evaluate_readiness",
        Mock(
            return_value=(
                _ready(FinancialScenarioKind.BASE),
                _missing_price(
                    FinancialScenarioKind.UPSIDE
                ),
                _ready(
                    FinancialScenarioKind.DOWNSIDE
                ),
            )
        ),
    )

    pause_mock = Mock()
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "pause_finance_for_user_input",
        pause_mock,
    )
    monkeypatch.setattr(
        executor,
        "fail_finance_stage",
        fail_mock,
    )

    session_factory = FakeSessionFactory()

    with pytest.raises(FinanceExecutionError):
        executor.execute_finance_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            assumption_runner=Mock(
                return_value=object()
            ),
        )

    pause_mock.assert_not_called()
    fail_mock.assert_called_once()
    assert (
        fail_mock.call_args.kwargs["error_code"]
        == "INCOMPLETE_FINANCE_SCENARIOS"
    )
