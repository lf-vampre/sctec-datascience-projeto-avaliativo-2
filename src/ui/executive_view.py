"""Executive View - Visão Executiva do BI com menu horizontal, despacho sob demanda e indicador de conexão."""

import logging
import streamlit as st

from src.models.contracts import Filtros
from src.ui import sidebar
from src.ui.data_loader import DadosIndisponiveis, neon_disponivel

logger = logging.getLogger(__name__)

MAPA_ABAS = {
    "D1 — Macro (BACEN)": "d1_macro",
    "D2 — Fundamentalista (CVM)": "d2_cvm",
    "D3 — Mercado e Risco (B3)": "d3_b3",
    "D4 — Visão Integrada (Tríade)": "d4_integrated",
}

MAPA_ABAS_REVERSO = {v: k for k, v in MAPA_ABAS.items()}


def render() -> None:
    """Renderiza a visão executiva com barra superior compacta, menu horizontal e despacho lazy de dashboards."""
    filtros: Filtros = sidebar.render()

    col_menu, col_status = st.columns([0.75, 0.25], vertical_alignment="center")

    opcoes_menu = list(MAPA_ABAS.keys())
    aba_atual_id = st.session_state.get("aba_ativa", "d1_macro")
    opcao_default = MAPA_ABAS_REVERSO.get(aba_atual_id, opcoes_menu[0])

    def _ao_mudar_aba():
        val = st.session_state.get("menu_opcao_dashboard")
        if val in MAPA_ABAS:
            st.session_state["aba_ativa"] = MAPA_ABAS[val]

    with col_menu:
        if hasattr(st, "segmented_control"):
            st.segmented_control(
                "Selecione o Dashboard",
                options=opcoes_menu,
                default=opcao_default,
                key="menu_opcao_dashboard",
                on_change=_ao_mudar_aba,
                label_visibility="collapsed",
            )
        else:
            st.radio(
                "Selecione o Dashboard",
                options=opcoes_menu,
                index=opcoes_menu.index(opcao_default) if opcao_default in opcoes_menu else 0,
                key="menu_opcao_dashboard",
                on_change=_ao_mudar_aba,
                horizontal=True,
                label_visibility="collapsed",
            )

    with col_status:
        is_neon = neon_disponivel()
        status_texto = "🟢 Postgres Neon" if is_neon else "🟠 Fallback Parquet"
        badge_class = "fx-badge-success" if is_neon else "fx-badge-warning"
        html_status = (
            f'<div style="text-align: right; font-size: var(--fx-font-size-sm); margin-bottom: 10px;">'
            f'<span style="color: var(--fx-color-text-secondary);">Conexão ativa: </span>'
            f'<span class="fx-badge {badge_class}">{status_texto}</span>'
            f'</div>'
        )
        st.markdown(html_status, unsafe_allow_html=True)

#    if opcao_selecionada:
#        st.session_state["aba_ativa"] = MAPA_ABAS.get(opcao_selecionada, "d1_macro")
#    else:
#        opcao_selecionada = opcao_default

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