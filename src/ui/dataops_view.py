"""Visão do DataOps Control Tower para parametrização, execução do pipeline e EDA."""

import io
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from src.config import settings
from src.config.universe import COMPANIES
from src.etl.eda.profiler import DataProfiler, RelatorioEDA
from src.etl.pipeline import PipelineOrchestrator, autorizar
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import PipelineParams
from src.ui.charts.eda_charts import (
    fig_assimetria_curtose,
    fig_cobertura_temporal,
    fig_distribuicao_histograma,
    fig_nulos_coluna,
)
from src.ui.components.alerts import aviso
from src.ui.components.header import header
from src.ui.state import (
    add_dataops_log,
    get_dataops_params,
    limpar_memoria_dataops,
    reset_dataops_pipeline,
    set_dataops_pipeline,
)

logger = logging.getLogger(__name__)


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
        pass
    except Exception as exc:
        logger.warning("Falha ao ler secrets do DataOps: %s", type(exc).__name__)

    setting_pass = getattr(settings, "DATAOPS_PASSWORD", None)
    if setting_pass:
        return str(setting_pass).strip()

    return None


def _render_autenticacao() -> None:
    """Renderiza a autenticação e indicação do modo no topo da página."""
    
    st.write("**🔐 Autenticação**")
    #col_inp, col_btn = st.columns([2, 1])
    #with col_inp:
    st.text_input(
        "Senha DataOps",
        type="password",
        key="input_dataops_password",
        label_visibility="collapsed",
        placeholder="Senha de Produção",
    )
    col_btn, col_status = st.columns([1, 2])
    
    with col_btn:
        btn_validar = st.button("Validar", key="btn_validar_senha", use_container_width=True)

        if btn_validar:
            senha_digitada = st.session_state.get("input_dataops_password", "")
            senha_esperada = _obter_senha_esperada()
            modo_resultado = autorizar(senha_digitada, senha_esperada)
            st.session_state["dataops_modo"] = modo_resultado

            orchestrator: Optional[PipelineOrchestrator] = st.session_state.get(
                "dataops_orchestrator"
            )
            if orchestrator and orchestrator.params:
                orchestrator.params.is_sandbox = modo_resultado == "sandbox"

            if modo_resultado == "producao":
                st.session_state["auth_feedback"] = (
                    "success",
                    "Autenticado - modo produção",
                )
            elif not senha_esperada:
                st.session_state["auth_feedback"] = (
                    "error",
                    "Senha de produção não configurada",
                )
            else:
                st.session_state["auth_feedback"] = ("error", "Senha inválida")

    with col_status:
        if "auth_feedback" in st.session_state:
            tipo, msg = st.session_state["auth_feedback"]
            if tipo == "success":
                st.success(msg)
            else:
                st.error(msg)

def _render_formulario() -> None:
    """Renderiza a seção de formulário e configuração do pipeline."""

    teto = getattr(settings, "SANDBOX_MAX_TICKERS", 5)

    if st.session_state.pop("reset_dates_flag", False):
        st.session_state["bacen_inicio"] = datetime.strptime(
            settings.DEFAULT_BACEN_START_DATE, "%Y-%m-%d"
        ).date()
        st.session_state["bacen_fim"] = datetime.strptime(
            settings.DEFAULT_BACEN_END_DATE, "%Y-%m-%d"
        ).date()
        st.session_state["b3_inicio"] = datetime.strptime(
            settings.DEFAULT_B3_START_DATE, "%Y-%m-%d"
        ).date()
        st.session_state["b3_fim"] = datetime.strptime(
            settings.DEFAULT_B3_END_DATE, "%Y-%m-%d"
        ).date()
        st.session_state["cvm_anos"] = list(
            range(settings.DEFAULT_CVM_START_YEAR, settings.DEFAULT_CVM_END_YEAR + 1)
        )

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
 
        if len(tickers_selecionados) > teto and st.session_state.get("dataops_modo", "sandbox") == "sandbox":
            aviso("error",
                f"Modo Sandbox aceita no máximo {teto} tickers. "
                f"Você selecionou {len(tickers_selecionados)} tickers."
            )

        st.markdown("---")
        st.write("**Períodos por Fonte de Dados**")
        st.caption(
            "💡 **Ajuda sobre os dados:** O período do BACEN e B3 utilizam datas no formato AAAA-MM-DD. "
            "A API do yfinance exige `end` exclusivo. A CVM opera com dados anuais do DFP."
        )

        if st.button("⏱️ Resetar para período padrão"):
            st.session_state["reset_dates_flag"] = True
            st.rerun()        

        st.markdown("---")

        col1_bacen, col1_b3 = st.columns(2)

        with col1_bacen:
            st.markdown("##### 🏛️ BACEN (SGS)")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                bacen_inicio = st.date_input(
                    "Início BACEN",
                    value=st.session_state.get(
                        "bacen_inicio",
                        datetime.strptime(
                            settings.DEFAULT_BACEN_START_DATE, "%Y-%m-%d"
                        ).date(),
                    ),
                    key="bacen_inicio",
                )
            with sub_c2:
                bacen_fim = st.date_input(
                    "Fim BACEN",
                    value=st.session_state.get(
                        "bacen_fim",
                        datetime.strptime(
                            settings.DEFAULT_BACEN_END_DATE, "%Y-%m-%d"
                        ).date(),
                    ),
                    key="bacen_fim",
                )

        #col1_b3, _ = st.columns(2)

        with col1_b3:
            st.markdown("##### 📈 B3 (Cotações)")
            sub_c3, sub_c4 = st.columns(2)
            with sub_c3:
                b3_inicio = st.date_input(
                    "Início B3",
                    value=st.session_state.get(
                        "b3_inicio",
                        datetime.strptime(
                            settings.DEFAULT_B3_START_DATE, "%Y-%m-%d"
                        ).date(),
                    ),
                    key="b3_inicio",
                )
            with sub_c4:
                b3_fim = st.date_input(
                    "Fim B3 (exclusivo)",
                    value=st.session_state.get(
                        "b3_fim",
                        datetime.strptime(
                            settings.DEFAULT_B3_END_DATE, "%Y-%m-%d"
                        ).date(),
                    ),
                    key="b3_fim",
                )

        st.markdown("---")

        st.markdown("##### 📄 CVM (Demonstrações Financeiras DFP)")
        anos_disponiveis = list(range(2010, datetime.now().year + 1))
        cvm_anos = st.multiselect(
            "Anos de Exercício CVM",
            options=anos_disponiveis,
            default=st.session_state.get(
                "cvm_anos",
                list(
                    range(
                        settings.DEFAULT_CVM_START_YEAR,
                        settings.DEFAULT_CVM_END_YEAR + 1,
                    )
                ),
            ),
            key="cvm_anos",
        )
      

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
        if len(tickers_selecionados) > teto:
            erros_validacao.append(
                f"Modo Sandbox aceita no máximo {teto} tickers. "
                f"Você selecionou {len(tickers_selecionados)} tickers."
            )

    for err in erros_validacao:
        aviso("error", err)

    botao_desabilitado = len(erros_validacao) > 0

    if st.button(
        "🚀 Iniciar Pipeline de Dados", disabled=botao_desabilitado, type="primary"
    ):
        params = PipelineParams(
            tickers=tickers_selecionados,
            bacen_periodo=(
                bacen_inicio.strftime("%Y-%m-%d"),
                bacen_fim.strftime("%Y-%m-%d"),
            ),
            b3_periodo=(
                b3_inicio.strftime("%Y-%m-%d"),
                b3_fim.strftime("%Y-%m-%d"),
            ),
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
            aviso(
                "info",
                "✅ Pipeline finalizado. Memória e cache liberados; logs mantidos para consulta.",
            )
        else:
            aviso("info", "Executando carga completa (Bronze ➔ Prata ➔ Ouro)...")

    persistence = Persistence()

    logs = st.session_state.get("dataops_logs", [])
    with st.expander("📜 Histórico de Logs", expanded=True):
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
                    aviso(
                        "info",
                        "✅ Pipeline finalizado. Memória e cache liberados; logs mantidos para consulta.",
                    )

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


@st.cache_data(ttl=3600, show_spinner="Gerando relatório de EDA...")
def _gerar_relatorio_eda(fonte: str, modo: str) -> RelatorioEDA:
    """Gera o relatório de EDA com suporte a cache por fonte e modo."""
    profiler = DataProfiler()
    return profiler.perfil(fonte=fonte, modo=modo)


def _render_secao_eda() -> None:
    """Renderiza a seção interativa de Análise Exploratória de Dados (EDA)."""
    with st.container(border=True):
        #st.markdown("---")
        st.subheader("🔍 EDA e Qualidade dos Dados (Prata)")

        modo_atual = st.session_state.get("dataops_modo", "sandbox")
        persistence = Persistence()

        # Verificar quais tabelas da Prata possuem dados
        fontes_opcoes = ["bacen", "b3", "cvm", "cadastro"]
        fontes_disponiveis = []

        for f in fontes_opcoes:
            tbl = DataProfiler.FONTE_TABELA[f]
            df_chk = persistence.load(layer="silver", name=tbl, modo=modo_atual)
            if not df_chk.empty:
                fontes_disponiveis.append(f)

        if not fontes_disponiveis:
            aviso(
                "info",
                f"Nenhum dado Prata encontrado no modo '{modo_atual}'. Execute o pipeline para gerar diagnósticos.",
            )
            return

        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            fonte_selecionada = st.selectbox(
                "Selecione a fonte para profilagem:",
                options=fontes_opcoes,
                format_func=lambda x: f"{x.upper()} ({DataProfiler.FONTE_TABELA[x]})",
                key="eda_fonte_select",
            )
        with col_btn:
            st.write("")
            st.write("")
            btn_gerar = st.button("Gerar Relatório", type="primary", key="btn_gerar_eda")

        if btn_gerar or "relatorio_eda_ativo" in st.session_state:
            st.session_state["relatorio_eda_ativo"] = (fonte_selecionada, modo_atual)
            relatorio: RelatorioEDA = _gerar_relatorio_eda(fonte_selecionada, modo_atual)

            resumo = relatorio.resumo
            achados = relatorio.achados

            # KPIs do Relatório
            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            with col_k1:
                st.metric("Total de Linhas", f"{resumo.get('linhas', 0):,}")
            with col_k2:
                st.metric("Total de Colunas", resumo.get("colunas", 0))
            with col_k3:
                criticos = sum(1 for a in achados if a.severidade == "critico")
                st.metric("Achados Críticos", criticos)
            with col_k4:
                atencao = sum(1 for a in achados if a.severidade == "atencao")
                st.metric("Avisos / Atenção", atencao)

            if relatorio.avisos:
                for av in relatorio.avisos:
                    aviso("warning", av)

            # Abas de Análise
            tab_nulos, tab_dist, tab_temp, tab_est, tab_achados = st.tabs(
                [
                    "📋 Nulos e Duplicatas",
                    "📊 Distribuições",
                    "📅 Cobertura Temporal",
                    "📈 Estatísticas",
                    "🚨 Achados de Qualidade",
                ]
            )

            with tab_nulos:
                st.markdown("#### Diagnosticador de Nulos e Duplicadas")
                if "nulos_por_coluna" in relatorio.tabelas:
                    df_nulos = relatorio.tabelas["nulos_por_coluna"]
                    fig_n = fig_nulos_coluna(df_nulos)
                    st.plotly_chart(fig_n, use_container_width=True)
                    st.markdown("###### Quantidade de Nulos e Percentual")
                    df_nulos['nulos_pct']= df_nulos['nulos_pct'].round(2)
                    df_nulos.rename(columns={'nulos_qtd':'Quantidade Nulos','nulos_pct':'Percentual Nulos'}, inplace=True)
                    st.dataframe(df_nulos, use_container_width=True)
                else:
                    st.info("Sem dados de nulos disponíveis.")

            with tab_dist:
                st.markdown("#### Análise de Distribuição e Outliers")
                tbl_silver = DataProfiler.FONTE_TABELA[fonte_selecionada]
                df_silver = persistence.load(
                    layer="silver", name=tbl_silver, modo=modo_atual
                )
                cols_num = df_silver.select_dtypes(include=["number"]).columns.tolist()

                if cols_num:
                    var_escolhida = st.selectbox(
                        "Variável Numérica:", options=cols_num, key="eda_var_dist"
                    )
                    fig_d = fig_distribuicao_histograma(df_silver, var_escolhida)
                    st.plotly_chart(fig_d, use_container_width=True)
                else:
                    st.info("Nenhuma coluna numérica encontrada para distribuição.")

            with tab_temp:
                st.markdown("#### Cobertura Temporal de Dados")
                tbl_silver = DataProfiler.FONTE_TABELA[fonte_selecionada]
                df_silver = persistence.load(
                    layer="silver", name=tbl_silver, modo=modo_atual
                )

                col_grp = next(
                    (
                        c
                        for c in ["codigo_sgs", "ticker", "cd_cvm", "sit_cad"]
                        if c in df_silver.columns
                    ),
                    None,
                )
                col_dt = next(
                    (c for c in ["data", "dt_refer", "DT_FIM_EXERC"] if c in df_silver.columns),
                    None,
                )

                if col_grp and col_dt:
                    fig_c = fig_cobertura_temporal(df_silver, col_grp, col_dt)
                    st.plotly_chart(fig_c, use_container_width=True)
                else:
                    st.info("Variáveis temporais ou de agrupamento não disponíveis.")

            with tab_est:
                st.markdown("#### Estatísticas Descritivas e Métricas Avançadas")
                if "estatisticas_descritivas" in relatorio.tabelas:
                    st.dataframe(
                        relatorio.tabelas["estatisticas_descritivas"],
                        use_container_width=True,
                    )

                if fonte_selecionada == "b3" and "metricas_b3" in relatorio.tabelas:
                    st.markdown("##### 📈 Diagnóstico de Normalidade e Retornos B3")
                    df_m = relatorio.tabelas["metricas_b3"]
                    fig_ac = fig_assimetria_curtose(df_m)
                    st.plotly_chart(fig_ac, use_container_width=True)
                    st.dataframe(df_m, use_container_width=True)

            with tab_achados:
                st.markdown("#### Lista Auditável de Achados de Qualidade")
                if achados:
                    for a in achados:
                        ic = (
                            "🔴"
                            if a.severidade == "critico"
                            else ("🟡" if a.severidade == "atencao" else "🔵")
                        )
                        with st.expander(
                            f"{ic} [{a.severidade.upper()}] {a.titulo} ({a.id})"
                        ):
                            st.write(f"**Detalhe:** {a.detalhe}")
                            st.write(f"**Métrica:** `{a.metrica}`")
                            st.write(f"**Ação Sugerida:** {a.acao_sugerida}")
                else:
                    st.success("Nenhum achado de qualidade ou anomalia registrado.")

            # Opções de Exportação
            st.markdown("---")
            st.markdown("##### 💾 Exportar Relatório de EDA")
            col_exp1, col_exp2 = st.columns(2)

            with col_exp1:
                # Markdown do resumo e achados
                md_buffer = io.StringIO()
                md_buffer.write(f"# Relatório EDA — {fonte_selecionada.upper()}\n\n")
                md_buffer.write(f"- **Data:** {resumo.get('data_geracao')}\n")
                md_buffer.write(f"- **Linhas:** {resumo.get('linhas')}\n")
                md_buffer.write(f"- **Colunas:** {resumo.get('colunas')}\n")
                md_buffer.write(f"- **Período:** {resumo.get('periodo')}\n\n")
                md_buffer.write("## Achados Registrados\n\n")

                for a in achados:
                    md_buffer.write(f"### [{a.severidade.upper()}] {a.titulo}\n")
                    md_buffer.write(f"- **ID:** {a.id}\n")
                    md_buffer.write(f"- **Detalhe:** {a.detalhe}\n")
                    md_buffer.write(f"- **Métrica:** {a.metrica}\n")
                    md_buffer.write(f"- **Ação Sugerida:** {a.acao_sugerida}\n\n")

                st.download_button(
                    "📥 Baixar Relatório (Markdown)",
                    data=md_buffer.getvalue(),
                    file_name=f"eda_relatorio_{fonte_selecionada}_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                )

            with col_exp2:
                # CSV dos Achados
                if achados:
                    df_achados = pd.DataFrame([a.__dict__ for a in achados])
                    csv_bytes = df_achados.to_csv(sep=";", index=False).encode("utf-8-sig")
                    st.download_button(
                        "📥 Baixar Achados (CSV)",
                        data=csv_bytes,
                        file_name=f"eda_achados_{fonte_selecionada}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )


def render() -> None:
    """Renderiza a visão do DataOps Control Tower."""

    col_header1, col_header2 = st.columns(2)

    with col_header1:
        header(
            titulo="⚙️ DataOps Control Tower",
            subtitulo="Orquestração, monitoramento e data profilling (ETL e AED).",
            mostrar_botao_voltar=True,
        )

    with col_header2:
        _render_autenticacao()

    modo_atual = st.session_state.get("dataops_modo", "sandbox")
    if modo_atual == "producao":
        aviso(
            "info",
            "🟢 Modo Produção Ativo — Execuções serão persistidas na área oficial do Data warehouse.",
        )
    else:
        aviso(
            "warning",
            "🟡 Modo Sandbox Ativo — Execuções limitadas ao ambiente temporário isolado.",
        )              

    tab_etl, tab_eda = st.tabs([
            "ETL - Ingestão, Transformação, Arquitetura Medalhão e Star Schema",
            "EDA - Análise Exploratória e Qualidade dos Dados",
        ])

    with tab_etl:
        params = get_dataops_params()
        orchestrator: Optional[PipelineOrchestrator] = st.session_state.get(
            "dataops_orchestrator"
        )

        if params is None:
            _render_formulario()
        else:
            _render_painel_execucao(orchestrator)

    with tab_eda:
        _render_secao_eda()