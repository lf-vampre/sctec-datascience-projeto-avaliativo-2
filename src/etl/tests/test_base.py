"""Testes unitários do módulo base do ETL (src/etl/base.py)."""

from pathlib import Path
import pytest

from src.etl.base import (
    BaseCleaner,
    BaseExtractor,
    PipelineLogger,
    bronze_is_fresh,
    get_layer_path,
    release_lock,
    try_acquire,
)
from src.models.contracts import PipelineParams, StepResult


def test_pipeline_logger():
    logger = PipelineLogger()
    events = []

    def custom_handler(evt):
        events.append(evt)

    logger.add_handler(custom_handler)
    logger.emit("INFO", "TestFuente", "TEST", "Mensagem de teste", key="val")

    assert len(logger.logs) == 1
    assert len(events) == 1
    assert events[0]["message"] == "Mensagem de teste"
    assert events[0]["metadata"] == {"key": "val"}


class DummyExtractor(BaseExtractor):
    def __init__(self, logger, fail=False):
        super().__init__(logger)
        self.fail = fail

    def extract(self, params: PipelineParams) -> StepResult:
        if self.fail:
            raise RuntimeError("Erro forçado na extração")
        return StepResult(step_id="extract_dummy", ok=True, rows=10, paths=["/path/dummy.parquet"])


def test_base_extractor_success():
    logger = PipelineLogger()
    extractor = DummyExtractor(logger, fail=False)
    params = PipelineParams(
        tickers=["WEGE3"],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2021-01-01", "2024-01-01"),
        cvm_anos=[2021, 2022],
        is_sandbox=True,
    )
    res = extractor.run_bronze(params)

    assert res.ok is True
    assert res.rows == 10
    assert res.error is None
    assert res.duration_s >= 0


def test_base_extractor_failure_isolation():
    logger = PipelineLogger()
    extractor = DummyExtractor(logger, fail=True)
    params = PipelineParams(
        tickers=["WEGE3"],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2021-01-01", "2024-01-01"),
        cvm_anos=[2021, 2022],
        is_sandbox=True,
    )
    res = extractor.run_bronze(params)

    assert res.ok is False
    assert res.error == "Erro forçado na extração"


def test_bronze_is_fresh(tmp_path: Path):
    test_file = tmp_path / "sample.parquet"
    assert bronze_is_fresh(test_file, ttl_days=1) is False

    test_file.touch()
    assert bronze_is_fresh(test_file, ttl_days=1) is True


def test_get_layer_path():
    params_sandbox = PipelineParams(
        tickers=[],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2021-01-01", "2024-01-01"),
        cvm_anos=[2021],
        is_sandbox=True,
    )
    path_sb = get_layer_path(params_sandbox, "bronze")
    assert "_sandbox" in str(path_sb)

    params_prod = PipelineParams(
        tickers=[],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2021-01-01", "2024-01-01"),
        cvm_anos=[2021],
        is_sandbox=False,
    )
    path_prod = get_layer_path(params_prod, "bronze")
    assert "_sandbox" not in str(path_prod)


def test_execution_lock():
    release_lock()
    assert try_acquire("producao") is True
    assert try_acquire("producao") is False
    release_lock()