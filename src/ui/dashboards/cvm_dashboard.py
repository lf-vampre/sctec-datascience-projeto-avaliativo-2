"""Dashboard Fundamentalista CVM (D2): Análise Contábil e Financeira.

Orquestra loader -> cálculo/prep -> gráficos -> componentes e layout UI.
"""

from typing import List, Optional
import pandas as pd
import streamlit as st

from src.models.contracts import Filtros
from src.ui.charts.cvm_charts import (
    fig_boxplot_ebit,
    fig_donut_setorial,
    fig_margem_evolucao,
    fig_margem_roe,
    fig_receita_agrupada,
    fig_solvencia,
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
from src.ui.prep.cvm_prep import (
    crescimento_receita,
    dispersao_margem_roe,
    distribuicao_ebit,
    distribuicao_setorial,
    kpis_cvm,
    margens_por_ano,
    painel_anual,
    solvencia,
)
from src.ui.prep.cvm_story import gerar_story_cvm


def render(filtros: Filtros) -> None:
    """Renderiza a view do Dashboard 2 (CVM / Fundamentalista) para os filtros fornecidos."""
    ano_ini_str = filtros.periodo[0][:4] if filtros.periodo and filtros.periodo[0] else "2019"
    ano_fim_str = filtros.periodo[1][:4] if filtros.periodo and filtros.periodo[1] else "2023"

    col_head, col_export = st.columns([3, 1])
    with col_head:
        header(
            "Dashboard 2 — Análise Fundamentalista & Contábil",
            f"Visão consolidada dos demonstrativos CVM ({ano_ini_str}–{ano_fim_str})",
        )

    try:
        carga_fato = load_gold("fato_demonstrativos", filtros)
        carga_dim_emp = load_dim("dim_empresa")
        carga_dim_ind = load_dim("dim_indicador")
    except DadosIndisponiveis as exc:
        aviso("limitacao", str(exc))
        return

    df_fato = carga_fato.dados
    df_emp = carga_dim_emp.dados
    df_ind = carga_dim_ind.dados

    if df_fato.empty or df_emp.empty or df_ind.empty:
        aviso("atencao", "Nenhum dado contábil encontrado para os filtros selecionados.")
        return

    # Consolida o painel no grão empresa x ano
    painel, avisos_prep = painel_anual(df_fato, df_emp, df_ind)

    if painel.empty:
        aviso("atencao", "Nenhum dado resultante para o cruzamento de empresas e indicadores.")
        return

    anos_disponiveis = sorted(painel["ano"].unique())
    ano_foco_default = anos_disponiveis[-1] if anos_disponiveis else int(ano_fim_str)
    ano_ini_default = anos_disponiveis[0] if anos_disponiveis else int(ano_ini_str)

    # Painel colapsável de filtros locais
    with st.expander("🔍 Exibir filtros disponíveis", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            ano_foco = st.selectbox("Exercício Foco (KPIs & Dispersão)", anos_disponiveis, index=len(anos_disponiveis) - 1)
        with col_f2:
            agrup_ebit = st.selectbox("Agrupamento EBIT", ["setor", "commodities"], format_func=lambda x: "Setor Analítico" if x == "setor" else "Commodities vs Serviços")
        with col_f3:
            limiar_liq = st.number_input("Limiar de Liquidez Corrente (x)", min_value=0.5, max_value=3.0, value=1.5, step=0.1)

    # Preparação de métricas com filtros locais aplicados
    kpis = kpis_cvm(painel, ano_foco)
    cresc = crescimento_receita(painel, ano_ini_default, ano_foco)
    disp = dispersao_margem_roe(painel, ano_foco)
    dist_ebit = distribuicao_ebit(painel, anos=anos_disponiveis, agrupamento=agrup_ebit)
    solv_df = solvencia(painel, ano_foco, limiar_liquidez=limiar_liq)
    dist_set = distribuicao_setorial(painel, ano_foco)
    margens = margens_por_ano(painel)

    # Botão de Exportação no topo à direita
    with col_export:
        csv_data = painel.to_csv(sep=";", decimal=",", encoding="utf-8-sig")
        st.download_button(
            label="📥 Exportar CSV (CVM)",
            data=csv_data,
            file_name=f"cvm_demonstrativos_{ano_ini_default}_{ano_foco}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Abas do Dashboard
    tab1, tab2, tab3, tab4 = st.tabs([
        "Visão Geral",
        "Rentabilidade",
        "Solvência",
        "Dados & Metodologia",
    ])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            delta_rec = f"{kpis['receita_delta_pct']:+.1f}% vs {kpis['ano_anterior']}" if kpis["receita_delta_pct"] is not None else None
            kpi(
                "Receita Líquida Total",
                kpis["receita_liquida_total"],
                delta_rec,
                formato="moeda_compacta",
                ajuda="Exclui instituições financeiras (ADR-09). Delta Like-for-Like.",
            )
        with c2:
            delta_lucro = f"{kpis['lucro_delta_pct']:+.1f}% vs {kpis['ano_anterior']}" if kpis["lucro_delta_pct"] is not None else None
            kpi(
                "Lucro Líquido Consolidado",
                kpis["lucro_liquido_total"],
                delta_lucro,
                formato="moeda_compacta",
                ajuda="Inclui todas as empresas da carteira. Delta Like-for-Like.",
            )
        with c3:
            delta_roe = f"{kpis['roe_delta_pp']:+.2f} p.p." if kpis["roe_delta_pp"] is not None else None
            kpi(
                "ROE Médio (Carteira)",
                kpis["roe_medio"],
                delta_roe,
                formato="percentual",
                ajuda=f"Média simples. Mediana: {kpis['roe_mediana']:.2f}%" if kpis["roe_mediana"] else "Empresas com PL > 0.",
            )
        with c4:
            delta_liq = f"{kpis['liquidez_delta_abs']:+.2f}x" if kpis["liquidez_delta_abs"] is not None else None
            kpi(
                "Liquidez Corrente Média",
                kpis["liquidez_corrente_media"],
                delta_liq,
                formato="numero",
                ajuda="Apenas empresas industriais/comerciais.",
            )

        col_g1, col_g2 = st.columns([3, 2])
        with col_g1:
            fig_ind, fig_fin = fig_receita_agrupada(painel)
            if fig_fin is not None:
                col_rec1, col_rec2 = st.columns(2)
                with col_rec1:
                    st.plotly_chart(fig_ind, use_container_width=True)
                with col_rec2:
                    st.plotly_chart(fig_fin, use_container_width=True)
            else:
                st.plotly_chart(fig_ind, use_container_width=True)
        with col_g2:
            st.plotly_chart(fig_donut_setorial(dist_set), use_container_width=True)

    with tab2:
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.plotly_chart(fig_margem_roe(disp), use_container_width=True)
        with col_r2:
            st.plotly_chart(fig_margem_evolucao(margens), use_container_width=True)

        st.plotly_chart(fig_boxplot_ebit(dist_ebit), use_container_width=True)

    with tab3:
        st.plotly_chart(fig_solvencia(solv_df, limiar_liquidez=limiar_liq), use_container_width=True)
        if not solv_df.empty:
            st.markdown("#### Empresas com Pontos de Atenção na Liquidez")
            st.dataframe(solv_df[solv_df["atencao_liquidez"]], use_container_width=True, hide_index=True)

    with tab4:
        if avisos_prep:
            st.markdown("#### Avisos de Qualidade e Estrutura dos Dados")
            for av in avisos_prep:
                st.caption(f"• {av}")

        painel_ind = painel[painel["comparavel_receita"]].dropna(how="all", axis=1)
        st.markdown("#### Demonstrativos Financeiros Processados (Todos os setores, excluindo setor Financeiro)")
        st.dataframe(painel_ind, use_container_width=True)

        painel_fin = painel[~painel["comparavel_receita"]].dropna(how="all", axis=1)
        painel_fin = painel_fin.drop(columns=["exportadora_commodities", "comparavel_receita"], errors="ignore")
        if not painel_fin.empty:
            st.markdown("#### Demonstrativos Financeiros Processados (Somente setor Financeiro)")
            st.dataframe(painel_fin, use_container_width=True)

        #nota_metodologica("bancos", titulo="Tratamento Contábil de Instituições Financeiras")

    # Storytelling
    story = gerar_story_cvm(kpis, cresc, disp, solv_df, dist_set, limiar_liquidez=limiar_liq)
    with st.container(border=True):
        st.markdown(f"**📌 Contexto:** {story['contexto']}")
        st.markdown(f"**💡 Insight:** {story['insight']}")
        st.markdown(f"**🎯 Ação Recomendada:** {story['acao']}")

    aviso_financeiras()
    aviso_nao_causalidade()

    # Rodapé de status
    fonte = carga_fato.fonte
    dt_upd = carga_fato.atualizado_em
    st.caption(f"Fonte dos dados em uso: **{fonte.upper()}** | Última atualização: **{dt_upd or 'N/A'}**")