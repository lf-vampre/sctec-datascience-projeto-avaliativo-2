"""Testes de integração e unidade para a camada Prata (BacenCleaner)."""

from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from src.config import settings
from src.etl.base import PipelineLogger
from src.etl.cleaners.bacen_cleaner import BacenCleaner
from src.models.contracts import PipelineParams


@pytest.fixture
def logger() -> PipelineLogger:
    return PipelineLogger()


def test_bacen_cleaner_success(logger: PipelineLogger) -> None:
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
    params = PipelineParams(
            tickers=["WEGE3"],
            bacen_periodo=("2019-01-01", "2023-12-31"),
            b3_periodo=("2019-01-01", "2024-01-01"),
            cvm_anos=[2021, 2022, 2023],
            is_sandbox=True,
        )

    result = cleaner.clean(params)

    assert result.ok is True
    assert result.rows == 2
    mock_storage.save.assert_called_once()

    saved_df = mock_storage.save.call_args[1]["df"]
    assert pd.api.types.is_datetime64_any_dtype(saved_df["data"])
    assert pd.api.types.is_float_dtype(saved_df["valor"])
    assert (saved_df["codigo"] == "SELIC_META").all()
    assert saved_df["data"].iloc[0] < saved_df["data"].iloc[1]


def test_bacen_cleaner_ipca_inconsistency_warning(logger: PipelineLogger) -> None:
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
    params = PipelineParams(
            tickers=["WEGE3"],
            bacen_periodo=("2019-01-01", "2023-12-31"),
            b3_periodo=("2019-01-01", "2024-01-01"),
            cvm_anos=[2021, 2022, 2023],
            is_sandbox=True,
        )

    result = cleaner.clean(params)

    assert result.ok is True
    assert any("Incoerência IPCA" in w for w in result.warnings)


def test_bacen_cleaner_empty_bronze(logger: PipelineLogger) -> None:
    mock_storage = MagicMock()
    mock_storage.load.return_value = pd.DataFrame()

    cleaner = BacenCleaner(logger=logger, storage_writer=mock_storage)
    params = PipelineParams(
        tickers=["WEGE3"],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2019-01-01", "2024-01-01"),
        cvm_anos=[2021, 2022, 2023],
        is_sandbox=True,
    )

    result = cleaner.clean(params)

    assert result.ok is False
    assert result.rows == 0
    assert "vazio" in result.error