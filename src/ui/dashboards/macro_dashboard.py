"""Dashboard Macro (D1): inteligência macroeconômica baseada nos dados BACEN SGS.

Orquestra loader -> cálculo/prep -> gráficos -> componentes e layout UI.
"""

from typing import List
import pandas as pd
import streamlit as st

from src.models.contracts import Filtros
from src.ui.charts.macro_charts import (
    fig_dispersao_ptax_ipca,
    fig_heatmap_correlacao,
    fig_ibc,
    fig_politica_monetaria,
    fig_ptax,
)
from src.ui.components.alerts import aviso, aviso_nao_causalidade
from src.ui.components.header import header
from src.ui.components.kpi import kpi
from src.ui.components.notes import nota_metodologica
from src.ui.data_loader import (
    DadosIndisponiveis,
    fonte_em_uso,
    load_dim,
    load_gold,
    ultima_atualizacao,
)
from src.ui.prep.macro_prep import (
    ciclos_selic,
    correlacao,
    correlacao_defasada,
    janelas_acima_media,
    juro_real_maximos,
    kpis_macro,
    painel_mensal,
    serie_diaria,
)
from src.ui.prep.macro_story import gerar_storytelling_macro


def render(filtros: Filtros) -> None:
    """Renderiza a view do Dashboard 1 (Macro) para os filtros fornecidos."""
    ano_ini = filtros.periodo[0][:4] if filtros.periodo and filtros.periodo[0] else "2019"
    ano_fim = filtros.periodo[1][:4] if filtros.periodo and filtros.periodo[1] else "2023"

    col_head, col_export = st.columns([3, 1])
    with col_head:
        header("Dashboard 1 — Inteligência Macroeconômica", f"Visão consolidada das variáveis BACEN ({ano_ini}–{ano_fim})")

    try:
        carga_macro = load_gold("fato_macro", filtros)
        carga_dim = load_dim("dim_indicador")
    except DadosIndisponiveis as exc:
        aviso("limitacao", str(exc))
        return

    df_macro = carga_macro.dados
    df_dim = carga_dim.dados

    if df_macro.empty or df_dim.empty:
        aviso("atencao", "Nenhum dado macroeconômico encontrado para os filtros selecionados.")
        return

    # Preparação dos dados no grão mensal e séries diárias
    painel = painel_mensal(df_macro, df_dim)
    selic_diaria = serie_diaria(df_macro, df_dim, "SELIC_META")
    ptax_diaria = serie_diaria(df_macro, df_dim, "PTAX_VENDA")

    kpis = kpis_macro(painel, selic_diaria, ptax_diaria)
    ciclos = ciclos_selic(selic_diaria)
    janelas_ptax = janelas_acima_media(ptax_diaria)
    jr_max = juro_real_maximos(painel, n=3)

    # Controles locais no topo + Download
    with col_export:
        if not painel.empty:
            csv_data = painel.to_csv(sep=";", decimal=",", encoding="utf-8-sig")
            st.download_button(
                label="📥 Exportar CSV (Mensal)",
                data=csv_data,
                file_name=f"macro_mensal_{filtros.periodo[0]}_{filtros.periodo[1]}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # Painel colapsavel de filtros
    indicadores_disp = [c for c in painel.columns if painel[c].notna().any()]
    with st.expander("🔍 Exibir filtros disponíveis", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            defasagem_k = st.slider("Defasagem Câmbio x Inflação (meses)", 0, 12, 0)
        with col_f2:
            modo_corr = st.selectbox("Modo da Correlação", ["niveis", "variacoes"], index=0)
        with col_f3:
            sel_indicadores = st.multiselect("Indicadores no Heatmap", indicadores_disp, default=indicadores_disp)

    # Abas do Dashboard
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Visão Geral",
        "Câmbio (PTAX)",
        "Atividade Econômica",
        "Correlações",
        "Dados & Metodologia",
    ])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi(
                "Selic Meta Vigente",
                kpis["selic_vigente"],
                f"{kpis['selic_delta_12m']:+.2f} p.p." if kpis["selic_delta_12m"] is not None else None,
                formato="percentual",
                ajuda="Delta referente a 12 meses anteriores",
            )
        with c2:
            kpi(
                "IPCA 12M Acumulado",
                kpis["ipca_12m"],
                f"{kpis['ipca_delta_12m']:+.2f} p.p." if kpis["ipca_delta_12m"] is not None else None,
                formato="percentual",
                ajuda="Delta referente a 12 meses anteriores",
            )
        with c3:
            kpi(
                "Juro Real Ex-Post",
                kpis["juro_real"],
                f"{kpis['juro_real_delta_12m']:+.2f} p.p." if kpis["juro_real_delta_12m"] is not None else None,
                formato="percentual",
                ajuda="Equação exata de Fisher (DM-01)",
            )
        with c4:
            kpi(
                "Dólar PTAX (Atual)",
                kpis["ptax_atual"],
                f"{kpis['ptax_delta_12m_pct']:+.1f}% vs 12m" if kpis["ptax_delta_12m_pct"] is not None else None,
                formato="moeda",
                ajuda=f"Média no período: R$ {kpis['ptax_medio']:.2f}" if kpis["ptax_medio"] else None,
            )

        st.plotly_chart(fig_politica_monetaria(painel), use_container_width=True)

    with tab2:
        st.plotly_chart(fig_ptax(ptax_diaria, kpis["ptax_medio"], janelas_ptax), use_container_width=True)
        st.plotly_chart(fig_dispersao_ptax_ipca(painel, defasagem=defasagem_k), use_container_width=True)

    with tab3:
        st.plotly_chart(fig_ibc(painel, ciclos), use_container_width=True)

    with tab4:
        cols_calc = sel_indicadores if sel_indicadores else indicadores_disp
        res_corr = correlacao(painel, colunas=cols_calc, modo=modo_corr)
        st.plotly_chart(fig_heatmap_correlacao(res_corr), use_container_width=True)

        if "PTAX_VENDA" in painel.columns and "IPCA_12M" in painel.columns:
            st.markdown("#### Matriz de Defasagem (PTAX x IPCA 12M)")
            df_def = correlacao_defasada(painel, "PTAX_VENDA", "IPCA_12M", max_defasagem=12)
            st.dataframe(df_def, use_container_width=True, hide_index=True)
            nota_metodologica("pearson", titulo="Legenda Correlação de Pearson")

    with tab5:
        st.markdown("### Base de Dados Mensal Processada")
        st.dataframe(painel, use_container_width=True)
        nota_metodologica("DM-01", titulo="Juro Real Ex-Post (Equação de Fisher)")

    # Storytelling
    story = gerar_storytelling_macro(painel, kpis, jr_max)
    with st.container(border=True):
        st.markdown(f"**📌 Contexto:** {story['contexto']}")
        st.markdown(f"**💡 Insight:** {story['insight']}")
        st.markdown(f"**🎯 Ação Recomendada:** {story['acao']}")

    st.markdown("---")
    aviso_nao_causalidade()

    # Rodapé de status
    fonte = carga_macro.fonte
    dt_upd = carga_macro.atualizado_em
    st.caption(f"Fonte dos dados em uso: **{fonte.upper()}** | Última atualização: **{dt_upd or 'N/A'}**")