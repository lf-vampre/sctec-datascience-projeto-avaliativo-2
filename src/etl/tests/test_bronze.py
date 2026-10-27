"""Testes unitários e de integração para os extratores da camada Bronze."""

from pathlib import Path
import pytest

from src.etl.base import PipelineLogger
from src.etl.extractors.bacen_extractor import BacenExtractor
from src.etl.extractors.cadastro_extractor import CadastroExtractor
from src.etl.warehouse.persistence import Persistence
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
        tickers=[],
        bacen_periodo=("2023-01-01", "2023-03-31"),
        b3_periodo=("2023-01-01", "2023-03-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )

    res1 = extractor.run_bronze(params)

    assert res1.ok is True
    assert res1.rows > 0
    assert len(res1.paths) == 1
    assert Path(res1.paths[0]).exists()

    df_saved = persistence.load("bronze", "bacen_sgs", modo="sandbox")
    assert not df_saved.empty
    assert set(df_saved.columns) == {"serie_codigo", "serie_nome", "data", "valor", "_ingest_ts", "_run_id"}
    series_obtidas = set(df_saved["serie_codigo"].unique())
    assert len(series_obtidas) == 7

    res2 = extractor.run_bronze(params)
    assert res2.ok is True
    assert any("reutilizado" in w.lower() for w in res2.warnings)


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
        tickers=["WEGE3", "PETR4", "VALE3"],
        bacen_periodo=("2023-01-01", "2023-03-31"),
        b3_periodo=("2023-01-01", "2023-03-31"),
        cvm_anos=[2023],
        is_sandbox=True,
    )

    res1 = extractor.run_bronze(params)

    assert res1.ok is True
    assert res1.rows > 0
    assert len(res1.paths) == 1
    assert Path(res1.paths[0]).exists()

    df_saved = persistence.load("bronze", "cvm_cadastro", modo="sandbox")
    assert not df_saved.empty
    assert ("CD_CVM" in df_saved.columns) or ("cd_cvm" in df_saved.columns)

    res2 = extractor.run_bronze(params)
    assert res2.ok is True
    assert any("reutilizado" in w.lower() for w in res2.warnings)