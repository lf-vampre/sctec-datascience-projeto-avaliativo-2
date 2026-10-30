from unittest.mock import patch

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
    steps = PipelineOrchestrator(base_params).steps()
    by_id = {s.step_id: s for s in steps}

    assert len(steps) == 12
    assert steps[0].step_id == "cadastro.bronze"
    assert by_id["cadastro.silver"].depende_de == "cadastro.bronze"
    assert by_id["dims"].depende_de == "cadastro.silver"
    assert [s.camada for s in steps] == ["bronze"] * 4 + ["silver"] * 4 + ["gold"] * 4


def test_pode_executar_sem_prerequisito(base_params, tmp_path):
    orchestrator = PipelineOrchestrator(base_params)
    with patch("src.etl.pipeline.get_layer_path", return_value=tmp_path):
        pode, msg = orchestrator.pode_executar("cadastro.silver")
    assert not pode
    assert "rode antes" in msg.lower()


def test_pode_executar_com_prerequisito_na_sessao(base_params):
    orchestrator = PipelineOrchestrator(base_params)
    orchestrator.resultados["cadastro.bronze"] = StepResult(step_id="cadastro.bronze", ok=True)
    pode, _ = orchestrator.pode_executar("cadastro.silver")
    assert pode


def test_validar_params_sandbox_teto():
    params = PipelineParams(
        tickers=["PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3"],
        bacen_periodo=("2023-01-01", "2023-12-31"),
        b3_periodo=("2023-01-01", "2023-12-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )
    orchestrator = PipelineOrchestrator(params)
    with patch("src.etl.pipeline.settings.SANDBOX_MAX_TICKERS", 3, create=True):
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
    with patch.object(
        orchestrator, "_executar_passo_interno",
        return_value=StepResult(step_id="cadastro.bronze", ok=True),
    ):
        with patch("src.etl.pipeline.try_acquire", return_value=True):
            orchestrator.run_step("cadastro.bronze")
            st = orchestrator.estado()
            assert "cadastro.bronze" in st
            assert isinstance(st["cadastro.bronze"], dict)
            assert st["cadastro.bronze"]["ok"] is True