"""Testes automatizados com AppTest para o painel de execução step-by-step do DataOps."""

from unittest.mock import MagicMock
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.models.contracts import PipelineParams, StepResult


class DummyStep:
    def __init__(self, step_id: str, rotulo: str, fonte: str, camada: str, depende_de: str = None):
        self.step_id = step_id
        self.rotulo = rotulo
        self.fonte = fonte
        self.camada = camada
        self.depende_de = depende_de


def _create_mock_orchestrator():
    orchestrator = MagicMock()
    
    step1 = DummyStep("step_1", "Etapa 1", "BACEN", "Bronze")
    step2 = DummyStep("step_2", "Etapa 2", "BACEN", "Silver", depende_de="step_1")
    orchestrator.steps.return_value = [step1, step2]
    
    resultados = {}
    orchestrator.resultados = resultados
    
    def proximo_passo():
        if "step_1" not in resultados:
            return "step_1"
        if "step_2" not in resultados:
            return "step_2"
        return None
        
    def pode_executar(step_id):
        if step_id == "step_1":
            return True, ""
        if step_id == "step_2":
            return "step_1" in resultados and resultados["step_1"].ok, "Aguardando etapa 1"
        return False, ""

    def run_step(step_id):
        res = StepResult(
            step_id=step_id,
            ok=True,
            rows=100,
            paths=["data/test.parquet"],
            duration_s=0.5,
        )
        resultados[step_id] = res
        return res

    orchestrator.proximo_passo.side_effect = proximo_passo
    orchestrator.pode_executar.side_effect = pode_executar
    orchestrator.run_step.side_effect = run_step
    orchestrator.logger = MagicMock()
    
    return orchestrator

def _run_dataops_execution_app():
    from unittest.mock import MagicMock
    import streamlit as st
    from src.models.contracts import PipelineParams, StepResult
    from src.ui.dataops_view import render
    from src.ui.state import init_state, set_dataops_pipeline

    init_state()

    if "test_initialized" not in st.session_state:
        st.session_state["test_initialized"] = True

        class DummyStep:
            def __init__(self, step_id: str, rotulo: str, fonte: str, camada: str, depende_de: str = None):
                self.step_id = step_id
                self.rotulo = rotulo
                self.fonte = fonte
                self.camada = camada
                self.depende_de = depende_de

        orchestrator = MagicMock()
        step1 = DummyStep("step_1", "Etapa 1", "BACEN", "Bronze")
        step2 = DummyStep("step_2", "Etapa 2", "BACEN", "Silver", depende_de="step_1")
        orchestrator.steps.return_value = [step1, step2]
        
        resultados = {}
        orchestrator.resultados = resultados
        
        def proximo_passo():
            if "step_1" not in resultados:
                return "step_1"
            if "step_2" not in resultados:
                return "step_2"
            return None
            
        def pode_executar(step_id):
            if step_id == "step_1":
                return True, ""
            if step_id == "step_2":
                return "step_1" in resultados and resultados["step_1"].ok, "Aguardando etapa 1"
            return False, ""

        def run_step(step_id):
            res = StepResult(
                step_id=step_id,
                ok=True,
                rows=100,
                paths=["data/test.parquet"],
                duration_s=0.5,
            )
            resultados[step_id] = res
            return res

        orchestrator.proximo_passo.side_effect = proximo_passo
        orchestrator.pode_executar.side_effect = pode_executar
        orchestrator.run_step.side_effect = run_step
        orchestrator.logger = MagicMock()

        params = PipelineParams(
            tickers=["PETR4"],
            bacen_periodo=("2019-01-01", "2023-12-31"),
            b3_periodo=("2019-01-01", "2024-01-01"),
            cvm_anos=[2019, 2020],
            is_sandbox=True,
        )
        set_dataops_pipeline(params, orchestrator)

    render()

def test_dataops_execution_panel_renders():
    at = AppTest.from_function(_run_dataops_execution_app).run()
    assert not at.exception
    assert at.session_state["dataops_params"] is not None


def test_dataops_step2_disabled_before_step1():
    at = AppTest.from_function(_run_dataops_execution_app).run()
    
    botoes_executar = [
        b for b in at.button 
        if "Executar" in b.label and "Reiniciar" not in b.label and "Limpar" not in b.label
    ]
    assert len(botoes_executar) >= 2
    assert botoes_executar[0].disabled is False
    assert botoes_executar[1].disabled is True


def test_dataops_executa_step1_e_libera_step2():
    at = AppTest.from_function(_run_dataops_execution_app).run()
    
    botoes_executar = [
        b for b in at.button 
        if "Executar" in b.label and "Reiniciar" not in b.label and "Limpar" not in b.label
    ]
    botoes_executar[0].click().run()
    assert not at.exception
    
    botoes_pos = [
        b for b in at.button 
        if "Executar" in b.label and "Reiniciar" not in b.label and "Limpar" not in b.label
    ]
    assert botoes_pos[1].disabled is False


def test_dataops_limpar_memoria():
    at = AppTest.from_function(_run_dataops_execution_app).run()
    
    btn_limpar = [b for b in at.button if "Finalizar e Limpar Memória" in b.label][0]
    btn_limpar.click().run()
    
    assert at.session_state["dataops_params"] is None
    assert at.session_state["dataops_orchestrator"] is None