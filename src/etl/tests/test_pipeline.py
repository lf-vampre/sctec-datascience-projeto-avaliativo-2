from unittest.mock import MagicMock, patch
import pytest

from src.etl.pipeline import PipelineOrchestrator, autorizar
from src.models.contracts import PipelineParams, StepResult


@pytest.fixture
def base_params():
    return PipelineParams(
        tickers=["PETR4", "VALE3"],
        bacen_periodo=("2023-01-01", "2023-12-31"),
        b3_periodo=("2023-01-01", "2023-12-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )


def test_autorizar():
    assert autorizar("secret123", "secret123") == "producao"
    assert autorizar("wrong", "secret123") == "sandbox"
    assert autorizar(None, "secret123") == "sandbox"
    assert autorizar("secret123", None) == "sandbox"


def test_steps_order_and_dependencies(base_params):
    orchestrator = PipelineOrchestrator(base_params)
    steps = orchestrator.steps()

    assert len(steps) == 12
    assert steps[0].step_id == "cadastro.bronze"
    assert steps[1].depende_de == "cadastro.bronze"
    assert steps[2].step_id == "dims"
    assert steps[2].depende_de == "cadastro.silver"


def test_pode_executar_sem_prerequisito(base_params):
    orchestrator = PipelineOrchestrator(base_params)
    pode, msg = orchestrator.pode_executar("cadastro.silver")
    assert not pode
    assert "rode antes" in msg.lower()


def test_validar_params_sandbox_teto(base_params):
    params = PipelineParams(
        tickers=["PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3"],
        bacen_periodo=("2023-01-01", "2023-12-31"),
        b3_periodo=("2023-01-01", "2023-12-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )
    orchestrator = PipelineOrchestrator(params)
    with patch("src.etl.pipeline.settings.SANDBOX_MAX_TICKERS", 3):
        with pytest.raises(ValueError, match="sandbox aceita no máximo"):
            orchestrator.validar_params(params)


def test_run_step_lock_release_on_exception(base_params):
    orchestrator = PipelineOrchestrator(base_params)

    with patch.object(orchestrator, "_executar_passo_interno", side_effect=RuntimeError("Erro simulado")):
        with patch("src.etl.pipeline.try_acquire", return_value=True):
            with patch("src.etl.pipeline.release_lock") as mock_liberar:
                res = orchestrator.run_step("cadastro.bronze")
                assert not res.ok
                assert "Erro simulado" in res.error
                assert mock_liberar.called


def test_estado_serializavel(base_params):
    orchestrator = PipelineOrchestrator(base_params)
    with patch.object(orchestrator, "_executar_passo_interno", return_value=StepResult(step_id="cadastro.bronze", ok=True)):
        with patch("src.etl.pipeline.try_acquire", return_value=True):
            orchestrator.run_step("cadastro.bronze")
            st = orchestrator.estado()
            assert "cadastro.bronze" in st
            assert isinstance(st["cadastro.bronze"], dict)
            assert st["cadastro.bronze"]["ok"] is True