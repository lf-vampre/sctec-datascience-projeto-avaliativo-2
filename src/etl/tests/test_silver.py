"""Testes de integração e unidade para a camada Prata (BacenCleaner, B3Cleaner, CvmCleaner e CadastroCleaner).

Valida desacoplamento por fonte, ordem trocada de execução, idempotência e isolamento.
"""

from unittest.mock import MagicMock
import pandas as pd
import pytest

from src.config import settings
from src.etl.base import PipelineLogger
from src.etl.cleaners.account_mapper import AccountMapper
from src.etl.cleaners.b3_cleaner import B3Cleaner
from src.etl.cleaners.bacen_cleaner import BacenCleaner
from src.etl.cleaners.cadastro_cleaner import CadastroCleaner
from src.etl.cleaners.cvm_cleaner import CvmCleaner
from src.models.contracts import PipelineParams


@pytest.fixture
def logger() -> PipelineLogger:
    return PipelineLogger()


@pytest.fixture
def params() -> PipelineParams:
    return PipelineParams(
        tickers=["WEGE3", "ITUB4"],
        bacen_periodo=("2019-01-01", "2023-12-31"),
        b3_periodo=("2019-01-01", "2024-01-01"),
        cvm_anos=[2021, 2022, 2023],
        is_sandbox=True,
    )


# ------------------------------------------------------------------------------
# Testes CadastroCleaner (STORY-018B)
# ------------------------------------------------------------------------------

def test_cadastro_cleaner_normalization_and_warnings(logger: PipelineLogger, params: PipelineParams) -> None:
    df_bronze = pd.DataFrame({
        "CD_CVM": ["14311", "14311", "906"],
        "CNPJ_CIA": ["84.429.695/0001-11", "84.429.695/0001-11", "60.746.948/0001-12345"],  # CNPJ com tamanho inválido
        "DENOM_SOC": ["WEG S.A.", "WEG S.A.", "BANCO BRADESCO S.A."],
        "SIT": ["FASE OPERACIONAL", "FASE OPERACIONAL", "REGISTRO CANCELADO"],
        "SETOR_ATIV": ["MAQUINARIOS", "MAQUINARIOS", "BANCOS"],
        "DT_REG": ["1995-01-01", "1995-01-01", "1980-01-01"],
    })

    mock_storage = MagicMock()
    mock_storage.load.return_value = df_bronze
    mock_storage.save.return_value = {
        "parquet_path": "data/silver/cvm_cadastro.parquet",
        "rows": 2,
        "neon_ok": False,
        "warning": None,
    }

    cleaner = CadastroCleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is True
    assert result.rows == 2
    mock_storage.save.assert_called_once()

    saved_df = mock_storage.save.call_args[1]["df"]
    
    # Validações de tratamento
    assert "cnpj_limpo" in saved_df.columns
    wege_row = saved_df[saved_df["cd_cvm"] == 14311].iloc[0]
    assert wege_row["cnpj_limpo"] == "84429695000111"

    # Validações de unicidade
    assert len(saved_df[saved_df["cd_cvm"] == 14311]) == 1

    # Validações de avisos (CNPJ inválido, duplicata, situação cancelada)
    assert any("CNPJs com tamanho diferente" in w for w in result.warnings)
    assert any("duplicatas" in w for w in result.warnings)
    assert any("situação" in w for w in result.warnings)


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
        "close": [38.8, 38.8, 39.2, None],
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
        "high": [75.0, 120.0],
        "low": [70.0, 78.0],
        "close": [80.0, 120.0],
        "volume": [0, 500000],
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


# ------------------------------------------------------------------------------
# Testes AccountMapper e CvmCleaner
# ------------------------------------------------------------------------------

def test_account_mapper_industrial_and_financial(logger: PipelineLogger) -> None:
    df = pd.DataFrame({
        "cd_cvm": [14311, 14311, 19348, 19348, 19348],
        "ano": [2022, 2022, 2022, 2022, 2022],
        "demonstrativo": ["DRE", "BPA", "DRE", "BPP", "DRE"],
        "cd_conta": ["3.01", "1.01", "3.01", "2.03", "3.05"],
        "ds_conta": [
            "Receita de Venda de Bens e/ou Serviços",
            "Ativo Circulante",
            "Receitas da Intermediação Financeira",
            "Patrimônio Líquido Consolidado",
            "Resultado Antes do Resultado Financeiro e dos Impostos",
        ],
        "st_conta_fixa": ["S", "S", "S", "S", "S"],
    })

    mapper = AccountMapper(logger=logger)
    df_mapped, warnings = mapper.map_accounts(df)

    wege_rec = df_mapped[(df_mapped["cd_cvm"] == 14311) & (df_mapped["cd_conta"] == "3.01")]
    assert wege_rec.iloc[0]["codigo_indicador"] == "RECEITA_LIQUIDA"

    wege_ac = df_mapped[(df_mapped["cd_cvm"] == 14311) & (df_mapped["cd_conta"] == "1.01")]
    assert wege_ac.iloc[0]["codigo_indicador"] == "ATIVO_CIRCULANTE"

    itub_rec = df_mapped[(df_mapped["cd_cvm"] == 19348) & (df_mapped["cd_conta"] == "3.01")]
    assert itub_rec.iloc[0]["codigo_indicador"] == "RECEITA_INTERMEDIACAO"

    itub_pl = df_mapped[(df_mapped["cd_cvm"] == 19348) & (df_mapped["cd_conta"] == "2.03")]
    assert itub_pl.iloc[0]["codigo_indicador"] == "PATRIMONIO_LIQUIDO"

    itub_ebit = df_mapped[(df_mapped["cd_cvm"] == 19348) & (df_mapped["cd_conta"] == "3.05")]
    assert pd.isna(itub_ebit.iloc[0]["codigo_indicador"])


def test_cvm_cleaner_integration_with_account_mapper(logger: PipelineLogger, params: PipelineParams) -> None:
    df_dre_bronze = pd.DataFrame({
        "CD_CVM": ["14311"],
        "DT_FIM_EXERC": ["2022-12-31"],
        "CD_CONTA": ["3.01"],
        "DS_CONTA": ["Receita de Venda de Bens e/ou Serviços"],
        "ST_CONTA_FIXA": ["S"],
        "VL_CONTA": [100.0],
        "ESCALA_MOEDA": ["MIL"],
        "VERSAO": [1],
        "ORDEM_EXERC": ["ÚLTIMO"],
    })

    def mock_load(layer: str, name: str, modo: str = "sandbox") -> pd.DataFrame:
        if name == "cvm_dre":
            return df_dre_bronze
        return pd.DataFrame()

    mock_storage = MagicMock()
    mock_storage.load.side_effect = mock_load
    mock_storage.save.return_value = {
        "parquet_path": "data/silver/cvm_demonstrativos.parquet",
        "rows": 1,
        "neon_ok": False,
        "warning": None,
    }

    cleaner = CvmCleaner(logger=logger, storage_writer=mock_storage)
    result = cleaner.clean(params)

    assert result.ok is True
    assert result.rows == 1
    mock_storage.save.assert_called_once()

    saved_df = mock_storage.save.call_args[1]["df"]
    assert "codigo_indicador" in saved_df.columns
    assert saved_df.iloc[0]["codigo_indicador"] == "RECEITA_LIQUIDA"


# ------------------------------------------------------------------------------
# Testes Desacoplamento, Idempotência, Ordem Trocada e Isolamento
# ------------------------------------------------------------------------------

def test_execution_order_independence(logger: PipelineLogger, params: PipelineParams) -> None:
    sgs_selic = settings.BACEN_SERIES["SELIC_META"]["sgs_codigo"]

    df_bacen = pd.DataFrame({
        "data": ["01/01/2023"],
        "valor": ["13.75"],
        "serie_codigo": [sgs_selic],
    })
    df_b3 = pd.DataFrame({
        "ticker": ["WEGE3"],
        "data": ["2023-01-02"],
        "open": [38.0],
        "high": [39.0],
        "low": [37.5],
        "close": [38.8],
        "volume": [1000000],
    })
    df_cvm = pd.DataFrame({
        "CD_CVM": ["14311"],
        "DT_FIM_EXERC": ["2022-12-31"],
        "CD_CONTA": ["3.01"],
        "DS_CONTA": ["Receita de Venda de Bens e/ou Serviços"],
        "ST_CONTA_FIXA": ["S"],
        "VL_CONTA": [100.0],
        "ESCALA_MOEDA": ["MIL"],
        "VERSAO": [1],
        "ORDEM_EXERC": ["ÚLTIMO"],
    })

    def make_storage(df):
        st = MagicMock()
        st.load.return_value = df
        st.save.return_value = {"parquet_path": "dummy.parquet", "rows": 1, "neon_ok": False, "warning": None}
        return st

    # Ordem 1: Bacen -> B3 -> CVM
    res_bacen_1 = BacenCleaner(logger, make_storage(df_bacen)).clean(params)
    res_b3_1 = B3Cleaner(logger, make_storage(df_b3)).clean(params)
    res_cvm_1 = CvmCleaner(logger, make_storage(df_cvm)).clean(params)

    # Ordem 2: CVM -> B3 -> Bacen
    res_cvm_2 = CvmCleaner(logger, make_storage(df_cvm)).clean(params)
    res_b3_2 = B3Cleaner(logger, make_storage(df_b3)).clean(params)
    res_bacen_2 = BacenCleaner(logger, make_storage(df_bacen)).clean(params)

    assert res_bacen_1.ok is True and res_bacen_2.ok is True
    assert res_b3_1.ok is True and res_b3_2.ok is True
    assert res_cvm_1.ok is True and res_cvm_2.ok is True
    assert res_bacen_1.rows == res_bacen_2.rows == 1
    assert res_b3_1.rows == res_b3_2.rows == 1
    assert res_cvm_1.rows == res_cvm_2.rows == 1


def test_idempotency_double_execution(logger: PipelineLogger, params: PipelineParams) -> None:
    df_b3 = pd.DataFrame({
        "ticker": ["WEGE3"],
        "data": ["2023-01-02"],
        "open": [38.0],
        "high": [39.0],
        "low": [37.5],
        "close": [38.8],
        "volume": [1000000],
    })

    mock_storage = MagicMock()
    mock_storage.load.return_value = df_b3
    mock_storage.save.return_value = {"parquet_path": "dummy.parquet", "rows": 1, "neon_ok": False, "warning": None}

    cleaner = B3Cleaner(logger=logger, storage_writer=mock_storage)

    res_run1 = cleaner.clean(params)
    res_run2 = cleaner.clean(params)

    assert res_run1.ok is True
    assert res_run2.ok is True
    assert res_run1.rows == res_run2.rows == 1


def test_isolation_missing_one_bronze_source(logger: PipelineLogger, params: PipelineParams) -> None:
    df_bacen = pd.DataFrame({
        "data": ["01/01/2023"],
        "valor": ["13.75"],
        "serie_codigo": [settings.BACEN_SERIES["SELIC_META"]["sgs_codigo"]],
    })

    st_bacen = MagicMock()
    st_bacen.load.return_value = df_bacen
    st_bacen.save.return_value = {"parquet_path": "bacen.parquet", "rows": 1, "neon_ok": False, "warning": None}

    st_b3_empty = MagicMock()
    st_b3_empty.load.return_value = pd.DataFrame()

    res_bacen = BacenCleaner(logger, st_bacen).clean(params)
    res_b3 = B3Cleaner(logger, st_b3_empty).clean(params)

    assert res_bacen.ok is True
    assert res_bacen.rows == 1
    assert res_b3.ok is False
    assert res_b3.rows == 0
    assert "vazio" in res_b3.error