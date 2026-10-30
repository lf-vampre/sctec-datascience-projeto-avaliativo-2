"""Testes AppTest do painel de execução contínua do DataOps."""

from streamlit.testing.v1 import AppTest


def _app(fail_step=None):
    from dataclasses import asdict
    from unittest.mock import MagicMock

    import streamlit as st

    from src.models.contracts import PipelineParams, StepResult
    from src.ui.dataops_view import render
    from src.ui.state import init_state, set_dataops_pipeline

    init_state()

    if "test_initialized" not in st.session_state:
        st.session_state["test_initialized"] = True

        class DummyStep:
            def __init__(self, step_id, rotulo, fonte, camada):
                self.step_id = step_id
                self.rotulo = rotulo
                self.fonte = fonte
                self.camada = camada
                self.depende_de = None

        orchestrator = MagicMock()
        orchestrator.steps.return_value = [
            DummyStep("step_1", "Etapa 1", "bacen", "bronze"),
            DummyStep("step_2", "Etapa 2", "bacen", "silver"),
        ]
        resultados = {}
        orchestrator.resultados = resultados

        def run_step(step_id):
            ok = step_id != fail_step
            res = StepResult(
                step_id=step_id,
                ok=ok,
                rows=100 if ok else 0,
                paths=[],
                duration_s=0.1,
                error=None if ok else "Erro simulado",
            )
            resultados[step_id] = res
            return res

        orchestrator.run_step.side_effect = run_step
        orchestrator.estado.side_effect = lambda: {k: asdict(v) for k, v in resultados.items()}

        params = PipelineParams(
            tickers=["PETR4"],
            bacen_periodo=("2019-01-01", "2023-12-31"),
            b3_periodo=("2019-01-01", "2024-01-01"),
            cvm_anos=[2021],
            is_sandbox=True,
        )
        set_dataops_pipeline(params, orchestrator)
        st.session_state["_test_orch"] = orchestrator  # referência p/ asserts

    render()


def _app_logs():
    from src.ui.state import add_dataops_log, init_state

    init_state()
    for i in range(600):
        add_dataops_log({"message": str(i)})


def test_execucao_continua_finaliza_e_limpa():
    at = AppTest.from_function(_app, default_timeout=10).run()
    assert not at.exception
    assert at.session_state["dataops_finalizado"] is True
    assert at.session_state["dataops_orchestrator"] is None
    assert set(at.session_state["dataops_resultados"]) == {"step_1", "step_2"}

    orch = at.session_state["_test_orch"]
    orch.logger.clear_handlers.assert_called_once()
    orch.logger.clear_logs.assert_called_once()


def test_falha_interrompe_pipeline_e_exibe_erro():
    at = AppTest.from_function(_app, kwargs={"fail_step": "step_1"}, default_timeout=10).run()
    assert not at.exception

    orch = at.session_state["_test_orch"]
    orch.run_step.assert_called_once_with("step_1")
    assert any("Erro simulado" in e.value for e in at.error)
    assert at.session_state["dataops_finalizado"] is True


def test_voltar_aos_parametros_zera_estado():
    at = AppTest.from_function(_app, default_timeout=10).run()
    [b for b in at.button if "Voltar aos Parâmetros" in b.label][0].click().run()

    assert at.session_state["dataops_params"] is None
    assert at.session_state["dataops_resultados"] == {}
    assert at.session_state["dataops_finalizado"] is False


def test_logs_respeitam_limite():
    at = AppTest.from_function(_app_logs).run()
    logs = at.session_state["dataops_logs"]
    assert len(logs) == 500
    assert logs[-1]["message"] == "599"