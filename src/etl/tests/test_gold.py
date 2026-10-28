"""Testes unitários e de integração para a camada Ouro (Star Schema, Metrics Calculator, Fatos e Persistência)."""

import json
import shutil
from unittest.mock import patch

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
from src.utils import paths


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
    expected_fisher = (1 + 0.1475) / (1 + 0.0440) - 1.0

    assert pytest.approx(res_fisher, abs=1e-5) == expected_fisher
    assert pytest.approx(res_fisher, abs=1e-4) == 0.0991
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
    dl = divida_liquida(cp=50.0, lp=150.0, caixa=30.0, aplic=20.0)
    assert dl == 150.0

    dates = pd.date_range("2021-01-01", "2022-12-31", freq="D")
    close_data = pd.Series(np.linspace(100, 200, len(dates)), index=dates)
    ret_anual = retorno_anual(close_data)

    assert 2021 in ret_anual.index
    assert 2022 in ret_anual.index

    df_ret_anual = pd.DataFrame(
        {"WEGE3": [0.10, 0.20], "EMBR3": [0.30, 0.40]}, index=[2021, 2022]
    )
    ret_setor = retorno_setorial_anual(df_ret_anual, ["WEGE3", "EMBR3"])
    assert pytest.approx(ret_setor.loc[2021], abs=1e-5) == 0.20
    assert pytest.approx(ret_setor.loc[2022], abs=1e-5) == 0.30


# ------------------------------------------------------------------------------
# Testes dos Fatos (fato_macro, fato_cotacoes, fato_demonstrativos)
# ------------------------------------------------------------------------------


def test_run_gold_without_dims_fails(
    builder: StarSchemaBuilder, mock_params: PipelineParams
) -> None:
    """Garante que chamar run_gold sem dimensões falha amigavelmente."""
    gold_dir = paths.SANDBOX_DIR / "gold"
    if gold_dir.exists():
        shutil.rmtree(gold_dir)

    res = builder.run_gold("bacen", mock_params)
    assert res.ok is False
    assert "Dimensões do Star Schema ausentes" in (res.error or "")


def test_run_gold_bacen_integrity(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida criação de fato_macro e presença de JURO_REAL_EXPOST sem chaves órfãs."""
    builder.run_dims(mock_params)

    df_bacen_silver = pd.DataFrame(
        [
            {"data": "2023-01-31", "sgs_codigo": 432, "valor": 13.75},
            {"data": "2023-01-31", "sgs_codigo": 13522, "valor": 5.77},
        ]
    )
    persistence.save("silver", "bacen_sgs", df_bacen_silver, modo=mock_params.modo)

    res = builder.run_gold("bacen", mock_params)
    assert res.ok is True

    df_fato = persistence.load("gold", "fato_macro", modo=mock_params.modo)
    assert not df_fato.empty
    assert "sk_tempo" in df_fato.columns
    assert "sk_indicador" in df_fato.columns
    assert "valor" in df_fato.columns

    df_ind = persistence.load("gold", "dim_indicador", modo=mock_params.modo)
    valid_sk_ind = set(df_ind["sk_indicador"])
    assert set(df_fato["sk_indicador"]).issubset(valid_sk_ind)

    juro_real_rows = df_fato[df_fato["sk_indicador"] == 8]
    assert not juro_real_rows.empty
    expected_fisher = (1 + 0.1375) / (1 + 0.0577) - 1.0
    assert pytest.approx(juro_real_rows.iloc[0]["valor"], abs=1e-4) == expected_fisher


def test_run_gold_b3_integrity_and_flag_update(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida criação de fato_cotacoes, indicadores derivados de mercado e atualização de tem_b3."""
    builder.run_dims(mock_params)

    dates = pd.date_range("2023-01-01", periods=60, freq="B")
    data_b3 = []
    for dt in dates:
        data_b3.append(
            {
                "ticker": "WEGE3",
                "data": dt.strftime("%Y-%m-%d"),
                "open": 38.0,
                "high": 39.0,
                "low": 37.5,
                "close": 38.5,
                "volume": 100000.0,
            }
        )
    df_b3_silver = pd.DataFrame(data_b3)
    persistence.save("silver", "b3_cotacoes", df_b3_silver, modo=mock_params.modo)

    res = builder.run_gold("b3", mock_params)
    assert res.ok is True

    df_fato = persistence.load("gold", "fato_cotacoes", modo=mock_params.modo)
    assert not df_fato.empty
    assert "retorno_diario" in df_fato.columns
    assert "sma_21" in df_fato.columns
    assert "sma_50" in df_fato.columns
    assert "volume_fin_aprox" in df_fato.columns

    df_empresa = persistence.load("gold", "dim_empresa", modo=mock_params.modo)
    wege_flag = df_empresa[df_empresa["ticker"] == "WEGE3"].iloc[0]["tem_b3"]
    jbss_flag = df_empresa[df_empresa["ticker"] == "JBSS3"].iloc[0]["tem_b3"]
    assert wege_flag is True or wege_flag == 1
    assert jbss_flag is False or jbss_flag == 0


def test_run_gold_cvm_financial_vs_industrial_rules(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida regras de negócio para instituições financeiras (ITUB4) vs industriais (WEGE3)."""
    builder.run_dims(mock_params)

    df_cvm_silver = pd.DataFrame(
        [
            {
                "cd_cvm": 5410,
                "dt_fim_exerc": "2023-12-31",
                "RECEITA_LIQUIDA": 1000.0,
                "LUCRO_BRUTO": 400.0,
                "EBIT": 200.0,
                "DESP_FINANCEIRAS": 20.0,
                "LUCRO_LIQUIDO": 150.0,
                "ATIVO_CIRCULANTE": 500.0,
                "PASSIVO_CIRCULANTE": 250.0,
                "CAIXA_EQUIV": 100.0,
                "APLIC_FINANC": 50.0,
                "EMPR_FIN_CP": 40.0,
                "EMPR_FIN_LP": 100.0,
                "PATRIMONIO_LIQUIDO": 800.0,
            },
            {
                "cd_cvm": 19348,
                "dt_fim_exerc": "2023-12-31",
                "RECEITA_INTERMEDIACAO": 5000.0,
                "LUCRO_LIQUIDO": 800.0,
                "PATRIMONIO_LIQUIDO": 4000.0,
            },
        ]
    )
    persistence.save("silver", "cvm_demonstrativos", df_cvm_silver, modo=mock_params.modo)

    res = builder.run_gold("cvm", mock_params)
    assert res.ok is True

    df_fato = persistence.load("gold", "fato_demonstrativos", modo=mock_params.modo)
    df_ind = persistence.load("gold", "dim_indicador", modo=mock_params.modo)
    ind_map = dict(zip(df_ind["codigo"], df_ind["sk_indicador"]))

    itub_sk = 19348
    itub_fatos = df_fato[df_fato["sk_empresa"] == itub_sk]
    itub_ind_sks = set(itub_fatos["sk_indicador"])

    assert ind_map["MARGEM_EBIT"] not in itub_ind_sks
    assert ind_map["LIQUIDEZ_CORRENTE"] not in itub_ind_sks
    assert ind_map["DIVIDA_BRUTA"] not in itub_ind_sks
    assert ind_map["DIVIDA_LIQUIDA"] not in itub_ind_sks

    assert ind_map["LUCRO_LIQUIDO"] in itub_ind_sks
    assert ind_map["PATRIMONIO_LIQUIDO"] in itub_ind_sks
    assert ind_map["ROE"] in itub_ind_sks
    assert ind_map["RECEITA_INTERMEDIACAO"] in itub_ind_sks

    wege_sk = 5410
    wege_fatos = df_fato[df_fato["sk_empresa"] == wege_sk]
    wege_ind_sks = set(wege_fatos["sk_indicador"])
    assert ind_map["MARGEM_EBIT"] in wege_ind_sks
    assert ind_map["LIQUIDEZ_CORRENTE"] in wege_ind_sks


def test_run_gold_idempotency(
    builder: StarSchemaBuilder, persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Garante que reexecutar run_gold não gera duplicatas nos fatos."""
    builder.run_dims(mock_params)

    df_bacen_silver = pd.DataFrame(
        [{"data": "2023-01-31", "sgs_codigo": 432, "valor": 13.75}]
    )
    persistence.save("silver", "bacen_sgs", df_bacen_silver, modo=mock_params.modo)

    builder.run_gold("bacen", mock_params)
    df_run1 = persistence.load("gold", "fato_macro", modo=mock_params.modo)

    builder.run_gold("bacen", mock_params)
    df_run2 = persistence.load("gold", "fato_macro", modo=mock_params.modo)

    assert len(df_run1) == len(df_run2)


# ------------------------------------------------------------------------------
# Testes da Persistência da Ouro (STORY-022)
# ------------------------------------------------------------------------------


def test_save_gold_creates_manifest(
    persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida se save('gold', ...) cria/atualiza _manifest.json corretamente."""
    df_mock = pd.DataFrame([{"sk_tempo": 20230101, "sk_indicador": 1, "valor": 13.75}])
    res = persistence.save("gold", "fato_macro", df_mock, modo=mock_params.modo)

    assert res["rows"] == 1

    manifest_path = paths.SANDBOX_DIR / "gold" / "_manifest.json"
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert "fato_macro" in manifest_data
    assert manifest_data["fato_macro"]["linhas"] == 1
    assert "run_id" in manifest_data["fato_macro"]
    assert "atualizado_em" in manifest_data["fato_macro"]


def test_load_gold_with_filters_pushdown(
    persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida filtragem pushdown no Parquet com dicionário e lista de tuplas."""
    df_mock = pd.DataFrame(
        [
            {"sk_tempo": 20230101, "sk_empresa": 5410, "close": 38.5},
            {"sk_tempo": 20230102, "sk_empresa": 5410, "close": 39.0},
            {"sk_tempo": 20230101, "sk_empresa": 19348, "close": 25.0},
        ]
    )
    persistence.save("gold", "fato_cotacoes", df_mock, modo=mock_params.modo)

    # Filtro via Dicionário
    df_filtered_dict = persistence.load(
        "gold", "fato_cotacoes", filters={"sk_empresa": 5410}, modo=mock_params.modo
    )
    assert len(df_filtered_dict) == 2
    assert set(df_filtered_dict["sk_empresa"]) == {5410}

    # Filtro via Lista de Tuplas com operador >=
    df_filtered_tuples = persistence.load(
        "gold",
        "fato_cotacoes",
        filters=[("sk_tempo", ">=", 20230102)],
        modo=mock_params.modo,
    )
    assert len(df_filtered_tuples) == 1
    assert df_filtered_tuples.iloc[0]["sk_tempo"] == 20230102


def test_load_gold_fallback_when_neon_unavailable(
    persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida se load em modo produção recorre ao Parquet se Neon estiver indisponível."""
    df_mock = pd.DataFrame([{"sk_tempo": 20230101, "sk_indicador": 1, "valor": 10.0}])
    persistence.save("gold", "fato_macro", df_mock, modo="producao")

    with patch("src.utils.db.is_available", return_value=False):
        df_loaded = persistence.load("gold", "fato_macro", modo="producao")
        assert not df_loaded.empty
        assert df_loaded.attrs.get("fonte") == "parquet"


def test_invalid_column_name_raises_error(persistence: Persistence) -> None:
    """Garante que tentativa de injeção de SQL via nomes de colunas resulta em ValueError."""
    with pytest.raises(ValueError, match="Nome de coluna inválido"):
        persistence.load("gold", "dim_empresa", columns=["ticker; DROP TABLE dim_empresa;--"])

    with pytest.raises(ValueError, match="Filtro com nome de coluna inválido"):
        persistence.load("gold", "dim_empresa", filters={"ticker; DELETE FROM dim_empresa;--": "WEGE3"})


def test_health_report_structure_and_divergence(
    persistence: Persistence, mock_params: PipelineParams
) -> None:
    """Valida estrutura do health_report() e identificação de divergências."""
    df_mock = pd.DataFrame([{"sk_tempo": 20230101, "sk_indicador": 1, "valor": 13.75}])
    persistence.save("gold", "fato_macro", df_mock, modo=mock_params.modo)

    report = persistence.health_report(modo=mock_params.modo)

    assert isinstance(report, dict)
    assert "fato_macro" in report
    assert "dim_empresa" in report

    macro_rep = report["fato_macro"]
    assert "linhas_parquet" in macro_rep
    assert "linhas_neon" in macro_rep
    assert "linhas_manifest" in macro_rep
    assert "fonte_ativa" in macro_rep
    assert macro_rep["linhas_manifest"] == 1