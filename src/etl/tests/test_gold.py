"""Testes unitários e de integração para a camada Ouro (Star Schema)."""

from pathlib import Path
import pandas as pd
import pytest

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

    # Unicidade da chave primária
    assert df_tempo["sk_tempo"].is_unique

    # Verificação de marco essencial para deltas de 2021
    sk_tempo_20201231 = 20201231
    assert sk_tempo_20201231 in df_tempo["sk_tempo"].values

    # Verificação de continuidade de datas (sem buracos)
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

    # Unicidades
    assert df_empresa["sk_empresa"].is_unique
    assert df_empresa["ticker"].is_unique
    assert df_empresa["cd_cvm"].is_unique

    # Validação de regras de negócio
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

    # Unicidade
    assert df_indicador["sk_indicador"].is_unique
    assert df_indicador["codigo"].is_unique

    # Presença dos indicadores essenciais
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