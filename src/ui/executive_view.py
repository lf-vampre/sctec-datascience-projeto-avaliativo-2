"""Executive View - Visão Executiva do BI com menu horizontal, despacho sob demanda e sidebar global."""

import logging
import streamlit as st

from src.models.contracts import Filtros
from src.ui import sidebar
from src.ui.components.header import header
from src.ui.data_loader import DadosIndisponiveis

logger = logging.getLogger(__name__)

MAPA_ABAS = {
    "Dashboard 1 — Macro (BACEN)": "d1_macro",
    "Dashboard 2 — Fundamentalista (CVM)": "d2_cvm",
    "Dashboard 3 — Mercado e Risco (B3)": "d3_b3",
    "Dashboard 4 — Visão Integrada (Tríade)": "d4_integrated",
}

MAPA_ABAS_REVERSO = {v: k for k, v in MAPA_ABAS.items()}


def render() -> None:
    """Renderiza a visão executiva com sidebar, menu horizontal e despacho lazy de dashboards."""
    header(
        titulo="BI Executivo",
        subtitulo="Visão Integrada e Análise Multidimensão",
        mostrar_botao_voltar=True,
        mostrar_indicador_conexao=True,
    )

    filtros: Filtros = sidebar.render()

    opcoes_menu = list(MAPA_ABAS.keys())
    aba_atual_id = st.session_state.get("aba_ativa", "d1_macro")
    opcao_default = MAPA_ABAS_REVERSO.get(aba_atual_id, opcoes_menu[0])

    if hasattr(st, "segmented_control"):
        opcao_selecionada = st.segmented_control(
            "Selecione o Dashboard",
            options=opcoes_menu,
            default=opcao_default,
            label_visibility="collapsed",
        )
    else:
        opcao_selecionada = st.radio(
            "Selecione o Dashboard",
            options=opcoes_menu,
            index=opcoes_menu.index(opcao_default) if opcao_default in opcoes_menu else 0,
            horizontal=True,
            label_visibility="collapsed",
        )

    if opcao_selecionada:
        st.session_state["aba_ativa"] = MAPA_ABAS.get(opcao_selecionada, "d1_macro")
    else:
        opcao_selecionada = opcao_default

    if not filtros.tickers:
        st.info("Aguardando seleção de ativos na sidebar para exibir o dashboard.")
        return

    aba_ativa = st.session_state.get("aba_ativa", "d1_macro")

    try:
        if aba_ativa == "d1_macro":
            from src.ui.dashboards import macro_dashboard
            macro_dashboard.render(filtros)
        elif aba_ativa == "d2_cvm":
            from src.ui.dashboards import cvm_dashboard
            cvm_dashboard.render(filtros)
        elif aba_ativa == "d3_b3":
            from src.ui.dashboards import b3_dashboard
            b3_dashboard.render(filtros)
        elif aba_ativa == "d4_integrated":
            from src.ui.dashboards import integrated_dashboard
            integrated_dashboard.render(filtros)
    except DadosIndisponiveis as e:
        logger.warning("Dados indisponíveis ao carregar dashboard %s: %s", aba_ativa, str(e))
        st.warning(
            "Dados indisponíveis para o recorte selecionado. Execute o pipeline no DataOps para gerar a camada Ouro."
        )
    except Exception as e:
        logger.error("Erro inesperado no dashboard %s: %s", aba_ativa, str(e), exc_info=True)
        st.error(
            "Ocorreu um erro ao carregar as visualizações deste dashboard. Verifique os filtros ou tente novamente."
        )