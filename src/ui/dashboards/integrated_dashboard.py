"""Dashboard Integrado (D4): Visão Tríade (BACEN + B3 + CVM).

Orquestra loader -> prep -> gráficos -> componentes e layout UI.
"""

from typing import List, Optional
import pandas as pd
import streamlit as st

from src.config.settings import (
    ESTRESSE_CAMBIAL_JANELA_DIAS,
    ESTRESSE_CAMBIAL_LIMIAR_PCT,
    RANKING_PESOS_DEFAULT,
)
from src.config.universe import COMPANIES
from src.models.contracts import Filtros
from src.ui.charts.integrated_charts import (
    fig_barras_contabeis,
    fig_base100,
    fig_dispersao_ebit_retorno,
    fig_efeito_aperto,
    fig_exportadoras_estresse,
    fig_macro_cambial,
    fig_ranking_setorial,
    fig_setorial_vs_selic,
)
from src.ui.components.alerts import aviso, aviso_financeiras, aviso_nao_causalidade
from src.ui.components.header import header
from src.ui.components.kpi import kpi
from src.ui.components.notes import nota_metodologica
from src.ui.data_loader import (
    DadosIndisponiveis,
    load_dim,
    load_gold,
)
from src.ui.prep.integrated_prep import (
    dispersao_ebit_retorno,
    efeito_aperto,
    exportadoras_em_estresse,
    janelas_estresse_cambial,
    kpis_triade,
    margem_ebit_exportadoras,
    painel_macro_cambial,
    ranking_setorial,
    retorno_setorial_vs_selic,
)
from src.ui.prep.integrated_story import gerar_story_integrada
from src.ui.prep.market_prep import _preparar_pivots, calcular_base100


def render(filtros: Filtros) -> None:
    """Renderiza o Dashboard 4 (Integrado / Tríade) para os filtros fornecidos."""
    ano_ini_str = filtros.periodo[0][:4] if filtros.periodo and filtros.periodo[0] else "2019"
    ano_fim_str = filtros.periodo[1][:4] if filtros.periodo and filtros.periodo[1] else "2023"

    col_head, col_export = st.columns([3, 1])
    with col_head:
        header(
            "Dashboard 4 — Visão Integrada da Tríade",
            f"Cruzamento analítico BACEN, B3 e CVM ({ano_ini_str}–{ano_fim_str})",
        )

    try:
        carga_macro = load_gold("fato_macro", filtros)
        carga_cot = load_gold("fato_cotacoes", filtros)
        carga_cvm = load_gold("fato_demonstrativos", filtros)
        carga_dim_emp = load_dim("dim_empresa")
        carga_dim_ind = load_dim("dim_indicador")
    except DadosIndisponiveis as exc:
        aviso("limitacao", str(exc))
        return

    df_macro = carga_macro.dados
    df_cot = carga_cot.dados
    df_cvm = carga_cvm.dados
    df_emp = carga_dim_emp.dados
    df_ind = carga_dim_ind.dados

    if df_macro.empty or df_cot.empty or df_cvm.empty or df_emp.empty or df_ind.empty:
        aviso("atencao", "Dados insuficientes em uma das fontes para a visão integrada.")
        return

    from src.ui.prep.cvm_prep import painel_anual
    painel_cvm_base, avisos_cvm = painel_anual(df_cvm, df_emp, df_ind)

    if painel_cvm_base.empty:
        aviso("atencao", "Nenhum dado contábil resultante para os filtros aplicados.")
        return

    anos_disponiveis = sorted(painel_cvm_base["ano"].unique())
    ano_foco_default = anos_disponiveis[-1] if anos_disponiveis else int(ano_fim_str)
    ano_base_default = anos_disponiveis[0] if anos_disponiveis else int(ano_ini_str)

    # Painel de Filtros Locais
    with st.expander("🔍 Exibir filtros Locais disponíveis. Filtros Globais, acesse o sidebar!", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            ano_foco = st.selectbox("Exercício Foco (KPIs & Contábil)", anos_disponiveis, index=len(anos_disponiveis) - 1)
            modo_disp = st.radio("Modo Dispersão EBIT vs Retorno", ["Ano de Foco", "Período Completo"], index=0)
        with col_f2:
            janela_est = st.number_input("Janela Estresse Cambial (Dias)", min_value=5, max_value=90, value=ESTRESSE_CAMBIAL_JANELA_DIAS, step=5)
            limiar_est = st.number_input("Limiar Alta PTAX (%)", min_value=1.0, max_value=20.0, value=ESTRESSE_CAMBIAL_LIMIAR_PCT, step=0.5)
        with col_f3:
            w_bolsa = st.slider("Peso Pilar Bolsa", 0.0, 3.0, RANKING_PESOS_DEFAULT["retorno_bolsa"], step=0.5)
            w_macro = st.slider("Peso Pilar Resiliência Macro", 0.0, 3.0, RANKING_PESOS_DEFAULT["resiliencia_macro"], step=0.5)
            w_solidez = st.slider("Peso Pilar Solidez Contábil", 0.0, 3.0, RANKING_PESOS_DEFAULT["solidez_contabil"], step=0.5)

    pesos_custom = {"retorno_bolsa": w_bolsa, "resiliencia_macro": w_macro, "solidez_contabil": w_solidez}

    # Processamento Prep
    kpis, avisos_kpi = kpis_triade(df_macro, df_ind, painel_cvm_base, ano_foco)
    p_macro = painel_macro_cambial(df_macro, df_ind)

    p_close, _, _ = _preparar_pivots(df_cot, df_emp)
    base100_df, _ = calcular_base100(p_close)

    t_setorial, avisos_set = retorno_setorial_vs_selic(df_macro, df_ind, df_cot, df_emp)

    if modo_disp == "Ano de Foco":
        df_disp, _ = dispersao_ebit_retorno(painel_cvm_base, df_cot, df_emp, ano_foco=ano_foco)
    else:
        df_disp, _ = dispersao_ebit_retorno(painel_cvm_base, df_cot, df_emp, periodo=(ano_base_default, ano_foco))

    t_aperto, avisos_aperto = efeito_aperto(painel_cvm_base, df_macro, df_ind, ano_base=ano_base_default)

    from src.ui.prep.macro_prep import serie_diaria
    s_ptax = serie_diaria(df_macro, df_ind, "PTAX_VENDA")
    janelas_est = janelas_estresse_cambial(s_ptax, janela_dias=int(janela_est), limiar_pct=float(limiar_est))
    df_est_ret, _ = exportadoras_em_estresse(df_cot, df_emp, janelas_est)
    df_est_margem, _ = margem_ebit_exportadoras(painel_cvm_base, df_macro, df_ind)

    df_rank, avisos_rank = ranking_setorial(painel_cvm_base, df_cot, df_emp, df_macro, df_ind, pesos=pesos_custom)

    # Botão de Exportação no topo à direita
    with col_export:
        csv_data = painel_cvm_base.to_csv(sep=";", decimal=",", encoding="utf-8-sig")
        st.download_button(
            label="📥 Exportar CSV (Tríade)",
            data=csv_data,
            file_name=f"triade_integrada_{ano_base_default}_{ano_foco}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Abas do Dashboard Integrado
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Visão Integrada",
        "Contabilidade e Mercado",
        "Juros e Setores",
        "Câmbio e Exportadoras",
        "Ranking Setorial",
        "Dados e Metodologia",
    ])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            delta_s = f"{kpis['selic_delta_12m']:+.2f} p.p." if kpis.get("selic_delta_12m") is not None else None
            kpi("Selic Meta Vigente", kpis.get("selic_vigente"), delta_s, formato="percentual")
        with c2:
            delta_i = f"{kpis['ipca_delta_12m']:+.2f} p.p." if kpis.get("ipca_delta_12m") is not None else None
            kpi("IPCA 12M Acumulado", kpis.get("ipca_12m"), delta_i, formato="percentual")
        with c3:
            delta_r = f"{kpis['receita_delta_pct']:+.1f}% vs {ano_foco-1}" if kpis.get("receita_delta_pct") is not None else None
            kpi("Receita Consolidada", kpis.get("receita_consolidada"), delta_r, formato="moeda_compacta", ajuda="Exclui instituições financeiras (ADR-09).")
        with c4:
            delta_l = f"{kpis['lucro_delta_pct']:+.1f}% vs {ano_foco-1}" if kpis.get("lucro_delta_pct") is not None else None
            kpi("Lucro Consolidado", kpis.get("lucro_consolidado"), delta_l, formato="moeda_compacta", ajuda="Inclui todas as empresas da carteira.")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(fig_macro_cambial(p_macro), use_container_width=True)
        with col_g2:
            st.plotly_chart(fig_base100(base100_df), use_container_width=True)

    with tab2:
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.plotly_chart(fig_barras_contabeis(painel_cvm_base, ano_foco), use_container_width=True)
        with col_r2:
            st.plotly_chart(fig_dispersao_ebit_retorno(df_disp), use_container_width=True)

    with tab3:
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.plotly_chart(fig_setorial_vs_selic(t_setorial), use_container_width=True)
        with col_s2:
            st.plotly_chart(fig_efeito_aperto(t_aperto), use_container_width=True)

    with tab4:
        st.plotly_chart(fig_exportadoras_estresse(df_est_ret, df_est_margem), use_container_width=True)

    with tab5:
        st.plotly_chart(fig_ranking_setorial(df_rank), use_container_width=True)

    with tab6:
        st.markdown("#### Notas Metodológicas e Limitações da Tríade")
        #nota_metodologica("bancos", titulo="Regras de Comparabilidade e Instituições Financeiras")
        st.caption("• O 1º ano do recorte histórico utiliza como base o 1º pregão disponível e é sinalizado como parcial.")
        st.caption("• O ranking setorial representa um índice descritivo ponderado, cujos pesos podem ser parametrizados nos filtros locais.")

        st.markdown("### Base Macroeconômica Mensal (BACEN)")
        st.dataframe(p_macro, use_container_width=True)

        painel_ind = painel_cvm_base[painel_cvm_base["comparavel_receita"]].dropna(how="all", axis=1)
        st.markdown("#### Demonstrativos Financeiros Processados (Todos os setores, excluindo setor Financeiro)")
        st.dataframe(painel_ind, use_container_width=True)

        painel_fin = painel_cvm_base[~painel_cvm_base["comparavel_receita"]].dropna(how="all", axis=1)
        painel_fin = painel_fin.drop(columns=["exportadora_commodities", "comparavel_receita", "setor_analitico"], errors="ignore")
        if not painel_fin.empty:
            st.markdown("#### Demonstrativos Financeiros Processados (Somente setor Financeiro)")
            st.dataframe(painel_fin, use_container_width=True)

        st.markdown("### Cotações Filtradas da Camada Ouro (B3)")
        st.dataframe(df_cot, use_container_width=True)

        #st.markdown("#### Base Integrada de Demonstrativos Processados")
        #st.dataframe(painel_cvm_base, use_container_width=True)

    # Storytelling
    story = gerar_story_integrada(kpis, t_aperto, t_setorial, df_est_ret, df_rank)
    with st.container(border=True):
        st.markdown(f"**📌 Contexto:** {story['contexto']}")
        st.markdown(f"**💡 Insight:** {story['insight']}")
        st.markdown(f"**🎯 Ação Recomendada:** {story['acao']}")

    aviso_financeiras()
    aviso_nao_causalidade()

    # Rodapé de status
    fonte = carga_macro.fonte
    dt_upd = carga_macro.atualizado_em
    st.caption(f"Fonte dos dados em uso: **{fonte.upper()}** | Última atualização: **{dt_upd or 'N/A'}**")