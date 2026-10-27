"""Testes de integração e unidade para a camada Prata (BacenCleaner e B3Cleaner)."""

from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from src.config import settings
from src.etl.base import PipelineLogger
from src.etl.cleaners.bacen_cleaner import BacenCleaner
from src.etl.cleaners.b3_cleaner import B3Cleaner
from src.models.contracts import PipelineParams


@pytest.fixture
def logger() -> PipelineLogger:
    return PipelineLogger()


@pytest.fixture
def params() -> PipelineParams:
    return PipelineParams(
        tickers=["WEGE3", "VALE3"],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2019-01-01", "2024-01-01"),
        cvm_anos=[2021, 2022, 2023],
        is_sandbox=True,
    )


# ------------------------------------------------------------------------------
# Testes BacenCleaner
# ------------------------------------------------------------------------------

def test_bacen_cleaner_success(logger: PipelineLogger, params: PipelineParams) -> None:
    sgs_selic = settings.BACEN_SERIES["SELIC_META"]["sgs_codigo"]

    df_bronze = pd.DataFrame({
        "data": ["02/01/2023", "01/01/2023", "01/01/2023"],
        "valor": ["13.75", "13.75", "13.75"],
        "serie_codigo": [sgs_selic, sgs_selic, sgs_selic],
    })

    mock_storage = MagicMock()
    mock_storage.load.return_value = df_bronze
    mock_storage.save.return_value = {
        "parquet_path": "data/silver/bacen_sgs.parquet",
        "rows": 2,
        "neon_ok": False,
        "warning": None,
    }

    cleaner = BacenCleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is True
    assert result.rows == 2
    mock_storage.save.assert_called_once()

    saved_df = mock_storage.save.call_args[1]["df"]
    assert pd.api.types.is_datetime64_any_dtype(saved_df["data"])
    assert pd.api.types.is_float_dtype(saved_df["valor"])
    assert (saved_df["codigo"] == "SELIC_META").all()
    assert saved_df["data"].iloc[0] < saved_df["data"].iloc[1]


def test_bacen_cleaner_ipca_inconsistency_warning(logger: PipelineLogger, params: PipelineParams) -> None:
    sgs_ipca_m = settings.BACEN_SERIES["IPCA_MENSAL"]["sgs_codigo"]
    sgs_ipca_12m = settings.BACEN_SERIES["IPCA_12M"]["sgs_codigo"]

    dates = pd.date_range("2022-01-01", "2022-12-01", freq="MS")
    df_m = pd.DataFrame({
        "data": dates.strftime("%d/%m/%Y"),
        "valor": ["0.5"] * 12,
        "serie_codigo": [sgs_ipca_m] * 12,
    })

    df_12m = pd.DataFrame({
        "data": ["01/12/2022"],
        "valor": ["15.0"],
        "serie_codigo": [sgs_ipca_12m],
    })

    df_bronze = pd.concat([df_m, df_12m], ignore_index=True)

    mock_storage = MagicMock()
    mock_storage.load.return_value = df_bronze
    mock_storage.save.return_value = {
        "parquet_path": "data/silver/bacen_sgs.parquet",
        "rows": 13,
        "neon_ok": False,
        "warning": None,
    }

    cleaner = BacenCleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is True
    assert any("Incoerência IPCA" in w for w in result.warnings)


def test_bacen_cleaner_empty_bronze(logger: PipelineLogger, params: PipelineParams) -> None:
    mock_storage = MagicMock()
    mock_storage.load.return_value = pd.DataFrame()

    cleaner = BacenCleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is False
    assert result.rows == 0
    assert "vazio" in result.error


# ------------------------------------------------------------------------------
# Testes B3Cleaner
# ------------------------------------------------------------------------------

def test_b3_cleaner_success(logger: PipelineLogger, params: PipelineParams) -> None:
    df_bronze = pd.DataFrame({
        "ticker": ["WEGE3", "WEGE3", "WEGE3", "WEGE3"],
        "data": ["2023-01-02", "2023-01-02", "2023-01-03", "2023-01-04"],
        "open": [38.0, 38.0, 38.5, 39.0],
        "high": [39.0, 39.0, 39.5, 40.0],
        "low": [37.5, 37.5, 38.0, 38.5],
        "close": [38.8, 38.8, 39.2, None],  # 1 duplicata e 1 close nulo
        "volume": [1000000, 1000000, 1200000, 500000],
    })

    mock_storage = MagicMock()
    mock_storage.load.return_value = df_bronze
    mock_storage.save.return_value = {
        "parquet_path": "data/silver/b3_cotacoes.parquet",
        "rows": 2,
        "neon_ok": False,
        "warning": None,
    }

    cleaner = B3Cleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is True
    assert result.rows == 2
    mock_storage.save.assert_called_once()

    saved_df = mock_storage.save.call_args[1]["df"]
    assert pd.api.types.is_datetime64_any_dtype(saved_df["data"])
    assert pd.api.types.is_float_dtype(saved_df["close"])
    assert (saved_df["ticker"] == "WEGE3").all()
    assert (saved_df["flag_qualidade"] == "OK").all()


def test_b3_cleaner_ohlc_and_extreme_return_flags(logger: PipelineLogger, params: PipelineParams) -> None:
    df_bronze = pd.DataFrame({
        "ticker": ["VALE3", "VALE3"],
        "data": ["2023-01-02", "2023-01-03"],
        "open": [80.0, 80.0],
        "high": [75.0, 120.0],  # high < open no dia 1 (inconsistente)
        "low": [70.0, 78.0],
        "close": [80.0, 120.0],  # retorno +50% no dia 2 (extremo)
        "volume": [0, 500000],   # volume zero no dia 1
    })

    mock_storage = MagicMock()
    mock_storage.load.return_value = df_bronze
    mock_storage.save.return_value = {
        "parquet_path": "data/silver/b3_cotacoes.parquet",
        "rows": 2,
        "neon_ok": False,
        "warning": None,
    }

    cleaner = B3Cleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is True
    assert result.rows == 2

    saved_df = mock_storage.save.call_args[1]["df"]
    flags_day1 = saved_df.iloc[0]["flag_qualidade"]
    flags_day2 = saved_df.iloc[1]["flag_qualidade"]

    assert "OHLC_INVALIDO" in flags_day1
    assert "VOLUME_ZERO" in flags_day1
    assert "RETORNO_EXTREMO" in flags_day2


def test_b3_cleaner_empty_bronze(logger: PipelineLogger, params: PipelineParams) -> None:
    mock_storage = MagicMock()
    mock_storage.load.return_value = pd.DataFrame()

    cleaner = B3Cleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is False
    assert result.rows == 0
    assert "vazio" in result.error