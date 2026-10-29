"""Testes automatizados com AppTest para o formulário e modo de execução do DataOps."""

from datetime import date
from unittest.mock import patch
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


def _run_dataops_app():
    from src.ui.dataops_view import render
    from src.ui.state import init_state

    init_state()
    render()


def test_dataops_form_defaults():
    at = AppTest.from_function(_run_dataops_app).run()
    assert not at.exception
    assert at.session_state["dataops_modo"] == "sandbox"
    assert at.session_state["dataops_params"] is None


def test_dataops_form_data_invalida_bloqueia():
    at = AppTest.from_function(_run_dataops_app).run()
    
    at.date_input(key="bacen_inicio").set_value(date(2024, 1, 1)).run()
    at.date_input(key="bacen_fim").set_value(date(2023, 1, 1)).run()

    botao_iniciar = [b for b in at.button if "Iniciar Pipeline" in b.label][0]
    assert botao_iniciar.disabled is True


def test_dataops_form_sandbox_teto_bloqueia():
    at = AppTest.from_function(_run_dataops_app).run()
    
    tickers_excesso = ["PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3", "ABEV3"]
    at.multiselect[0].set_value(tickers_excesso).run()

    botao_iniciar = [b for b in at.button if "Iniciar Pipeline" in b.label][0]
    assert botao_iniciar.disabled is True


def test_dataops_form_senha_incorreta_mantem_sandbox():
    at = AppTest.from_function(_run_dataops_app).run()
    
    with patch.object(st, "secrets", {"dataops_password": "senha_segura_123"}):
        at.text_input[0].set_value("senha_errada").run()
        assert at.session_state["dataops_modo"] == "sandbox"


def test_dataops_form_senha_correta_ativa_producao():
    at = AppTest.from_function(_run_dataops_app).run()
    
    with patch.object(st, "secrets", {"dataops_password": "senha_segura_123"}):
        at.text_input[0].set_value("senha_segura_123").run()
        assert at.session_state["dataops_modo"] == "producao"

def test_senha_nao_armazenada_em_session_state():
    at = AppTest.from_function(_run_dataops_app).run()
    at.text_input[0].set_value("senha_secreta_teste").run()

    chaves_estado = ["dataops_params", "dataops_modo", "dataops_orchestrator", "modo", "aba_ativa", "filtros"]
    for key in chaves_estado:
        assert at.session_state[key] != "senha_secreta_teste" 