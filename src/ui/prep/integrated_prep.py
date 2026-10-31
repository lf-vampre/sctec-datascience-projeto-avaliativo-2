"""Funções puras de preparação de dados para o Dashboard Integrado (D4 - Tríade)."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.etl.warehouse.metrics_calculator import (
    retorno_acumulado,
    retorno_anual,
    retorno_setorial_anual,
    selic_media_anual,
)
from src.ui.prep.cvm_prep import kpis_cvm
from src.ui.prep.macro_prep import kpis_macro, painel_mensal, serie_diaria
from src.ui.prep.market_prep import _preparar_pivots


def universo_triade(dim_empresa: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Filtra empresas com cobertura CVM e B3 simultânea (tem_cvm AND tem_b3)."""
    avisos: List[str] = []
    if dim_empresa.empty:
        return pd.DataFrame(), ["dim_empresa está vazia."]

    has_cvm = "tem_cvm" in dim_empresa.columns
    has_b3 = "tem_b3" in dim_empresa.columns

    if not (has_cvm and has_b3):
        return dim_empresa.copy(), avisos

    mask_triade = dim_empresa["tem_cvm"] & dim_empresa["tem_b3"]
    df_triade = dim_empresa[mask_triade].copy()

    excluidas = dim_empresa[~mask_triade]
    if not excluidas.empty:
        tickers_excluidos = excluidas["ticker"].unique().tolist()
        avisos.append(
            f"Empresas excluídas do universo Tríade por falta de cobertura CVM/B3: {', '.join(tickers_excluidos)}"
        )

    return df_triade, avisos


def kpis_triade(
    fato_macro: pd.DataFrame,
    dim_indicador: pd.DataFrame,
    painel_cvm: pd.DataFrame,
    ano_foco: int,
) -> Tuple[Dict[str, Any], List[str]]:
    """Calcula KPIs agregados da Tríade (Macro + CVM Carteira) para o exercício de foco."""
    avisos: List[str] = []
    res: Dict[str, Any] = {
        "selic_vigente": None,
        "selic_delta_12m": None,
        "ipca_12m": None,
        "ipca_delta_12m": None,
        "receita_consolidada": None,
        "receita_delta_pct": None,
        "lucro_consolidado": None,
        "lucro_delta_pct": None,
        "n_empresas_receita": 0,
        "n_empresas_lucro": 0,
    }

    # KPIs Macro
    p_mensal = painel_mensal(fato_macro, dim_indicador)
    s_selic = serie_diaria(fato_macro, dim_indicador, "SELIC_META")
    s_ptax = serie_diaria(fato_macro, dim_indicador, "PTAX_VENDA")

    km = kpis_macro(p_mensal, s_selic, s_ptax)
    res["selic_vigente"] = km.get("selic_vigente")
    res["selic_delta_12m"] = km.get("selic_delta_12m")
    res["ipca_12m"] = km.get("ipca_12m")
    res["ipca_delta_12m"] = km.get("ipca_delta_12m")

    # KPIs CVM
    kc = kpis_cvm(painel_cvm, ano_foco)
    res["receita_consolidada"] = kc.get("receita_liquida_total")
    res["receita_delta_pct"] = kc.get("receita_delta_pct")
    res["lucro_consolidado"] = kc.get("lucro_liquido_total")
    res["lucro_delta_pct"] = kc.get("lucro_delta_pct")
    res["n_empresas_receita"] = kc.get("n_empresas_receita", 0)
    res["n_empresas_lucro"] = kc.get("n_empresas_lucro", 0)

    if not painel_cvm.empty and "tipo_plano" in painel_cvm.columns:
        df_curr = painel_cvm[painel_cvm["ano"] == ano_foco]
        fin_count = len(df_curr[df_curr["tipo_plano"] == "financeira"])
        if fin_count > 0:
            avisos.append(
                f"KPI de Receita Consolidada exclui {fin_count} instituição(ões) financeira(s) (ADR-09). Lucro Líquido inclui todas."
            )

    return res, avisos


def painel_macro_cambial(
    fato_macro: pd.DataFrame, dim_indicador: pd.DataFrame
) -> pd.DataFrame:
    """Consolida os indicadores Selic Meta, IPCA 12M e PTAX no grão mensal."""
    return painel_mensal(fato_macro, dim_indicador)


def retorno_setorial_vs_selic(
    fato_macro: pd.DataFrame,
    dim_indicador: pd.DataFrame,
    fato_cotacoes: pd.DataFrame,
    dim_empresa: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    """Tabela ano x setor com retorno setorial anual B3, Selic média anual e IPCA 12M de dezembro."""
    avisos: List[str] = []
    colunas = [
        "ano",
        "setor_analitico",
        "retorno_setorial_pct",
        "selic_media_pct",
        "ipca_12m_dec_pct",
        "flag_parcial",
    ]
    df_vazio = pd.DataFrame(columns=colunas)

    if fato_cotacoes.empty or dim_empresa.empty:
        return df_vazio, ["Dados de cotação ou empresa ausentes."]

    emp_triade, avisos_u = universo_triade(dim_empresa)
    avisos.extend(avisos_u)

    if emp_triade.empty:
        return df_vazio, avisos

    pivot_close, _, _ = _preparar_pivots(fato_cotacoes, emp_triade)
    if pivot_close.empty or not isinstance(pivot_close.index, pd.DatetimeIndex):
        return df_vazio, avisos

    years = sorted(pivot_close.index.year.unique())
    if not years:
        return df_vazio, avisos

    df_ret_anual = pd.DataFrame()
    for ticker in pivot_close.columns:
        s_close = pivot_close[ticker].dropna()
        if not s_close.empty:
            df_ret_anual[ticker] = retorno_anual(s_close)

    primeiro_ano = years[0]
    avisos.append(
        f"O primeiro ano da janela ({primeiro_ano}) utiliza como base de retorno o 1º pregão disponível, sendo classificado como parcial."
    )

    s_selic = serie_diaria(fato_macro, dim_indicador, "SELIC_META")
    p_mensal = painel_mensal(fato_macro, dim_indicador)

    mapa_setor = emp_triade.set_index("ticker")["setor_analitico"].to_dict()
    setores = sorted(list(set(mapa_setor.values())))
    linhas = []

    for yr in years:
        if not s_selic.empty and isinstance(s_selic.index, pd.DatetimeIndex):
            selic_yr = s_selic[s_selic.index.year == yr]
            selic_med = selic_media_anual(selic_yr)
        else:
            selic_med = np.nan

        ipca_dec = np.nan
        if not p_mensal.empty and "IPCA_12M" in p_mensal.columns:
            m_yr = [idx for idx in p_mensal.index if str(idx).startswith(str(yr))]
            if m_yr:
                m_dec = [m for m in m_yr if m.endswith("-12")]
                chosen_m = m_dec[0] if m_dec else m_yr[-1]
                ipca_dec = float(p_mensal.loc[chosen_m, "IPCA_12M"])

        is_parcial = yr == primeiro_ano

        for setor in setores:
            tickers_setor = [t for t, s in mapa_setor.items() if s == setor]
            if not df_ret_anual.empty and yr in df_ret_anual.index:
                ret_set = retorno_setorial_anual(df_ret_anual.loc[[yr]], tickers_setor)
                ret_val = float(ret_set.iloc[0]) if not ret_set.empty else np.nan
            else:
                ret_val = np.nan

            linhas.append({
                "ano": yr,
                "setor_analitico": setor,
                "retorno_setorial_pct": ret_val * 100.0 if pd.notna(ret_val) else np.nan,
                "selic_media_pct": selic_med,
                "ipca_12m_dec_pct": ipca_dec,
                "flag_parcial": is_parcial,
            })

    df_res = pd.DataFrame(linhas)
    return df_res, avisos


def dispersao_ebit_retorno(
    painel_cvm: pd.DataFrame,
    fato_cotacoes: pd.DataFrame,
    dim_empresa: pd.DataFrame,
    ano_foco: Optional[int] = None,
    periodo: Optional[Tuple[int, int]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """Gera dados de dispersão Margem EBIT x Retorno Acumulado por empresa industrial da Tríade."""
    avisos: List[str] = []
    cols = [
        "ticker",
        "setor_analitico",
        "exportadora_commodities",
        "receita_liquida",
        "margem_ebit",
        "retorno_acumulado_pct",
    ]
    df_vazio = pd.DataFrame(columns=cols)

    if painel_cvm.empty or fato_cotacoes.empty or dim_empresa.empty:
        return df_vazio, ["Dados insuficientes para dispersão."]

    emp_triade, avisos_u = universo_triade(dim_empresa)
    avisos.extend(avisos_u)

    if emp_triade.empty:
        return df_vazio, avisos

    if "tipo_plano" in emp_triade.columns:
        emp_ind = emp_triade[emp_triade["tipo_plano"] != "financeira"]
    else:
        emp_ind = emp_triade

    if emp_ind.empty:
        return df_vazio, avisos

    pivot_close, _, _ = _preparar_pivots(fato_cotacoes, emp_ind)
    if pivot_close.empty or not isinstance(pivot_close.index, pd.DatetimeIndex):
        return df_vazio, avisos

    if ano_foco is not None:
        p_close_sub = pivot_close[pivot_close.index.year == ano_foco]
        cvm_sub = painel_cvm[
            (painel_cvm["ano"] == ano_foco)
            & (painel_cvm["ticker"].isin(emp_ind["ticker"]))
            & (
                painel_cvm["comparavel_receita"]
                if "comparavel_receita" in painel_cvm.columns
                else True
            )
        ]
    elif periodo is not None:
        p_close_sub = pivot_close[
            (pivot_close.index.year >= periodo[0])
            & (pivot_close.index.year <= periodo[1])
        ]
        cvm_sub = painel_cvm[
            (painel_cvm["ano"] >= periodo[0])
            & (painel_cvm["ano"] <= periodo[1])
            & (painel_cvm["ticker"].isin(emp_ind["ticker"]))
            & (
                painel_cvm["comparavel_receita"]
                if "comparavel_receita" in painel_cvm.columns
                else True
            )
        ]
    else:
        p_close_sub = pivot_close
        cvm_sub = painel_cvm[
            (painel_cvm["ticker"].isin(emp_ind["ticker"]))
            & (
                painel_cvm["comparavel_receita"]
                if "comparavel_receita" in painel_cvm.columns
                else True
            )
        ]

    if p_close_sub.empty or cvm_sub.empty:
        return df_vazio, avisos

    cvm_agg = (
        cvm_sub.groupby("ticker")
        .agg({
            "setor_analitico": "first",
            "exportadora_commodities": "first",
            "RECEITA_LIQUIDA": "mean" if periodo is not None else "last",
            "MARGEM_EBIT": "mean" if periodo is not None else "last",
        })
        .reset_index()
    )

    linhas = []
    for _, row in cvm_agg.iterrows():
        t = row["ticker"]
        if t not in p_close_sub.columns:
            continue
        s_c = p_close_sub[t].dropna()
        if s_c.empty:
            continue

        ret_s = retorno_acumulado(s_c)
        ret_val = float(ret_s.iloc[-1]) if not ret_s.empty else np.nan

        linhas.append({
            "ticker": t,
            "setor_analitico": row["setor_analitico"],
            "exportadora_commodities": bool(row["exportadora_commodities"]),
            "receita_liquida": (
                float(row["RECEITA_LIQUIDA"])
                if pd.notna(row["RECEITA_LIQUIDA"])
                else np.nan
            ),
            "margem_ebit": (
                float(row["MARGEM_EBIT"])
                if pd.notna(row["MARGEM_EBIT"])
                else np.nan
            ),
            "retorno_acumulado_pct": (
                ret_val * 100.0 if pd.notna(ret_val) else np.nan
            ),
        })

    df_res = pd.DataFrame(linhas)
    return df_res, avisos