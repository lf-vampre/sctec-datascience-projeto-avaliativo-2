"""Preparação de dados e cálculos de risco/retorno para o Dashboard de Mercado e Risco B3 (D3).

Módulo de funções puras em Pandas/NumPy (sem streamlit, sem I/O).
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config.settings import SERIE_RISCO_LIVRE
from src.etl.warehouse.metrics_calculator import (
    base100 as calc_base100,
    drawdown as calc_drawdown,
    drawdown_maximo,
    retorno_acumulado,
    retorno_diario,
    rf_diaria_de_selic,
    sharpe,
    sma,
    vol_anualizada,
)


def _preparar_pivots(
    fato_cotacoes: pd.DataFrame,
    dim_empresa: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Cruza cotações com empresas e gera matrizes pivoteadas (data x ticker) para fecho, volume e retorno."""
    if fato_cotacoes.empty or dim_empresa.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = fato_cotacoes.merge(dim_empresa[["sk_empresa", "ticker"]], on="sk_empresa", how="inner")
    if "data" not in df.columns and "sk_tempo" in df.columns:
        df["data"] = pd.to_datetime(df["sk_tempo"].astype(str), format="%Y%m%d")

    df = df.sort_values("data")

    pivot_close = df.pivot(index="data", columns="ticker", values="close")
    pivot_volume = df.pivot(index="data", columns="ticker", values="volume")

    if "volume_fin_aprox" in df.columns and df["volume_fin_aprox"].notna().any():
        pivot_vol_fin = df.pivot(index="data", columns="ticker", values="volume_fin_aprox")
    else:
        pivot_vol_fin = pivot_close * pivot_volume

    return pivot_close, pivot_vol_fin, pivot_close.pct_change(fill_method=None)


def extrair_rf_diaria(
    fato_macro: pd.DataFrame,
    dim_indicador: pd.DataFrame,
    index_datas: pd.DatetimeIndex,
    serie_codigo: str = SERIE_RISCO_LIVRE,
) -> Tuple[Optional[pd.Series], List[str]]:
    """Extrai e converte a série de risco-livre diária (ex: Selic Efetiva) para os dias de pregão."""
    avisos: List[str] = []
    if fato_macro.empty or dim_indicador.empty:
        avisos.append(f"Ausência da série de risco-livre '{serie_codigo}' na camada Ouro.")
        return None, avisos

    ind_rf = dim_indicador[dim_indicador["codigo"] == serie_codigo]
    if ind_rf.empty:
        avisos.append(f"Indicador de risco-livre '{serie_codigo}' não encontrado em dim_indicador.")
        return None, avisos

    sk_rf = ind_rf.iloc[0]["sk_indicador"]
    macro_rf = fato_macro[fato_macro["sk_indicador"] == sk_rf].copy()

    if macro_rf.empty:
        avisos.append(f"Sem dados observados para a série de risco-livre '{serie_codigo}'.")
        return None, avisos

    macro_rf["data"] = pd.to_datetime(macro_rf["sk_tempo"].astype(str), format="%Y%m%d")
    macro_rf = macro_rf.sort_values("data").set_index("data")

    rf_aa = macro_rf["valor"].reindex(index_datas).ffill().bfill()
    rf_diaria = rf_diaria_de_selic(rf_aa)
    return rf_diaria, avisos


def calcular_base100(pivot_close: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Calcula a base 100 (normalizada em 100 no 1º pregão) por ativo e a carteira equiponderada."""
    avisos: List[str] = []
    if pivot_close.empty:
        return pd.DataFrame(), ["Sem dados de cotação para calcular Base 100."]

    base100_df = pd.DataFrame(index=pivot_close.index)
    min_date_global = pivot_close.index[0]

    for col in pivot_close.columns:
        serie = pivot_close[col].dropna()
        if serie.empty:
            avisos.append(f"Ativo {col} sem cotações válidas na janela selecionada.")
            continue
        if serie.index[0] > min_date_global:
            avisos.append(
                f"Ativo {col} iniciou histórico em {serie.index[0].strftime('%d/%m/%Y')}, posterior ao início da janela."
            )
        base100_df[col] = calc_base100(serie)

    if not base100_df.empty:
        base100_df["Carteira"] = base100_df.drop(columns=["Carteira"], errors="ignore").mean(axis=1)

    return base100_df, avisos


def tabela_risco_retorno(
    pivot_close: pd.DataFrame,
    pivot_vol_fin: pd.DataFrame,
    pivot_retornos: pd.DataFrame,
    rf_diaria: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Consolida a tabela de métricas estatísticas, risco e retorno por ativo e carteira equiponderada."""
    if pivot_close.empty:
        return pd.DataFrame()

    registros = []
    cols = list(pivot_close.columns)

    for col in cols:
        close_col = pivot_close[col].dropna()
        ret_col = pivot_retornos[col].dropna()
        vol_fin_col = pivot_vol_fin[col].dropna() if col in pivot_vol_fin.columns else pd.Series(dtype=float)

        if close_col.empty or ret_col.empty:
            continue

        ret_acum = float(retorno_acumulado(close_col).iloc[-1]) if not close_col.empty else np.nan
        vol_an = vol_anualizada(ret_col)
        sh_val = sharpe(ret_col, rf_diaria) if rf_diaria is not None else sharpe(ret_col, 0.0)
        dd_max = drawdown_maximo(close_col)
        skew_val = float(ret_col.skew()) if len(ret_col) > 2 else np.nan
        kurt_val = float(ret_col.kurtosis()) if len(ret_col) > 2 else np.nan
        p5_val = float(ret_col.quantile(0.05)) if not ret_col.empty else np.nan
        vol_med = float(vol_fin_col.mean()) if not vol_fin_col.empty else np.nan

        registros.append({
            "ticker": col,
            "retorno_acumulado": ret_acum,
            "volatilidade_anualizada": vol_an,
            "sharpe": sh_val,
            "drawdown_maximo": dd_max,
            "assimetria": skew_val,
            "curtose": kurt_val,
            "p5_retorno_diario": p5_val,
            "volume_medio_diario": vol_med,
        })

    # Adiciona a Carteira equiponderada
    if pivot_close.shape[1] > 0:
        ret_carteira_diario = pivot_retornos.mean(axis=1).dropna()
        base100_cart = pivot_close.apply(calc_base100).mean(axis=1).dropna()
        ret_acum_cart = (base100_cart.iloc[-1] / 100.0) - 1.0 if not base100_cart.empty else np.nan
        vol_an_cart = vol_anualizada(ret_carteira_diario)
        sh_cart = sharpe(ret_carteira_diario, rf_diaria) if rf_diaria is not None else sharpe(ret_carteira_diario, 0.0)
        dd_cart = float(calc_drawdown(base100_cart).min()) if not base100_cart.empty else np.nan
        vol_med_cart = float(pivot_vol_fin.sum(axis=1).mean()) if not pivot_vol_fin.empty else np.nan

        registros.append({
            "ticker": "Carteira",
            "retorno_acumulado": ret_acum_cart,
            "volatilidade_anualizada": vol_an_cart,
            "sharpe": sh_cart,
            "drawdown_maximo": dd_cart,
            "assimetria": float(ret_carteira_diario.skew()),
            "curtose": float(ret_carteira_diario.kurtosis()),
            "p5_retorno_diario": float(ret_carteira_diario.quantile(0.05)),
            "volume_medio_diario": vol_med_cart,
        })

    res_df = pd.DataFrame(registros)
    if not res_df.empty:
        res_df = res_df.sort_values(by="sharpe", ascending=False, na_position="last").reset_index(drop=True)

    return res_df


def kpis_mercado(tabela_rr: pd.DataFrame, pivot_close: pd.DataFrame) -> Dict[str, Any]:
    """Gera KPIs executivos de mercado com deltas anuais quando aplicável."""
    if tabela_rr.empty:
        return {
            "retorno_medio_carteira": None,
            "retorno_delta_pp": None,
            "ativo_destaque": "N/A",
            "ativo_destaque_retorno": None,
            "ativo_pior": "N/A",
            "ativo_pior_retorno": None,
            "volatilidade_media": None,
            "volatilidade_delta_pp": None,
        }

    tab_act = tabela_rr[tabela_rr["ticker"] != "Carteira"].copy()
    tab_cart = tabela_rr[tabela_rr["ticker"] == "Carteira"]

    ret_cart = float(tab_cart.iloc[0]["retorno_acumulado"]) if not tab_cart.empty else tab_act["retorno_acumulado"].mean()
    vol_med = float(tab_act["volatilidade_anualizada"].mean()) if not tab_act.empty else None

    destaque_row = tab_act.sort_values("retorno_acumulado", ascending=False).iloc[0] if not tab_act.empty else None
    pior_row = tab_act.sort_values("retorno_acumulado", ascending=True).iloc[0] if not tab_act.empty else None

    # Cálculo do Delta (Ano Atual vs. Ano Anterior se janela >= 2 anos)
    delta_ret_pp = None
    delta_vol_pp = None

    if not pivot_close.empty and isinstance(pivot_close.index, pd.DatetimeIndex):
        anos = sorted(pivot_close.index.year.unique())
        if len(anos) >= 2:
            ano_fim, ano_ant = anos[-1], anos[-2]
            close_fim = pivot_close[pivot_close.index.year == ano_fim]
            close_ant = pivot_close[pivot_close.index.year == ano_ant]

            if not close_fim.empty and not close_ant.empty:
                ret_fim = (close_fim.iloc[-1] / close_fim.iloc[0]) - 1.0
                ret_ant = (close_ant.iloc[-1] / close_ant.iloc[0]) - 1.0
                delta_ret_pp = float((ret_fim.mean() - ret_ant.mean()) * 100.0)

                vol_fim = close_fim.pct_change(fill_method=None).std() * np.sqrt(252)
                vol_ant = close_ant.pct_change(fill_method=None).std() * np.sqrt(252)
                delta_vol_pp = float((vol_fim.mean() - vol_ant.mean()) * 100.0)

    return {
        "retorno_medio_carteira": ret_cart,
        "retorno_delta_pp": delta_ret_pp,
        "ativo_destaque": destaque_row["ticker"] if destaque_row is not None else "N/A",
        "ativo_destaque_retorno": float(destaque_row["retorno_acumulado"]) if destaque_row is not None else None,
        "ativo_pior": pior_row["ticker"] if pior_row is not None else "N/A",
        "ativo_pior_retorno": float(pior_row["retorno_acumulado"]) if pior_row is not None else None,
        "volatilidade_media": vol_med,
        "volatilidade_delta_pp": delta_vol_pp,
    }


def distribuicao_retornos(
    pivot_retornos: pd.DataFrame, ticker: Optional[str] = None
) -> Tuple[pd.Series, Dict[str, float]]:
    """Extrai a série de retornos diários de um ativo ou da carteira e calcula estatísticas de forma."""
    if pivot_retornos.empty:
        return pd.Series(dtype=float), {}

    if ticker and ticker in pivot_retornos.columns:
        serie = pivot_retornos[ticker].dropna()
    else:
        serie = pivot_retornos.mean(axis=1).dropna()

    if serie.empty:
        return pd.Series(dtype=float), {}

    stats = {
        "media": float(serie.mean()),
        "desvio_padrao": float(serie.std()),
        "assimetria": float(serie.skew()),
        "curtose": float(serie.kurtosis()),
        "p5": float(serie.quantile(0.05)),
        "minimo": float(serie.min()),
        "maximo": float(serie.max()),
    }
    return serie, stats


def serie_drawdown(pivot_close: pd.DataFrame) -> pd.DataFrame:
    """Calcula a série temporal de drawdown por ativo e pela carteira equiponderada."""
    if pivot_close.empty:
        return pd.DataFrame()

    dd_df = pd.DataFrame(index=pivot_close.index)
    for col in pivot_close.columns:
        dd_df[col] = calc_drawdown(pivot_close[col])

    base100_cart = pivot_close.apply(calc_base100).mean(axis=1)
    dd_df["Carteira"] = calc_drawdown(base100_cart)
    return dd_df


def ranking_resiliencia(tabela_rr: pd.DataFrame) -> pd.DataFrame:
    """Ordena os ativos pelo menor drawdown máximo em módulo (maior resiliência)."""
    if tabela_rr.empty:
        return pd.DataFrame()

    df = tabela_rr[tabela_rr["ticker"] != "Carteira"].copy()
    df["abs_drawdown"] = df["drawdown_maximo"].abs()
    return df.sort_values(by="abs_drawdown", ascending=True).drop(columns=["abs_drawdown"]).reset_index(drop=True)


def serie_sma(
    fato_cotacoes: pd.DataFrame,
    dim_empresa: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """Retorna a série temporal de fecho e médias móveis simples (21 e 50 períodos) com flags de cruzamento."""
    if fato_cotacoes.empty or dim_empresa.empty:
        return pd.DataFrame()

    emp = dim_empresa[dim_empresa["ticker"] == ticker]
    if emp.empty:
        return pd.DataFrame()

    sk_emp = emp.iloc[0]["sk_empresa"]
    sub = fato_cotacoes[fato_cotacoes["sk_empresa"] == sk_emp].copy()

    if sub.empty:
        return pd.DataFrame()

    sub["data"] = pd.to_datetime(sub["sk_tempo"].astype(str), format="%Y%m%d")
    sub = sub.sort_values("data").set_index("data")

    df_res = pd.DataFrame(index=sub.index)
    df_res["close"] = sub["close"]

    # Reutiliza SMA gravada na Ouro ou calcula no histórico
    df_res["sma_21"] = sub["sma_21"] if "sma_21" in sub.columns and sub["sma_21"].notna().any() else sma(sub["close"], 21)
    df_res["sma_50"] = sub["sma_50"] if "sma_50" in sub.columns and sub["sma_50"].notna().any() else sma(sub["close"], 50)

    # Identificação descritiva de cruzamento (sem recomendação de compra/venda)
    df_res["cruzamento"] = "Neutro"
    valido = df_res["sma_21"].notna() & df_res["sma_50"].notna()
    diff = df_res.loc[valido, "sma_21"] - df_res.loc[valido, "sma_50"]
    sinal = np.sign(diff)
    cruz = sinal.diff()

    df_res.loc[cruz[cruz > 0].index, "cruzamento"] = "SMA 21 cruzou acima da SMA 50"
    df_res.loc[cruz[cruz < 0].index, "cruzamento"] = "SMA 21 cruzou abaixo da SMA 50"

    return df_res