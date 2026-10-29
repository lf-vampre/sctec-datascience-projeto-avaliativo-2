"""Visão do DataOps Control Tower para parametrização e execução do pipeline."""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import streamlit as st
import logging

logger = logging.getLogger(__name__)

from src.config import settings
from src.config.universe import COMPANIES
from src.etl.pipeline import PipelineOrchestrator, autorizar
from src.models.contracts import PipelineParams
from src.ui.components.alerts import aviso
from src.ui.components.header import header
from src.ui.state import (
    add_dataops_log,
    get_dataops_params,
    limpar_memoria_dataops,
    reset_dataops_pipeline,
    set_dataops_pipeline,
)


def _format_ticker_option(ticker: str) -> str:
    """Formata o rótulo do ticker para a seleção: TICKER — razão / setor."""
    info = COMPANIES[ticker]
    return f"{ticker} — {info.denom_cia} / {info.setor_analitico}"

def _obter_senha_esperada() -> Optional[str]:
    """Obtém a senha configurada via variáveis de ambiente, secrets do Streamlit ou settings."""
    env_pass = os.getenv("DATAOPS_PASSWORD") or os.getenv("dataops_password")
    if env_pass:
        return str(env_pass).strip()

    try:
        if hasattr(st, "secrets"):
            if "dataops_password" in st.secrets:
                return str(st.secrets["dataops_password"]).strip()
            if "DATAOPS_PASSWORD" in st.secrets:
                return str(st.secrets["DATAOPS_PASSWORD"]).strip()
            if "dataops" in st.secrets:
                sec_dataops = st.secrets["dataops"]
                if isinstance(sec_dataops, dict) and "password" in sec_dataops:
                    return str(sec_dataops["password"]).strip()
                elif isinstance(sec_dataops, str):
                    return str(sec_dataops).strip()
    except FileNotFoundError:
        # Sem secrets.toml: esperado em ambiente sem configuração
        pass
    except Exception as exc:
        logger.warning("Falha ao ler secrets do DataOps: %s", type(exc).__name__)

    setting_pass = getattr(settings, "DATAOPS_PASSWORD", None)
    if setting_pass:
        return str(setting_pass).strip()

    return None

def _render_autenticacao() -> None:
    """Renderiza a autenticação e indicação do modo no topo da página."""
    col_auth, col_status = st.columns([1, 2])

    with col_auth:
        st.write("**🔐 Autenticação**")
        col_inp, col_btn = st.columns([2, 1])
        with col_inp:
            senha_digitada = st.text_input(
                "Senha DataOps",
                type="password",
                key="input_dataops_password",
                label_visibility="collapsed",
                placeholder="Senha de Produção",
            )
        with col_btn:
            btn_validar = st.button("Validar", key="btn_validar_senha")

        if btn_validar:
            senha_esperada = _obter_senha_esperada()
            modo_resultado = autorizar(senha_digitada, senha_esperada)
            st.session_state["dataops_modo"] = modo_resultado

            orchestrator: Optional[PipelineOrchestrator] = st.session_state.get("dataops_orchestrator")
            if orchestrator and orchestrator.params:
                orchestrator.params.is_sandbox = (modo_resultado == "sandbox")

            if modo_resultado == "producao":
                st.session_state["auth_feedback"] = ("success", "Autenticado - modo produção")
            elif not senha_esperada:
                st.session_state["auth_feedback"] = ("error", "Senha de produção não configurada")
            else:
                st.session_state["auth_feedback"] = ("error", "Senha inválida")

        if "auth_feedback" in st.session_state:
            tipo, msg = st.session_state["auth_feedback"]
            if tipo == "success":
                st.success(msg)
            else:
                st.error(msg)

    modo_atual = st.session_state.get("dataops_modo", "sandbox")
    #with col_status:
        #

    if modo_atual == "producao":
        aviso("info", "🟢 Modo Produção Ativo — Execuções serão persistidas na área oficial do Data warehouse.")
    else:
        aviso("warning", "🟡 Modo Sandbox Ativo — Execuções limitadas ao ambiente temporário isolado.")


def _render_formulario() -> None:
    """Renderiza a seção de formulário e configuração do pipeline."""
    if st.session_state.pop("reset_dates_flag", False):
        st.session_state["bacen_inicio"] = datetime.strptime(settings.DEFAULT_BACEN_START_DATE, "%Y-%m-%d").date()
        st.session_state["bacen_fim"] = datetime.strptime(settings.DEFAULT_BACEN_END_DATE, "%Y-%m-%d").date()
        st.session_state["b3_inicio"] = datetime.strptime(settings.DEFAULT_B3_START_DATE, "%Y-%m-%d").date()
        st.session_state["b3_fim"] = datetime.strptime(settings.DEFAULT_B3_END_DATE, "%Y-%m-%d").date()
        st.session_state["cvm_anos"] = list(range(settings.DEFAULT_CVM_START_YEAR, settings.DEFAULT_CVM_END_YEAR + 1))

    with st.container(border=True):
        st.subheader("📋 Parâmetros da Carga")

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
        st.caption(
                "💡 **Ajuda sobre os dados:** O período do BACEN e B3 utilizam datas no formato AAAA-MM-DD. "
                "A API do yfinance exige `end` exclusivo. A CVM opera com dados anuais do DFP."
            )
        st.markdown("---")

        col1_bacen, col2_bacen = st.columns(2)

        with col1_bacen:
            st.markdown("##### 🏛️ BACEN (SGS)")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                bacen_inicio = st.date_input(
                    "Início BACEN",
                    value=st.session_state.get("bacen_inicio", datetime.strptime(settings.DEFAULT_BACEN_START_DATE, "%Y-%m-%d").date()),
                    key="bacen_inicio",
                )
            with sub_c2:
                bacen_fim = st.date_input(
                    "Fim BACEN",
                    value=st.session_state.get("bacen_fim", datetime.strptime(settings.DEFAULT_BACEN_END_DATE, "%Y-%m-%d").date()),
                    key="bacen_fim",
                )

        col1_b3, col2_b3 = st.columns(2)

        with col1_b3:
            st.markdown("##### 📈 B3 (Cotações)")
            sub_c3, sub_c4 = st.columns(2)
            with sub_c3:
                b3_inicio = st.date_input(
                    "Início B3",
                    value=st.session_state.get("b3_inicio", datetime.strptime(settings.DEFAULT_B3_START_DATE, "%Y-%m-%d").date()),
                    key="b3_inicio",
                )
            with sub_c4:
                b3_fim = st.date_input(
                    "Fim B3 (exclusivo)",
                    value=st.session_state.get("b3_fim", datetime.strptime(settings.DEFAULT_B3_END_DATE, "%Y-%m-%d").date()),
                    key="b3_fim",
                )

        st.markdown("##### 📄 CVM (Demonstrações Financeiras DFP)")
        anos_disponiveis = list(range(2010, datetime.now().year + 1))
        cvm_anos = st.multiselect(
            "Anos de Exercício CVM",
            options=anos_disponiveis,
            default=st.session_state.get("cvm_anos", list(range(settings.DEFAULT_CVM_START_YEAR, settings.DEFAULT_CVM_END_YEAR + 1))),
            key="cvm_anos",
        )

        if st.button("⏱️ Resetar para período padrão"):
            st.session_state["reset_dates_flag"] = True
            st.rerun()

    modo_resultado = st.session_state.get("dataops_modo", "sandbox")
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
        st.rerun()

def _render_painel_execucao(orchestrator: Optional[PipelineOrchestrator]) -> None:
    """Renderiza a interface de execução sequencial e relatórios."""
    finalizado = st.session_state.get("dataops_finalizado", False)

    if st.button("🔄 Voltar aos Parâmetros"):
        reset_dataops_pipeline()
        st.rerun()

    st.markdown("### 🚀 Execução do Pipeline")
    banner = st.empty()
    with banner.container():
        if finalizado:
            aviso("info", "✅ Pipeline finalizado. Memória e cache liberados; logs mantidos para consulta.")
        else:
            aviso("info", "Executando carga completa (Bronze ➔ Prata ➔ Ouro)...")

    from src.etl.warehouse.persistence import Persistence

    persistence = Persistence()

    logs = st.session_state.get("dataops_logs", [])
    with st.expander(
        "📜 Histórico de Logs", expanded=True
    ):
        fontes_disponiveis = ["TODAS"] + sorted(
            list({l["fonte"] for l in logs if "fonte" in l})
        )
        niveis_disponiveis = ["TODOS", "INFO", "WARNING", "ERROR"]

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_fonte = st.selectbox(
                "Filtrar por Fonte",
                options=fontes_disponiveis,
                key="log_f_fonte",
            )
        with col_f2:
            filtro_nivel = st.selectbox(
                "Filtrar por Nível",
                options=niveis_disponiveis,
                key="log_f_nivel",
            )

        log_placeholder = st.empty()

        def _render_logs_em_tempo_real() -> None:
            logs_atuais = st.session_state.get("dataops_logs", [])
            logs_filtrados = logs_atuais
            if filtro_fonte != "TODAS":
                logs_filtrados = [
                    l for l in logs_filtrados if l.get("fonte") == filtro_fonte
                ]
            if filtro_nivel != "TODOS":
                logs_filtrados = [
                    l for l in logs_filtrados if l.get("level") == filtro_nivel
                ]

            def _tag(l: Dict[str, Any]) -> str:
                camada = (l.get("camada") or "").capitalize()
                return f"{camada} - {l['fonte']}" if camada else l["fonte"]

            log_str = "\n".join(
                f"[{l['timestamp']}] [{l['level']}] [{_tag(l)}] [{l['etapa']}] {l['message']}"
                for l in logs_filtrados
            )
            log_placeholder.code(
                log_str if log_str else "Aguardando eventos...", language="text"
            )

        def log_callback(event: Dict[str, Any]) -> None:
            add_dataops_log(event)
            _render_logs_em_tempo_real()

        if orchestrator is not None and not orchestrator.resultados:
            orchestrator.logger.add_handler(log_callback)
            try:
                for step in orchestrator.steps():
                    res = orchestrator.run_step(step.step_id)
                    if not res.ok:
                        break
            except Exception as e:
                st.error(f"❌ Erro fatal na execução do pipeline: {e}")
            finally:
                limpar_memoria_dataops()
                with banner.container():
                    aviso("info", "✅ Pipeline finalizado. Memória e cache liberados; logs mantidos para consulta.")

        _render_logs_em_tempo_real()

    resultados = st.session_state.get("dataops_resultados", {})
    for step_id, res in resultados.items():
        if not res.get("ok"):
            st.error(f"❌ Falha em {step_id}: {res.get('error')}")

    st.markdown("### 🏥 Relatório de Saúde (Health Report)")
    modo_atual = st.session_state.get("dataops_modo", "sandbox")
    report = persistence.health_report(modo=modo_atual)

    for tabela, stats in report.items():
        diverge_icon = "⚠️" if stats.get("divergencia") else "✅"
        st.info(
            f"{diverge_icon} **{tabela}**: Parquet: {stats.get('linhas_parquet', 0)} | "
            f"Neon: {stats.get('linhas_neon', 0)} | "
            f"Fonte: {stats.get('fonte_ativa', 'N/A')} | "
            f"Divergência: {stats.get('divergencia', False)}"
        )

def render() -> None:
    """Renderiza a visão do DataOps Control Tower."""
    header(
        titulo="⚙️ DataOps Control Tower",
        subtitulo="Orquestração e monitoramento do pipeline de dados.",
        mostrar_botao_voltar=True,
    )

    _render_autenticacao()


    params = get_dataops_params()
    orchestrator: Optional[PipelineOrchestrator] = st.session_state.get("dataops_orchestrator")

    if params is None:
        _render_formulario()
    else:
        _render_painel_execucao(orchestrator)