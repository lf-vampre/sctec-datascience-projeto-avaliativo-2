"""Testes de integração para os extratores da camada Bronze (Bacen, Cadastro, B3 e CVM)."""

from pathlib import Path
import pandas as pd
import pytest

from src.etl.extractors.b3_extractor import B3Extractor
from src.etl.extractors.bacen_extractor import BacenExtractor
from src.etl.extractors.cadastro_extractor import CadastroExtractor
from src.etl.extractors.cvm_extractor import CvmExtractor
from src.etl.warehouse.persistence import Persistence
from src.etl.base import PipelineLogger
from src.models.contracts import PipelineParams


@pytest.mark.integration
def test_bacen_extractor_run_bronze(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    sandbox_dir = tmp_path / "data" / "_sandbox"
    monkeypatch.setattr("src.utils.paths.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", sandbox_dir)

    logger = PipelineLogger()
    persistence = Persistence()
    extractor = BacenExtractor(logger=logger, storage_writer=persistence)

    params = PipelineParams(
        tickers=["WEGE3", "PETR4"],
        bacen_periodo=("2023-01-01", "2023-03-31"),
        b3_periodo=("2023-01-01", "2023-03-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )

    res = extractor.run_bronze(params)

    assert res.ok is True
    assert res.rows > 0
    assert len(res.paths) == 1

    parquet_file = Path(res.paths[0])
    assert parquet_file.exists()

    df = pd.read_parquet(parquet_file)
    assert not df.empty
    assert "data" in df.columns
    assert "valor" in df.columns
    assert "serie_codigo" in df.columns


@pytest.mark.integration
def test_cadastro_extractor_run_bronze(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    sandbox_dir = tmp_path / "data" / "_sandbox"
    monkeypatch.setattr("src.utils.paths.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", sandbox_dir)

    logger = PipelineLogger()
    persistence = Persistence()
    extractor = CadastroExtractor(logger=logger, storage_writer=persistence)

    params = PipelineParams(
        tickers=["WEGE3", "PETR4"],
        bacen_periodo=("2023-01-01", "2023-03-31"),
        b3_periodo=("2023-01-01", "2023-03-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )

    res = extractor.run_bronze(params)

    assert res.ok is True
    assert res.rows >= 2
    assert len(res.paths) == 1

    parquet_file = Path(res.paths[0])
    assert parquet_file.exists()

    df = pd.read_parquet(parquet_file)
    assert len(df) >= 2
    assert "CD_CVM" in df.columns
    assert "CNPJ_CIA" in df.columns
    assert "DENOM_SOCIAL" in df.columns
    expected_cvm_codes = {"5410", "05410", "005410", "9512", "09512", "009512"}
    assert set(df["CD_CVM"].astype(str).str.strip().unique()).issubset(expected_cvm_codes)


@pytest.mark.integration
def test_b3_extractor_run_bronze(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    sandbox_dir = tmp_path / "data" / "_sandbox"
    monkeypatch.setattr("src.utils.paths.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", sandbox_dir)

    logger = PipelineLogger()
    persistence = Persistence()
    extractor = B3Extractor(logger=logger, storage_writer=persistence)

    params = PipelineParams(
        tickers=["WEGE3", "PETR4"],
        bacen_periodo=("2023-01-01", "2023-03-31"),
        b3_periodo=("2023-01-01", "2023-03-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )

    res = extractor.run_bronze(params)

    assert res.ok is True
    assert res.rows > 0
    assert len(res.paths) > 0

    df = persistence.load("bronze", "b3_cotacoes", modo=params.modo)
    assert not df.empty
    assert "ticker" in df.columns
    assert "close" in df.columns
    assert set(df["ticker"].unique()).issubset({"WEGE3", "PETR4"})


@pytest.mark.integration
def test_cvm_extractor_run_bronze(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    sandbox_dir = tmp_path / "data" / "_sandbox"
    monkeypatch.setattr("src.utils.paths.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.paths.SANDBOX_DIR", sandbox_dir)

    logger = PipelineLogger()
    persistence = Persistence()
    extractor = CvmExtractor(logger=logger, storage_writer=persistence)

    params = PipelineParams(
        tickers=["WEGE3", "PETR4"],
        bacen_periodo=("2023-01-01", "2023-03-31"),
        b3_periodo=("2023-01-01", "2023-03-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )

    res = extractor.run_bronze(params)

    assert res.ok is True
    assert res.rows > 0
    assert len(res.paths) == 3

    # Validação da presença e schema das 3 tabelas Bronze da CVM
    for table_name in ["cvm_dre", "cvm_bpa", "cvm_bpp"]:
        df = persistence.load("bronze", table_name, modo=params.modo)
        assert not df.empty
        assert "CD_CVM" in df.columns
        assert "ORDEM_EXERC" in df.columns
        assert "ano_arquivo" in df.columns

        # Garante que apenas empresas do universo selecionado foram carregadas
        expected_cvm_codes = {"5410", "05410", "005410", "9512", "09512", "009512"}
        extracted_codes = set(df["CD_CVM"].astype(str).str.strip().unique())
        assert extracted_codes.issubset(expected_cvm_codes)

        # Valida existência de registros dos exercícios ÚLTIMO e PENÚLTIMO
        ordens = set(df["ORDEM_EXERC"].unique())
        assert "ÚLTIMO" in ordens or "PENÚLTIMO" in ordens