"""Testes de integração do módulo executive_view usando Streamlit AppTest."""

from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest

from src.ui.data_loader import DadosIndisponiveis
from src.ui.state import init_state


def _app_script():
    import streamlit as st
    from src.ui.executive_view import render
    from src.ui.state import init_state

    init_state()
    render()


def test_executive_view_render_padrao():
    at = AppTest.from_function(_app_script)
    at.run()
    assert not at.exception


def test_executive_view_troca_de_aba():
    def _script_troca():
        import streamlit as st
        from src.ui.executive_view import render
        from src.ui.state import init_state

        init_state()
        st.session_state["aba_ativa"] = "d2_cvm"
        render()

    at = AppTest.from_function(_script_troca)
    at.run()
    assert not at.exception
    assert at.session_state["aba_ativa"] == "d2_cvm"


def test_executive_view_tratamento_dados_indisponiveis():
    def _script_erro_dados():
        from unittest.mock import patch
        import streamlit as st
        from src.ui.executive_view import render
        from src.ui.state import init_state
        from src.ui.data_loader import DadosIndisponiveis

        init_state()
        with patch(
            "src.ui.dashboards.macro_dashboard.render",
            side_effect=DadosIndisponiveis("Falha na camada Ouro"),
        ):
            render()

    at = AppTest.from_function(_script_erro_dados)
    at.run()
    assert not at.exception
    assert len(at.warning) > 0


def test_executive_view_tratamento_erro_generico():
    def _script_erro_generico():
        from unittest.mock import patch
        import streamlit as st
        from src.ui.executive_view import render
        from src.ui.state import init_state

        init_state()
        with patch(
            "src.ui.dashboards.macro_dashboard.render",
            side_effect=RuntimeError("Erro inesperado no dashboard"),
        ):
            render()

    at = AppTest.from_function(_script_erro_generico)
    at.run()
    assert not at.exception
    assert len(at.error) > 0