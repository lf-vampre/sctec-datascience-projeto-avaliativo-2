"""Funções puras de cálculo de métricas financeiras, macroeconômicas e de mercado."""

from typing import List, Union
import numpy as np
import pandas as pd


def _safe_div(
    numerator: Union[float, pd.Series], denominator: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Realiza divisão segura substituindo divisão por zero, nulos e infinitos por NaN."""
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        num = pd.Series(numerator) if not isinstance(numerator, pd.Series) else numerator
        den = pd.Series(denominator) if not isinstance(denominator, pd.Series) else denominator
        with np.errstate(divide="ignore", invalid="ignore"):
            result = num / den
            result = result.replace([np.inf, -np.inf], np.nan)
        return result
    else:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return np.nan
        with np.errstate(divide="ignore", invalid="ignore"):
            res = numerator / denominator
            if np.isinf(res) or np.isnan(res):
                return np.nan
            return float(res)


# ------------------------------------------------------------------------------
# Métricas de Mercado
# ------------------------------------------------------------------------------


def retorno_diario(close: pd.Series) -> pd.Series:
    """Calcula o retorno diário percentual de uma série de preços de fechamento."""
    if close.empty:
        return pd.Series(dtype=float)
    return close.pct_change(fill_method=None)


def retorno_acumulado(close: pd.Series) -> pd.Series:
    """Calcula o retorno acumulado de uma série a partir do primeiro valor disponível."""
    if close.empty or close.iloc[0] == 0 or pd.isna(close.iloc[0]):
        return pd.Series(np.nan, index=close.index)
    return (close / close.iloc[0]) - 1.0


def base100(close: pd.Series) -> pd.Series:
    """Normaliza a série de preços para a base 100 no primeiro pregão."""
    if close.empty or close.iloc[0] == 0 or pd.isna(close.iloc[0]):
        return pd.Series(np.nan, index=close.index)
    return (close / close.iloc[0]) * 100.0


def vol_anualizada(retornos: pd.Series) -> float:
    """Calcula a volatilidade anualizada dos retornos diários (assumindo 252 dias úteis)."""
    clean_ret = retornos.dropna()
    if len(clean_ret) < 2:
        return np.nan
    std_val = float(clean_ret.std())
    if np.isnan(std_val):
        return np.nan
    return std_val * np.sqrt(252)


def drawdown(close: pd.Series) -> pd.Series:
    """Calcula a série de drawdown em relação ao pico histórico da série."""
    if close.empty:
        return pd.Series(dtype=float)
    peak = close.cummax()
    return _safe_div(close - peak, peak)


def drawdown_maximo(close: pd.Series) -> float:
    """Retorna o valor do drawdown máximo (menor valor negativo) de uma série."""
    dd = drawdown(close)
    if dd.empty or dd.dropna().empty:
        return np.nan
    return float(dd.min())


def sma(close: pd.Series, n: int) -> pd.Series:
    """Calcula a média móvel simples de n períodos."""
    if close.empty or len(close) < n:
        return pd.Series(np.nan, index=close.index)
    return close.rolling(window=n).mean()


def rf_diaria_de_selic(selic_aa_pct: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """Converte a taxa Selic percentual ao ano para taxa diária equivalente (252 dias úteis)."""
    if isinstance(selic_aa_pct, pd.Series):
        return ((1.0 + selic_aa_pct / 100.0) ** (1.0 / 252.0)) - 1.0
    if pd.isna(selic_aa_pct):
        return np.nan
    return ((1.0 + selic_aa_pct / 100.0) ** (1.0 / 252.0)) - 1.0


def sharpe(
    retornos: pd.Series, rf_diaria: Union[float, pd.Series]
) -> float:
    """Calcula o índice de Sharpe anualizado a partir dos retornos diários e do risco-livre diário."""
    clean_ret = retornos.dropna()
    if clean_ret.empty or len(clean_ret) < 2:
        return np.nan

    if isinstance(rf_diaria, pd.Series):
        rf_aligned = rf_diaria.reindex(clean_ret.index).ffill().bfill().fillna(0.0)
        excesso = clean_ret - rf_aligned
    else:
        rf_val = 0.0 if pd.isna(rf_diaria) else rf_diaria
        excesso = clean_ret - rf_val

    excesso_clean = excesso.dropna()
    if len(excesso_clean) < 2:
        return np.nan

    std_excesso = float(excesso_clean.std())
    if std_excesso == 0.0 or np.isnan(std_excesso):
        return np.nan

    mean_excesso = float(excesso_clean.mean())
    return (mean_excesso / std_excesso) * np.sqrt(252)


# ------------------------------------------------------------------------------
# Métricas Macro
# ------------------------------------------------------------------------------


def juro_real_fisher(
    i_pct: Union[float, pd.Series], pi_pct: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Calcula o Juro Real Ex-Post utilizando a fórmula exata de Fisher."""
    num = 1.0 + i_pct / 100.0
    den = 1.0 + pi_pct / 100.0
    return _safe_div(num, den) - 1.0


def selic_media_anual(selic_diaria: pd.Series) -> float:
    """Calcula a média simples da Selic diária para o período/ano informado."""
    clean_selic = selic_diaria.dropna()
    if clean_selic.empty:
        return np.nan
    return float(clean_selic.mean())


# ------------------------------------------------------------------------------
# Métricas Fundamentalistas
# ------------------------------------------------------------------------------


def margem_liquida(
    ll: Union[float, pd.Series], rl: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Calcula a Margem Líquida (fração)."""
    return _safe_div(ll, rl)


def margem_ebit(
    ebit: Union[float, pd.Series], rl: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Calcula a Margem EBIT (fração)."""
    return _safe_div(ebit, rl)


def roe(
    ll: Union[float, pd.Series], pl: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Calcula o ROE (Return on Equity) (fração)."""
    return _safe_div(ll, pl)


def liquidez_corrente(
    ac: Union[float, pd.Series], pc: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Calcula a Liquidez Corrente (fração)."""
    return _safe_div(ac, pc)


def divida_bruta(
    cp: Union[float, pd.Series], lp: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """Calcula a Dívida Bruta (soma dos empréstimos e financiamentos CP e LP)."""
    return cp + lp


def divida_liquida(
    cp: Union[float, pd.Series],
    lp: Union[float, pd.Series],
    caixa: Union[float, pd.Series],
    aplic: Union[float, pd.Series],
) -> Union[float, pd.Series]:
    """Calcula a Dívida Líquida (Dívida Bruta menos Caixa e Aplicações)."""
    db = divida_bruta(cp, lp)
    liquidez = caixa + aplic
    return db - liquidez


def crescimento(serie_anual: pd.Series) -> pd.Series:
    """Calcula a variação percentual ano a ano de uma série temporal contábil."""
    if serie_anual.empty:
        return pd.Series(dtype=float)
    return serie_anual.pct_change(fill_method=None)


# ------------------------------------------------------------------------------
# Métricas de Retorno Anual e Setorial
# ------------------------------------------------------------------------------


def retorno_anual(close: pd.Series) -> pd.Series:
    """Calcula o retorno anual de uma série de preços de fechamento com índice Datetime.
    
    Regra: último pregão do ano / último pregão do ano anterior - 1.
    No 1º ano da janela, a base é o 1º pregão da janela.
    """
    if close.empty or not isinstance(close.index, pd.DatetimeIndex):
        return pd.Series(dtype=float)

    sorted_close = close.sort_index().dropna()
    if sorted_close.empty:
        return pd.Series(dtype=float)

    years = sorted_close.index.year.unique()
    returns = {}

    for i, yr in enumerate(years):
        close_yr = sorted_close[sorted_close.index.year == yr]
        if close_yr.empty:
            continue
        last_close_yr = close_yr.iloc[-1]

        if i == 0:
            base_close = sorted_close.iloc[0]
        else:
            prev_yr = years[i - 1]
            close_prev_yr = sorted_close[sorted_close.index.year == prev_yr]
            base_close = close_prev_yr.iloc[-1] if not close_prev_yr.empty else sorted_close.iloc[0]

        ret_val = _safe_div(last_close_yr - base_close, base_close)
        returns[yr] = float(ret_val) if not isinstance(ret_val, pd.Series) else ret_val

    return pd.Series(returns)


def retorno_setorial_anual(
    retornos_por_ticker: pd.DataFrame, tickers_setor: List[str]
) -> pd.Series:
    """Calcula a média simples dos retornos anuais para os tickers pertencentes a um setor."""
    valid_tickers = [t for t in tickers_setor if t in retornos_por_ticker.columns]
    if not valid_tickers or retornos_por_ticker.empty:
        return pd.Series(dtype=float)
    return retornos_por_ticker[valid_tickers].mean(axis=1)