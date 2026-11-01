"""Funções puras de preparação de dados para o Dashboard Integrado (D4 - Tríade)."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config.settings import (
    ESTRESSE_CAMBIAL_JANELA_DIAS,
    ESTRESSE_CAMBIAL_LIMIAR_PCT,
    RANKING_PESOS_DEFAULT,
)
from src.etl.warehouse.metrics_calculator import (
    base100 as calc_base100,
    drawdown_maximo,
    retorno_acumulado,
    retorno_anual,
    retorno_setorial_anual,
    selic_media_anual,
    sharpe,
)
from src.ui.prep.cvm_prep import kpis_cvm
from src.ui.prep.macro_prep import kpis_macro, painel_mensal, serie_diaria
from src.ui.prep.market_prep import _preparar_pivots, extrair_rf_diaria


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

    p_mensal = painel_mensal(fato_macro, dim_indicador)
    s_selic = serie_diaria(fato_macro, dim_indicador, "SELIC_META")
    s_ptax = serie_diaria(fato_macro, dim_indicador, "PTAX_VENDA")

    km = kpis_macro(p_mensal, s_selic, s_ptax)
    res["selic_vigente"] = km.get("selic_vigente")
    res["selic_delta_12m"] = km.get("selic_delta_12m")
    res["ipca_12m"] = km.get("ipca_12m")
    res["ipca_delta_12m"] = km.get("ipca_delta_12m")

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


# ------------------------------------------------------------------------------
# Pergunta 1 — Apertos de Juros 
# ------------------------------------------------------------------------------

def efeito_aperto(
    painel_cvm: pd.DataFrame,
    fato_macro: pd.DataFrame,
    dim_indicador: pd.DataFrame,
    ano_base: int = 2021,
) -> Tuple[pd.DataFrame, List[str]]:
    """Calcula Despesa Financeira, Lucro Líquido e Alavancagem agregados das empresas industriais com base 100."""
    avisos: List[str] = []
    cols = [
        "ano",
        "despesa_financeira_total",
        "despesa_financeira_b100",
        "lucro_liquido_total",
        "lucro_liquido_b100",
        "alavancagem_media",
        "selic_media_anual",
    ]
    df_vazio = pd.DataFrame(columns=cols)

    if painel_cvm.empty:
        return df_vazio, ["Painel CVM está vazio."]

    # Filtra apenas empresas industriais (comparavel_receita = True)
    df_ind = painel_cvm[
        painel_cvm["comparavel_receita"] if "comparavel_receita" in painel_cvm.columns else (painel_cvm["tipo_plano"] != "financeira")
    ].copy()

    if df_ind.empty:
        return df_vazio, ["Nenhuma empresa industrial encontrada no painel CVM."]

    col_desp = (
        "DESP_FINANCEIRAS"
        if "DESP_FINANCEIRAS" in df_ind.columns
        else ("DESPESAS_FINANCEIRAS" if "DESPESAS_FINANCEIRAS" in df_ind.columns else "DESPESA_FINANCEIRA")
    )
    if col_desp not in df_ind.columns:
        df_ind[col_desp] = np.nan

    s_selic = serie_diaria(fato_macro, dim_indicador, "SELIC_META")

    anos = sorted(df_ind["ano"].unique())
    linhas = []

    for yr in anos:
        sub_yr = df_ind[df_ind["ano"] == yr]
        desp_tot = float(sub_yr[col_desp].sum(min_count=1))
        lucro_tot = float(sub_yr["LUCRO_LIQUIDO"].sum(min_count=1))

        # Alavancagem = Dívida Líquida / PL
        alavancagens = []
        for _, row in sub_yr.iterrows():
            dl = row.get("DIVIDA_LIQUIDA", np.nan)
            pl = row.get("PATRIMONIO_LIQUIDO", np.nan)
            if pd.notna(dl) and pd.notna(pl):
                if pl <= 0:
                    avisos.append(
                        f"Empresa {row['ticker']} no ano {yr} possui PL <= 0 ({pl}). Alavancagem desconsiderada."
                    )
                else:
                    alavancagens.append(dl / pl)

        alav_med = float(np.mean(alavancagens)) if alavancagens else np.nan

        if not s_selic.empty and isinstance(s_selic.index, pd.DatetimeIndex):
            selic_yr = s_selic[s_selic.index.year == yr]
            selic_med = selic_media_anual(selic_yr)
        else:
            selic_med = np.nan

        linhas.append({
            "ano": yr,
            "despesa_financeira_total": desp_tot,
            "lucro_liquido_total": lucro_tot,
            "alavancagem_media": alav_med,
            "selic_media_anual": selic_med,
        })

    df_res = pd.DataFrame(linhas)
    if df_res.empty:
        return df_vazio, avisos

    # Cálculo da base 100 com base no ano_base
    row_base = df_res[df_res["ano"] == ano_base]
    if not row_base.empty:
        desp_base = row_base.iloc[0]["despesa_financeira_total"]
        lucro_base = row_base.iloc[0]["lucro_liquido_total"]

        df_res["despesa_financeira_b100"] = (
            (df_res["despesa_financeira_total"] / desp_base) * 100.0 if pd.notna(desp_base) and desp_base != 0 else np.nan
        )
        df_res["lucro_liquido_b100"] = (
            (df_res["lucro_liquido_total"] / lucro_base) * 100.0 if pd.notna(lucro_base) and lucro_base != 0 else np.nan
        )
    else:
        df_res["despesa_financeira_b100"] = np.nan
        df_res["lucro_liquido_b100"] = np.nan
        avisos.append(f"Ano base {ano_base} não encontrado para cálculo da Base 100.")

    return df_res, avisos


# ------------------------------------------------------------------------------
# Pergunta 3 — Estresse Cambial 
# ------------------------------------------------------------------------------

def janelas_estresse_cambial(
    ptax_diaria: pd.Series,
    janela_dias: int = ESTRESSE_CAMBIAL_JANELA_DIAS,
    limiar_pct: float = ESTRESSE_CAMBIAL_LIMIAR_PCT,
) -> pd.DataFrame:
    """Identifica janelas de tempo contínuas em que a PTAX subiu pelo menos limiar_pct em janela_dias."""
    cols = ["inicio", "fim", "variacao_pct", "ptax_inicio", "ptax_fim"]
    clean = ptax_diaria.dropna().sort_index()
    if clean.empty or len(clean) < 2:
        return pd.DataFrame(columns=cols)

    janelas = []
    n = len(clean)

    for i in range(n):
        dt_ini = clean.index[i]
        val_ini = float(clean.iloc[i])
        dt_limite = dt_ini + pd.Timedelta(days=janela_dias)

        sub = clean[(clean.index >= dt_ini) & (clean.index <= dt_limite)]
        if len(sub) < 2:
            continue

        val_max = float(sub.max())
        dt_max = sub.idxmax()

        var_pct = ((val_max / val_ini) - 1.0) * 100.0
        if var_pct >= limiar_pct:
            janelas.append({
                "inicio": dt_ini,
                "fim": dt_max,
                "variacao_pct": var_pct,
                "ptax_inicio": val_ini,
                "ptax_fim": val_max,
            })

    if not janelas:
        return pd.DataFrame(columns=cols)

    df_j = pd.DataFrame(janelas).sort_values("inicio")
    # Mescla janelas sobrepostas ou contíguas
    merged = []
    curr = df_j.iloc[0].to_dict()

    for idx in range(1, len(df_j)):
        row = df_j.iloc[idx].to_dict()
        if row["inicio"] <= curr["fim"]:
            if row["ptax_fim"] > curr["ptax_fim"]:
                curr["fim"] = row["fim"]
                curr["ptax_fim"] = row["ptax_fim"]
                curr["variacao_pct"] = ((curr["ptax_fim"] / curr["ptax_inicio"]) - 1.0) * 100.0
        else:
            merged.append(curr)
            curr = row
    merged.append(curr)

    return pd.DataFrame(merged)


def exportadoras_em_estresse(
    fato_cotacoes: pd.DataFrame,
    dim_empresa: pd.DataFrame,
    janelas_estresse: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    """Compara o retorno diário médio dentro vs. fora das janelas de estresse cambial para exportadoras vs. demais."""
    avisos: List[str] = []
    cols = ["grupo", "retorno_diario_medio_dentro_pct", "retorno_diario_medio_fora_pct", "diferenca_pp"]
    df_vazio = pd.DataFrame(columns=cols)

    if fato_cotacoes.empty or dim_empresa.empty:
        return df_vazio, ["Dados de cotação ou empresa ausentes."]

    emp_triade, avisos_u = universo_triade(dim_empresa)
    avisos.extend(avisos_u)

    if emp_triade.empty:
        return df_vazio, avisos

    pivot_close, _, pivot_ret = _preparar_pivots(fato_cotacoes, emp_triade)
    if pivot_ret.empty or not isinstance(pivot_ret.index, pd.DatetimeIndex):
        return df_vazio, avisos

    mapa_exp = emp_triade.set_index("ticker")["exportadora_commodities"].to_dict()

    tickers_exp = [t for t, is_exp in mapa_exp.items() if is_exp and t in pivot_ret.columns]
    tickers_demais = [t for t, is_exp in mapa_exp.items() if not is_exp and t in pivot_ret.columns]

    if not tickers_exp:
        avisos.append("Nenhuma empresa exportadora encontrada na seleção.")
    if not tickers_demais:
        avisos.append("Nenhuma empresa não-exportadora encontrada na seleção.")

    ret_exp = pivot_ret[tickers_exp].mean(axis=1) if tickers_exp else pd.Series(dtype=float)
    ret_demais = pivot_ret[tickers_demais].mean(axis=1) if tickers_demais else pd.Series(dtype=float)

    # Flag de dias de estresse
    dias_estresse = pd.Series(False, index=pivot_ret.index)
    if not janelas_estresse.empty:
        for _, row in janelas_estresse.iterrows():
            dias_estresse |= (pivot_ret.index >= row["inicio"]) & (pivot_ret.index <= row["fim"])

    linhas = []
    for nome_grp, s_ret in [("Exportadoras Commodities", ret_exp), ("Demais Setores", ret_demais)]:
        if s_ret.empty:
            continue
        dentro = s_ret[dias_estresse].dropna()
        fora = s_ret[~dias_estresse].dropna()

        med_d = float(dentro.mean()) * 100.0 if not dentro.empty else np.nan
        med_f = float(fora.mean()) * 100.0 if not fora.empty else np.nan
        diff = med_d - med_f if pd.notna(med_d) and pd.notna(med_f) else np.nan

        linhas.append({
            "grupo": nome_grp,
            "retorno_diario_medio_dentro_pct": med_d,
            "retorno_diario_medio_fora_pct": med_f,
            "diferenca_pp": diff,
        })

    return pd.DataFrame(linhas), avisos


def margem_ebit_exportadoras(
    painel_cvm: pd.DataFrame,
    fato_macro: pd.DataFrame,
    dim_indicador: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    """Compara a Margem EBIT média por exercício de exportadoras vs. demais industriais, com PTAX média anual."""
    avisos: List[str] = []
    cols = ["ano", "margem_ebit_exportadoras_pct", "margem_ebit_demais_pct", "ptax_media_anual"]
    df_vazio = pd.DataFrame(columns=cols)

    if painel_cvm.empty:
        return df_vazio, ["Painel CVM está vazio."]

    df_ind = painel_cvm[
        painel_cvm["comparavel_receita"] if "comparavel_receita" in painel_cvm.columns else (painel_cvm["tipo_plano"] != "financeira")
    ].copy()

    if df_ind.empty or "MARGEM_EBIT" not in df_ind.columns:
        return df_vazio, ["Nenhum dado válido de Margem EBIT encontrado."]

    s_ptax = serie_diaria(fato_macro, dim_indicador, "PTAX_VENDA")

    anos = sorted(df_ind["ano"].unique())
    linhas = []

    for yr in anos:
        sub_yr = df_ind[df_ind["ano"] == yr]
        exp_yr = sub_yr[sub_yr["exportadora_commodities"] & sub_yr["MARGEM_EBIT"].notna()]
        demais_yr = sub_yr[~sub_yr["exportadora_commodities"] & sub_yr["MARGEM_EBIT"].notna()]

        m_exp = float(exp_yr["MARGEM_EBIT"].mean()) * 100.0 if not exp_yr.empty else np.nan
        m_demais = float(demais_yr["MARGEM_EBIT"].mean()) * 100.0 if not demais_yr.empty else np.nan

        if not s_ptax.empty and isinstance(s_ptax.index, pd.DatetimeIndex):
            ptax_yr = s_ptax[s_ptax.index.year == yr]
            ptax_med = float(ptax_yr.mean()) if not ptax_yr.empty else np.nan
        else:
            ptax_med = np.nan

        linhas.append({
            "ano": yr,
            "margem_ebit_exportadoras_pct": m_exp,
            "margem_ebit_demais_pct": m_demais,
            "ptax_media_anual": ptax_med,
        })

    return pd.DataFrame(linhas), avisos


# ------------------------------------------------------------------------------
# Pergunta 4 — Ranking Setorial 
# ------------------------------------------------------------------------------

def ranking_setorial(
    painel_cvm: pd.DataFrame,
    fato_cotacoes: pd.DataFrame,
    dim_empresa: pd.DataFrame,
    fato_macro: pd.DataFrame,
    dim_indicador: pd.DataFrame,
    pesos: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """Calcula o ranking setorial ponderado (3 pilares: Bolsa, Resiliência Macro e Solidez Contábil)."""
    avisos: List[str] = []
    cols = [
        "setor_analitico",
        "pilar_bolsa_score",
        "pilar_resiliencia_score",
        "pilar_solidez_score",
        "score_final",
        "flag_parcial",
    ]
    df_vazio = pd.DataFrame(columns=cols)

    pesos_efetivos = RANKING_PESOS_DEFAULT.copy()
    if pesos:
        pesos_efetivos.update(pesos)

    emp_triade, avisos_u = universo_triade(dim_empresa)
    avisos.extend(avisos_u)

    if emp_triade.empty:
        return df_vazio, avisos

    setores = sorted(emp_triade["setor_analitico"].unique().tolist())
    if not setores:
        return df_vazio, avisos

    pivot_close, _, pivot_ret = _preparar_pivots(fato_cotacoes, emp_triade)
    s_ptax = serie_diaria(fato_macro, dim_indicador, "PTAX_VENDA")
    janelas_est = janelas_estresse_cambial(s_ptax) if not s_ptax.empty else pd.DataFrame()
    rf_diaria, avisos_rf = extrair_rf_diaria(fato_macro, dim_indicador, pivot_close.index if not pivot_close.empty else pd.DatetimeIndex([]))
    avisos.extend(avisos_rf)

    dados_setores = []

    for setor in setores:
        emps_setor = emp_triade[emp_triade["setor_analitico"] == setor]
        tickers_setor = emps_setor["ticker"].tolist()
        is_financeiro = "Financeiro" in setor or all(emps_setor["tipo_plano"] == "financeira")

        # 1. Pilar Bolsa (Retorno Acumulado Médio + Sharpe Médio)
        ret_acums = []
        sharpes = []
        drawdowns = []
        ret_estresse = []

        if not pivot_close.empty:
            for t in tickers_setor:
                if t in pivot_close.columns:
                    sc = pivot_close[t].dropna()
                    sr = pivot_ret[t].dropna() if t in pivot_ret.columns else pd.Series(dtype=float)
                    if not sc.empty:
                        r_ac = retorno_acumulado(sc)
                        if not r_ac.empty:
                            ret_acums.append(float(r_ac.iloc[-1]))
                        dd_m = drawdown_maximo(sc)
                        if pd.notna(dd_m):
                            drawdowns.append(dd_m)

                    if not sr.empty:
                        sh_v = sharpe(sr, rf_diaria)
                        if pd.notna(sh_v):
                            sharpes.append(sh_v)

                        if not janelas_est.empty and isinstance(sr.index, pd.DatetimeIndex):
                            dias_est = pd.Series(False, index=sr.index)
                            for _, r_j in janelas_est.iterrows():
                                dias_est |= (sr.index >= r_j["inicio"]) & (sr.index <= r_j["fim"])
                            r_d = sr[dias_est].dropna()
                            if not r_d.empty:
                                ret_estresse.append(float(r_d.mean()))

        med_ret_bolsa = float(np.mean(ret_acums)) if ret_acums else np.nan
        med_sharpe = float(np.mean(sharpes)) if sharpes else np.nan
        med_dd = float(np.mean(drawdowns)) if drawdowns else np.nan
        med_ret_estresse = float(np.mean(ret_estresse)) if ret_estresse else np.nan

        # 2. Pilar Solidez Contábil (ROE, Margem EBIT, Liquidez Corrente)
        roes, margens_ebit, liquidezes = [], [], []
        if not painel_cvm.empty:
            sub_cvm = painel_cvm[painel_cvm["ticker"].isin(tickers_setor)]
            if not sub_cvm.empty:
                if "ROE" in sub_cvm.columns:
                    roes = sub_cvm["ROE"].dropna().tolist()
                if not is_financeiro:
                    if "MARGEM_EBIT" in sub_cvm.columns:
                        margens_ebit = sub_cvm["MARGEM_EBIT"].dropna().tolist()
                    if "LIQUIDEZ_CORRENTE" in sub_cvm.columns:
                        liquidezes = sub_cvm["LIQUIDEZ_CORRENTE"].dropna().tolist()

        med_roe = float(np.mean(roes)) if roes else np.nan
        med_ebit = float(np.mean(margens_ebit)) if margens_ebit else np.nan
        med_liq = float(np.mean(liquidezes)) if liquidezes else np.nan

        dados_setores.append({
            "setor_analitico": setor,
            "is_financeiro": is_financeiro,
            "retorno_bolsa_raw": med_ret_bolsa,
            "sharpe_raw": med_sharpe,
            "drawdown_raw": med_dd,  # Menos negativo é melhor
            "ret_estresse_raw": med_ret_estresse,
            "roe_raw": med_roe,
            "ebit_raw": med_ebit,
            "liq_raw": med_liq,
        })

    df_raw = pd.DataFrame(dados_setores)

    # Normalização 0 - 100 dos pilares
    def _scale_col(series: pd.Series, ascending: bool = True) -> pd.Series:
        clean = series.dropna()
        if clean.empty or clean.max() == clean.min():
            return pd.Series(50.0, index=series.index)
        if ascending:
            res = ((series - clean.min()) / (clean.max() - clean.min())) * 100.0
        else:
            res = ((clean.max() - series) / (clean.max() - clean.min())) * 100.0
        return res.fillna(50.0)

    df_raw["score_ret_bolsa"] = _scale_col(df_raw["retorno_bolsa_raw"])
    df_raw["score_sharpe"] = _scale_col(df_raw["sharpe_raw"])
    df_raw["pilar_bolsa_score"] = df_raw[["score_ret_bolsa", "score_sharpe"]].mean(axis=1).fillna(50.0)

    df_raw["score_drawdown"] = _scale_col(df_raw["drawdown_raw"], ascending=True)
    df_raw["score_estresse"] = _scale_col(df_raw["ret_estresse_raw"])
    df_raw["pilar_resiliencia_score"] = df_raw[["score_drawdown", "score_estresse"]].mean(axis=1).fillna(50.0)

    df_raw["score_roe"] = _scale_col(df_raw["roe_raw"])
    df_raw["score_ebit"] = _scale_col(df_raw["ebit_raw"])
    df_raw["score_liq"] = _scale_col(df_raw["liq_raw"])

    solidez_scores = []
    for _, row in df_raw.iterrows():
        if row["is_financeiro"]:
            val = row["score_roe"]
            solidez_scores.append(val if pd.notna(val) else 50.0)
        else:
            vals = [row["score_roe"], row["score_ebit"], row["score_liq"]]
            valid_vals = [v for v in vals if pd.notna(v)]
            solidez_scores.append(float(np.mean(valid_vals)) if valid_vals else 50.0)
    df_raw["pilar_solidez_score"] = solidez_scores

    # Score Final Ponderado
    w_b = pesos_efetivos.get("retorno_bolsa", 1.0)
    w_r = pesos_efetivos.get("resiliencia_macro", 1.0)
    w_s = pesos_efetivos.get("solidez_contabil", 1.0)
    w_tot = w_b + w_r + w_s

    df_raw["score_final"] = (
        (df_raw["pilar_bolsa_score"].fillna(50.0) * w_b)
        + (df_raw["pilar_resiliencia_score"].fillna(50.0) * w_r)
        + (df_raw["pilar_solidez_score"].fillna(50.0) * w_s)
    ) / (w_tot if w_tot > 0 else 1.0)

    df_raw["flag_parcial"] = df_raw["is_financeiro"]

    fin_setores = df_raw[df_raw["flag_parcial"]]["setor_analitico"].tolist()
    if fin_setores:
        avisos.append(
            f"Setor(es) financeiro(s) ({', '.join(fin_setores)}) avaliado(s) com pilar de solidez parcial (apenas ROE) sem penalização."
        )

    res_df = df_raw[cols].sort_values("score_final", ascending=False).reset_index(drop=True)
    return res_df, avisos