"""Testes unitários e de integração para a camada Ouro (Star Schema e Metrics Calculator)."""

import numpy as np
import pandas as pd
import pytest

from src.etl.warehouse.metrics_calculator import (
    base100,
    crescimento,
    divida_bruta,
    divida_liquida,
    drawdown,
    drawdown_maximo,
    juro_real_fisher,
    liquidez_corrente,
    margem_ebit,
    margem_liquida,
    retorno_acumulado,
    retorno_anual,
    retorno_diario,
    retorno_setorial_anual,
    rf_diaria_de_selic,
    roe,
    sharpe,
    sma,
    vol_anualizada,
)
from src.etl.warehouse.persistence import Persistence
from src.etl.warehouse.star_schema import StarSchemaBuilder
from src.models.contracts import PipelineParams


@pytest.fixture
def mock_params() -> PipelineParams:
    """Retorna PipelineParams configurado para ambiente de teste sandbox."""
    return PipelineParams(
        tickers=["WEGE3", "ITUB4", "JBSS3"],
        bacen_periodo=("2021-01-01", "2023-12-31"),
        b3_periodo=("2021-01-01", "2023-12-31"),
        cvm_anos=[2021, 2022, 2023],
        is_sandbox=True,
    )


@pytest.fixture
def persistence() -> Persistence:
    """Instância de Persistence para testes."""
    return Persistence()


@pytest.fixture
def builder(persistence: Persistence) -> StarSchemaBuilder:
    """Instância do StarSchemaBuilder para testes."""
    return StarSchemaBuilder(persistence=persistence)


# ------------------------------------------------------------------------------
# Testes das Dimensões (Star Schema)
# ------------------------------------------------------------------------------


def test_run_dims_execution(builder: StarSchemaBuilder, mock_params: PipelineParams) -> None:
    """Valida a execução de run_dims e o retorno de StepResult."""
    result = builder.run_dims(mock_params)

    assert result.ok is True
    assert result.step_id == "run_dims"
    assert result.rows > 0
    assert len(result.paths) == 3
    assert result.error is None


def test_dim_tempo_integrity(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida integridade, continuidade e presença do marco 2020-12-31 na dim_tempo."""
    builder.run_dims(mock_params)
    df_tempo = persistence.load("gold", "dim_tempo", modo=mock_params.modo)

    assert not df_tempo.empty
    assert "sk_tempo" in df_tempo.columns
    assert "data" in df_tempo.columns

    assert df_tempo["sk_tempo"].is_unique

    sk_tempo_20201231 = 20201231
    assert sk_tempo_20201231 in df_tempo["sk_tempo"].values

    df_tempo["dt"] = pd.to_datetime(df_tempo["data"])
    df_tempo_sorted = df_tempo.sort_values("dt")
    date_diffs = df_tempo_sorted["dt"].diff().dropna()
    assert (date_diffs == pd.Timedelta(days=1)).all()


def test_dim_empresa_integrity(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida unicidade de chaves, mapeamento de tipo_plano e estabilidade na dim_empresa."""
    builder.run_dims(mock_params)
    df_empresa = persistence.load("gold", "dim_empresa", modo=mock_params.modo)

    assert not df_empresa.empty

    assert df_empresa["sk_empresa"].is_unique
    assert df_empresa["ticker"].is_unique
    assert df_empresa["cd_cvm"].is_unique

    itub4_row = df_empresa[df_empresa["ticker"] == "ITUB4"].iloc[0]
    assert itub4_row["tipo_plano"] == "financeira"

    wege3_row = df_empresa[df_empresa["ticker"] == "WEGE3"].iloc[0]
    assert wege3_row["tipo_plano"] == "industrial"


def test_dim_indicador_integrity(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida unicidade de chaves e estrutura da dim_indicador."""
    builder.run_dims(mock_params)
    df_indicador = persistence.load("gold", "dim_indicador", modo=mock_params.modo)

    assert not df_indicador.empty

    assert df_indicador["sk_indicador"].is_unique
    assert df_indicador["codigo"].is_unique

    codigos = set(df_indicador["codigo"])
    assert "SELIC_META" in codigos
    assert "RECEITA_LIQUIDA" in codigos
    assert "JURO_REAL_EXPOST" in codigos
    assert "ROE" in codigos
    assert "RETORNO_DIARIO" in codigos


def test_keys_stability_between_runs(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Garante que as chaves substitutas sk_empresa, sk_tempo e sk_indicador são idênticas entre execuções."""
    builder.run_dims(mock_params)
    empresa_run1 = persistence.load("gold", "dim_empresa", modo=mock_params.modo)
    indicador_run1 = persistence.load("gold", "dim_indicador", modo=mock_params.modo)

    builder.run_dims(mock_params)
    empresa_run2 = persistence.load("gold", "dim_empresa", modo=mock_params.modo)
    indicador_run2 = persistence.load("gold", "dim_indicador", modo=mock_params.modo)

    pd.testing.assert_frame_equal(empresa_run1, empresa_run2)
    pd.testing.assert_frame_equal(indicador_run1, indicador_run2)


# ------------------------------------------------------------------------------
# Testes do Metrics Calculator (DM-01, DM-02 e Regras de Negócio)
# ------------------------------------------------------------------------------


def test_juro_real_fisher_exact_value() -> None:
    """Valida Fisher exato (DM-01) para Selic 14,75% e IPCA 4,40% = ≈9,9138% (e não 10,35%)."""
    i_selic = 14.75
    pi_ipca = 4.40

    res_fisher = juro_real_fisher(i_selic, pi_ipca)
    expected_fisher = (1 + 0.1475) / (1 + 0.0440) - 1.0  # ≈ 0.09913793...

    assert pytest.approx(res_fisher, abs=1e-5) == expected_fisher
    assert pytest.approx(res_fisher, abs=1e-4) == 0.0991
    # Garante que difere da aproximação simples (14.75 - 4.40 = 10.35% = 0.1035)
    assert round(res_fisher, 4) != 0.1035


def test_base100_start_value() -> None:
    """Garante que a série em Base 100 sempre inicia exatamente em 100.0."""
    close = pd.Series([25.5, 26.0, 24.8, 27.2], index=pd.date_range("2023-01-01", periods=4))
    res_b100 = base100(close)

    assert res_b100.iloc[0] == 100.0
    assert pytest.approx(res_b100.iloc[1], abs=1e-4) == (26.0 / 25.5) * 100.0


def test_drawdown_maximo_custom_series() -> None:
    """Valida o cálculo do drawdown e drawdown máximo em série construída à mão."""
    close = pd.Series([100.0, 120.0, 90.0, 110.0])
    # Peak = [100, 120, 120, 120]
    # Drawdown = [0, 0, (90-120)/120 = -0.25, (110-120)/120 = -0.0833]
    dd_series = drawdown(close)
    max_dd = drawdown_maximo(close)

    assert pytest.approx(dd_series.iloc[2], abs=1e-4) == -0.25
    assert pytest.approx(max_dd, abs=1e-4) == -0.25


def test_sharpe_zero_rf() -> None:
    """Valida o índice de Sharpe com taxa livre de risco zero (DM-02)."""
    retornos = pd.Series([0.01, -0.005, 0.02, 0.003, -0.002, 0.015])
    rf_zero = 0.0

    sharpe_val = sharpe(retornos, rf_zero)
    expected_sharpe = (retornos.mean() / retornos.std()) * np.sqrt(252)

    assert pytest.approx(sharpe_val, abs=1e-5) == expected_sharpe


def test_safe_division_by_zero_returns_nan() -> None:
    """Garante que divisão por zero ou dados nulos retornam NaN sem lançar exceção ou inf."""
    res_single = margem_liquida(100.0, 0.0)
    assert np.isnan(res_single)

    res_null = roe(np.nan, 100.0)
    assert np.isnan(res_null)

    ll_series = pd.Series([10.0, 20.0, 30.0])
    rl_series = pd.Series([100.0, 0.0, np.nan])
    res_series = margem_liquida(ll_series, rl_series)

    assert res_series.iloc[0] == 0.10
    assert np.isnan(res_series.iloc[1])
    assert np.isnan(res_series.iloc[2])


def test_fundamentalist_and_annual_returns() -> None:
    """Valida cálculos fundamentalistas (Dívida Líquida) e retorno anual/setorial."""
    # Dívida Líquida = (CP + LP) - (Caixa + Aplicações)
    dl = divida_liquida(cp=50.0, lp=150.0, caixa=30.0, aplic=20.0)
    assert dl == 150.0  # (200) - (50)

    # Retorno Anual
    dates = pd.date_range("2021-01-01", "2022-12-31", freq="D")
    close_data = pd.Series(np.linspace(100, 200, len(dates)), index=dates)
    ret_anual = retorno_anual(close_data)

    assert 2021 in ret_anual.index
    assert 2022 in ret_anual.index

    # Retorno Setorial
    df_ret_anual = pd.DataFrame(
        {"WEGE3": [0.10, 0.20], "EMBR3": [0.30, 0.40]}, index=[2021, 2022]
    )
    ret_setor = retorno_setorial_anual(df_ret_anual, ["WEGE3", "EMBR3"])
    assert pytest.approx(ret_setor.loc[2021], abs=1e-5) == 0.20
    assert pytest.approx(ret_setor.loc[2022], abs=1e-5) == 0.30