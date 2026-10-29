"""Visão do DataOps Control Tower para configuração de parâmetros e modo de execução."""

from datetime import datetime
from typing import List, Tuple
import streamlit as st

from src.config import settings
from src.config.universe import COMPANIES
from src.etl.pipeline import PipelineOrchestrator, autorizar
from src.models.contracts import PipelineParams
from src.ui.components.alerts import aviso
from src.ui.components.header import header
from src.ui.state import (
    get_dataops_params,
    reset_dataops_pipeline,
    set_dataops_pipeline,
)


def _format_ticker_option(ticker: str) -> str:
    """Formata o rótulo do ticker para a seleção: TICKER — razão / setor."""
    info = COMPANIES[ticker]
    return f"{ticker} — {info.denom_cia} / {info.setor_analitico}"


def render() -> None:
    """Renderiza o formulário de parâmetros e modo de execução do DataOps."""
    header(
        titulo="⚙️ DataOps Control Tower",
        subtitulo="Orquestração e monitoramento do pipeline de dados.",
        mostrar_botao_voltar=True,
    )

    params_existentes = get_dataops_params()
    modo_atual = st.session_state.get("dataops_modo", "sandbox")

    # Faixa de modo sempre visível
    if modo_atual == "producao":
        aviso("info", "🟢 Modo Produção Ativo — Execuções serão persistidas na área oficial do Data Lake.")
    else:
        aviso(
            "warning",
            "🟡 Modo Sandbox Ativo — Execuções limitadas ao ambiente temporário isolado.",
        )

    st.caption(
        "💡 **Ajuda sobre os dados:** O período do BACEN e B3 utilizam datas no formato AAAA-MM-DD. "
        "A API do yfinance exige `end` exclusivo (ex: até 2024-01-01 para incluir todo o ano de 2023). "
        "A CVM opera com dados anuais do DFP."
    )

    if params_existentes:
        st.warning("⚠️ O pipeline já foi configurado. Alterar parâmetros irá reiniciar a sessão do orquestrador.")
        if st.button("🔄 Redefinir Parâmetros"):
            reset_dataops_pipeline()
            st.rerun()

    with st.container(border=True):
        st.subheader("📋 Parâmetros da Carga")

        # Seleção de Empresas/Tickers
        todos_tickers = list(COMPANIES.keys())
        tickers_selecionados = st.multiselect(
            "Empresas e Tickers",
            options=todos_tickers,
            default=todos_tickers,
            format_func=_format_ticker_option,
            help="Selecione os tickers do universo cobertos pelo pipeline.",
        )

        st.markdown("---")
        st.write("**Períodos por Fonte de Dados**")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 🏛️ BACEN (SGS)")
            bacen_inicio = st.date_input(
                "Início BACEN",
                value=datetime.strptime(settings.DEFAULT_BACEN_START_DATE, "%Y-%m-%d").date(),
                key="bacen_inicio",
            )
            bacen_fim = st.date_input(
                "Fim BACEN",
                value=datetime.strptime(settings.DEFAULT_BACEN_END_DATE, "%Y-%m-%d").date(),
                key="bacen_fim",
            )

        with col2:
            st.markdown("##### 📈 B3 (Cotações)")
            b3_inicio = st.date_input(
                "Início B3",
                value=datetime.strptime(settings.DEFAULT_B3_START_DATE, "%Y-%m-%d").date(),
                key="b3_inicio",
            )
            b3_fim = st.date_input(
                "Fim B3 (exclusivo)",
                value=datetime.strptime(settings.DEFAULT_B3_END_DATE, "%Y-%m-%d").date(),
                key="b3_fim",
            )

        st.markdown("##### 📄 CVM (Demonstrações Financeiras DFP)")
        anos_disponiveis = list(range(2010, datetime.now().year + 1))
        cvm_anos = st.multiselect(
            "Anos de Exercício CVM",
            options=anos_disponiveis,
            default=list(range(settings.DEFAULT_CVM_START_YEAR, settings.DEFAULT_CVM_END_YEAR + 1)),
            key="cvm_anos",
        )

        if st.button("⏱️ Aplicar Período Padrão B3/BACEN a Todas as Fontes"):
            st.session_state["bacen_inicio"] = datetime.strptime(settings.DEFAULT_BACEN_START_DATE, "%Y-%m-%d").date()
            st.session_state["bacen_fim"] = datetime.strptime(settings.DEFAULT_BACEN_END_DATE, "%Y-%m-%d").date()
            st.session_state["b3_inicio"] = datetime.strptime(settings.DEFAULT_B3_START_DATE, "%Y-%m-%d").date()
            st.session_state["b3_fim"] = datetime.strptime(settings.DEFAULT_B3_END_DATE, "%Y-%m-%d").date()
            st.rerun()

    # Expander de Modo de Execução
    with st.expander("🔑 Modo de Execução & Autenticação", expanded=False):
        senha_digitada = st.text_input(
            "Senha de Acesso DataOps",
            type="password",
            help="Deixe em branco ou informe senha para liberar o modo produção.",
        )

        senha_esperada = None
        try:
            senha_esperada = st.secrets.get("dataops_password")
        except Exception:
            pass

        modo_resultado = autorizar(senha_digitada, senha_esperada)
        st.session_state["dataops_modo"] = modo_resultado

        if modo_resultado == "producao":
            st.success("Autenticação realizada com sucesso! Modo Produção ativo.")
        else:
            st.info(
                "Modo Sandbox ativo. Execuções em sandbox salvam arquivos temporários "
                "e possuem restrições de volume de tickers sem impactar os dados oficiais."
            )

    # Validações prévias
    erros_validacao: List[str] = []

    if not tickers_selecionados:
        erros_validacao.append("Selecione pelo menos 1 ticker.")

    if bacen_inicio >= bacen_fim:
        erros_validacao.append("BACEN: Data inicial deve ser anterior à data final.")

    if b3_inicio >= b3_fim:
        erros_validacao.append("B3: Data inicial deve ser anterior à data final.")

    if not cvm_anos:
        erros_validacao.append("CVM: Selecione pelo menos 1 ano de exercício.")

    if modo_resultado == "sandbox":
        teto = getattr(settings, "SANDBOX_MAX_TICKERS", 5)
        if len(tickers_selecionados) > teto:
            erros_validacao.append(
                f"Modo Sandbox aceita no máximo {teto} tickers. "
                f"Você selecionou {len(tickers_selecionados)} tickers."
            )

    for err in erros_validacao:
        aviso("error", err)

    # Botão Iniciar
    botao_desabilitado = len(erros_validacao) > 0

    if st.button("🚀 Iniciar Pipeline de Dados", disabled=botao_desabilitado, type="primary"):
        params = PipelineParams(
            tickers=tickers_selecionados,
            bacen_periodo=(bacen_inicio.strftime("%Y-%m-%d"), bacen_fim.strftime("%Y-%m-%d")),
            b3_periodo=(b3_inicio.strftime("%Y-%m-%d"), b3_fim.strftime("%Y-%m-%d")),
            cvm_anos=sorted(cvm_anos),
            is_sandbox=(modo_resultado == "sandbox"),
        )
        orchestrator = PipelineOrchestrator(params)
        set_dataops_pipeline(params, orchestrator)
        st.success("Pipeline inicializado com sucesso! Pronto para execução dos passos.")
        st.rerun()