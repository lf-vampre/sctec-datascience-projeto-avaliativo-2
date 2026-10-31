"""Dashboard de Mercado e Risco B3 (D3).

Orquestra loader -> cálculo/prep -> gráficos -> componentes e layout UI.
"""

from typing import List, Optional
import pandas as pd
import streamlit as st

from src.config.methodology import METHODOLOGY_BANCOS, METHODOLOGY_SHARPE
from src.config.settings import SERIE_RISCO_LIVRE
from src.models.contracts import Filtros
from src.ui.charts.market_charts import (
    fig_base100,
    fig_drawdown,
    fig_hist_retornos,
    fig_risco_retorno,
    fig_sma,
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
from src.ui.prep.market_prep import (
    _preparar_pivots,
    calcular_base100,
    distribuicao_retornos,
    extrair_rf_diaria,
    kpis_mercado,
    ranking_resiliencia,
    serie_drawdown,
    serie_sma,
    tabela_risco_retorno,
)
from src.ui.prep.market_story import gerar_story_mercado
from src.utils.formatting import format_percent


def render(filtros: Filtros) -> None:
    """Renderiza a view do Dashboard 3 (Mercado e Risco B3) para os filtros fornecidos."""
    ano_ini = filtros.periodo[0][:4] if filtros.periodo and filtros.periodo[0] else "2019"
    ano_fim = filtros.periodo[1][:4] if filtros.periodo and filtros.periodo[1] else "2023"

    col_head, col_export = st.columns([3, 1])
    with col_head:
        header(
            "Dashboard 3 — Mercado e Risco (B3)",
            f"Visão consolidada do mercado financeiro e métricas de risco ({ano_ini}–{ano_fim})",
        )

    try:
        carga_cotacoes = load_gold("fato_cotacoes", filtros)
        carga_emp = load_dim("dim_empresa")
        carga_ind = load_dim("dim_indicador")

        filtros_rf = Filtros(
            periodo=filtros.periodo,
            tickers=(),
            setores=(),
            indicadores_bacen=(SERIE_RISCO_LIVRE,),
        )
        carga_macro = load_gold("fato_macro", filtros_rf)
    except DadosIndisponiveis as exc:
        aviso("limitacao", str(exc))
        return

    df_cotacoes = carga_cotacoes.dados
    df_empresa = carga_emp.dados
    df_indicador = carga_ind.dados
    df_macro = carga_macro.dados

    if df_cotacoes.empty or df_empresa.empty:
        aviso("atencao", "Nenhum dado de cotações encontrado para os filtros selecionados.")
        return

    pivot_close, pivot_vol_fin, pivot_retornos = _preparar_pivots(df_cotacoes, df_empresa)

    if pivot_close.empty:
        aviso("atencao", "Dados insuficientes para estruturação das séries temporais dos ativos.")
        return

    rf_diaria, avisos_rf = extrair_rf_diaria(df_macro, df_indicador, pivot_close.index)
    base100_df, avisos_b100 = calcular_base100(pivot_close)
    tab_rr = tabela_risco_retorno(pivot_close, pivot_vol_fin, pivot_retornos, rf_diaria)
    kpis = kpis_mercado(tab_rr, pivot_close)

    # Exportação CSV no topo
    with col_export:
        if not tab_rr.empty:
            csv_data = tab_rr.to_csv(sep=";", decimal=",", encoding="utf-8-sig", index=False)
            st.download_button(
                label="📥 Exportar CSV (Risco/Retorno)",
                data=csv_data,
                file_name=f"mercado_risco_retorno_{filtros.periodo[0]}_{filtros.periodo[1]}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # Avisos informativos se houver ressalvas de dados
    for av in avisos_rf + avisos_b100:
        aviso("atencao", av)

    tickers_disponiveis = list(pivot_close.columns)

    # Filtros Locais em Expander
    with st.expander("🔍 Exibir filtros disponíveis", expanded=False):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            sel_destaque = st.selectbox(
                "Destaque na Base 100",
                options=["Nenhum"] + tickers_disponiveis,
                index=0,
            )
        with f2:
            sel_hist_ticker = st.selectbox(
                "Distribuição dos retornos (Histograma) / Ativo:",
                options=["Carteira"] + tickers_disponiveis,
                index=0,
            )
        with f3:
            sel_dd_tickers = st.multiselect(
                "Ativos no Drawdown",
                options=["Carteira"] + tickers_disponiveis,
                default=["Carteira"] + tickers_disponiveis[: min(3, len(tickers_disponiveis))],
            )
        with f4:
            sel_sma_ticker = st.selectbox(
                "Ativo para Análise de Tendência (SMA)",
                options=tickers_disponiveis,
                index=0,
            )

    # Abas do Dashboard
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Rentabilidade",
        "Risco e retorno",
        "Distribuição dos retornos",
        "Drawdown",
        "Tendência",
        "Dados e metodologia",
    ])

    # Aba 1 — Rentabilidade
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi(
                "Retorno Médio da Carteira",
                kpis["retorno_medio_carteira"] * 100.0 if kpis["retorno_medio_carteira"] is not None else None,
                f"{kpis['retorno_delta_pp']:+.2f} p.p." if kpis["retorno_delta_pp"] is not None else None,
                formato="percentual",
                ajuda="Média simples dos retornos acumulados dos ativos (delta vs ano anterior)",
            )
        with c2:
            kpi(
                f"Destaque: {kpis['ativo_destaque']}",
                kpis["ativo_destaque_retorno"] * 100.0 if kpis["ativo_destaque_retorno"] is not None else None,
                f"{kpis['ativo_destaque_delta_pp']:+.2f} p.p." if kpis.get("ativo_destaque_delta_pp") is not None else None,
                formato="percentual",
                ajuda="Ativo com maior retorno acumulado (delta vs ano anterior)",
            )
        with c3:
            kpi(
                f"Menor Perf.: {kpis['ativo_pior']}",
                kpis["ativo_pior_retorno"] * 100.0 if kpis["ativo_pior_retorno"] is not None else None,
                f"{kpis['ativo_pior_delta_pp']:+.2f} p.p." if kpis.get("ativo_pior_delta_pp") is not None else None,
                formato="percentual",
                ajuda="Ativo com menor retorno acumulado (delta vs ano anterior)",
            )
        with c4:
            kpi(
                "Volatilidade Anualizada Média",
                kpis["volatilidade_media"] * 100.0 if kpis["volatilidade_media"] is not None else None,
                f"{kpis['volatilidade_delta_pp']:+.2f} p.p." if kpis["volatilidade_delta_pp"] is not None else None,
                formato="percentual",
                ajuda="Média simples da volatilidade histórica (delta vs ano anterior)",
            )

        destacar_ativo = None if sel_destaque == "Nenhum" else sel_destaque
        st.plotly_chart(fig_base100(base100_df, destacar=destacar_ativo), use_container_width=True)

    # Aba 2 — Risco e Retorno
    with tab2:
        st.plotly_chart(fig_risco_retorno(tab_rr), use_container_width=True)
        st.markdown("### Tabela de Risco e Retorno Ajustado")

        df_exibir_rr = tab_rr.copy()
        for col in ["retorno_acumulado", "volatilidade_anualizada", "drawdown_maximo", "p5_retorno_diario"]:
            df_exibir_rr[col] = df_exibir_rr[col].apply(
                lambda v: f"{v*100.0:.2f}%".replace(".", ",") if pd.notna(v) else "N/A"
            )
        df_exibir_rr["sharpe"] = df_exibir_rr["sharpe"].apply(
            lambda v: f"{v:.2f}".replace(".", ",") if pd.notna(v) else "—"
        )
        df_exibir_rr["volume_medio_diario"] = df_exibir_rr["volume_medio_diario"].apply(
            lambda v: f"R$ {v/1e6:,.2f} M".replace(",", "X").replace(".", ",").replace("X", ".")
            if pd.notna(v)
            else "N/A"
        )

        st.dataframe(df_exibir_rr, use_container_width=True, hide_index=True)

    # Aba 3 — Distribuição dos Retornos
    with tab3:
        target_hist = None if sel_hist_ticker == "Carteira" else sel_hist_ticker
        s_ret, stats_hist = distribuicao_retornos(pivot_retornos, target_hist)

        

        st.markdown("##### Métricas Estatísticas da Distribuição")
        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
        with col_s1:
            st.metric("Assimetria (Skew)", f"{stats_hist.get('assimetria', 0.0):.2f}".replace(".", ","))
        with col_s2:
            st.metric("Curtose (Kurtosis)", f"{stats_hist.get('curtose', 0.0):.2f}".replace(".", ","))
        with col_s3:
            p5_val = stats_hist.get("p5", 0.0)
            st.metric("Percentil 5% (Cauda)", f"{p5_val*100.0:.2f}%".replace(".", ","))
        with col_s4:
            st.metric("Retorno Mínimo", f"{stats_hist.get('minimo', 0.0)*100.0:.2f}%".replace(".", ","))
        with col_s5:
            st.metric("Retorno Máximo", f"{stats_hist.get('maximo', 0.0)*100.0:.2f}%".replace(".", ","))

        st.plotly_chart(
            fig_hist_retornos(s_ret, stats_hist, sel_hist_ticker),
            use_container_width=True,
        )    

    # Aba 4 — Drawdown
    with tab4:
        df_dd = serie_drawdown(pivot_close)
        st.plotly_chart(fig_drawdown(df_dd, sel_dd_tickers), use_container_width=True)

        st.markdown("### Ranking de Resiliência (Menor Drawdown Máximo em Módulo)")
        tab_resil = ranking_resiliencia(tab_rr)

        if not tab_resil.empty:
            df_resil_fmt = tab_resil[["ticker", "drawdown_maximo", "volatilidade_anualizada", "sharpe"]].copy()
            df_resil_fmt["drawdown_maximo"] = df_resil_fmt["drawdown_maximo"].apply(
                lambda v: f"{v*100.0:.2f}%".replace(".", ",") if pd.notna(v) else "N/A"
            )
            df_resil_fmt["volatilidade_anualizada"] = df_resil_fmt["volatilidade_anualizada"].apply(
                lambda v: f"{v*100.0:.2f}%".replace(".", ",") if pd.notna(v) else "N/A"
            )
            df_resil_fmt["sharpe"] = df_resil_fmt["sharpe"].apply(
                lambda v: f"{v:.2f}".replace(".", ",") if pd.notna(v) else "—"
            )
            st.dataframe(df_resil_fmt, use_container_width=True, hide_index=True)

    # Aba 5 — Tendência (SMA)
    with tab5:
        df_sma_data = serie_sma(df_cotacoes, df_empresa, sel_sma_ticker)
        st.plotly_chart(fig_sma(df_sma_data, sel_sma_ticker), use_container_width=True)

    # Aba 6 — Dados & Metodologia
    with tab6:
        st.markdown("### Cotações Filtradas da Camada Ouro")
        st.dataframe(df_cotacoes, use_container_width=True)

        st.caption(f"Limitação de Volume: O volume financeiro diário é aproximado via fecho × quantidade (Yahoo Finance).")
        st.caption("Aviso de Desempenho: Rentabilidade passada não representa garantia de rentabilidade futura.")
        nota_metodologica("DM-02", titulo="Cálculo do Índice de Sharpe e Taxa Livre de Risco")

    # Storytelling posicionada abaixo das abas
    df_sma_story = serie_sma(df_cotacoes, df_empresa, sel_sma_ticker) if sel_sma_ticker else None
    story = gerar_story_mercado(kpis, tab_rr, df_sma_story, sel_sma_ticker)

    with st.container(border=True):
        st.markdown(f"**📌 Contexto:** {story['contexto']}")
        st.markdown(f"**💡 Insight:** {story['insight']}")
        st.markdown(f"**🎯 Ação Informativa:** {story['acao']}")

    #st.markdown("---")

    # Rodapé Global
    aviso_nao_causalidade()

    fonte = carga_cotacoes.fonte
    dt_upd = carga_cotacoes.atualizado_em
    st.caption(f"Fonte dos dados em uso: **{fonte.upper()}** | Última atualização: **{dt_upd or 'N/A'}**")