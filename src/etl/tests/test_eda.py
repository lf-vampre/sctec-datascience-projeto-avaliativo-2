"""Testes unitários para o DataProfiler (EDA somente leitura)."""

import math
import numpy as np
import pandas as pd
import pytest

from src.config import settings
from src.etl.eda.profiler import Achado, DataProfiler, RelatorioEDA


@pytest.fixture
def profiler() -> DataProfiler:
    return DataProfiler()


def test_profiler_fonte_invalida(profiler: DataProfiler) -> None:
    with pytest.raises(ValueError, match="Fonte inválida"):
        profiler.perfil("invalida")


def test_profiler_dataframe_vazio(profiler: DataProfiler) -> None:
    df_empty = pd.DataFrame()
    relatorio = profiler.perfil("bacen", df_custom=df_empty)

    assert relatorio.resumo["linhas"] == 0
    assert len(relatorio.achados) == 1
    assert relatorio.achados[0].id == "EMPTY_TABLE"
    assert relatorio.achados[0].severidade == "critico"


def test_profiler_preserva_input(profiler: DataProfiler) -> None:
    df = pd.DataFrame({
        "codigo_sgs": [432, 432],
        "data": ["2023-01-01", "2023-01-02"],
        "valor": [13.75, 13.75],
    })
    df_copy = df.copy()

    profiler.perfil("bacen", df_custom=df)

    pd.testing.assert_frame_equal(df, df_copy)


def test_profiler_bacen_duplicatas_e_outliers(profiler: DataProfiler) -> None:
    df_bacen = pd.DataFrame({
        "codigo_sgs": [432, 432, 433, 433, 433, 433, 433],
        "data": [
            "2023-01-01", "2023-01-01",  # Duplicata na chave
            "2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01", "2023-05-01"
        ],
        "valor": [
            13.75, 13.75,
            0.5, 0.6, 0.4, 0.5, 50.0  # 50.0 é outlier em IPCA mensal (SGS 433)
        ],
    })

    relatorio = profiler.perfil("bacen", df_custom=df_bacen)

    achados_ids = [a.id for a in relatorio.achados]
    assert "BACEN_DUPLICATES" in achados_ids
    assert "BACEN_OUTLIER_IQR_433" in achados_ids

    # Garantir que a tabela resumo de séries BACEN foi gerada
    assert "resumo_series_bacen" in relatorio.tabelas
    resumo_df = relatorio.tabelas["resumo_series_bacen"]
    assert 433 in resumo_df["codigo_sgs"].values


def test_profiler_b3_jarque_bera_e_retornos_extremos(profiler: DataProfiler) -> None:
    np.random.seed(42)
    datas = pd.date_range("2023-01-01", periods=15, freq="B")
    
    # Preços com um salto extremo (>15%)
    close_prices = [10.0] * 10 + [20.0] + [20.0] * 4

    df_b3 = pd.DataFrame({
        "ticker": ["PETR4"] * 15,
        "data": datas.strftime("%Y-%m-%d"),
        "close": close_prices,
        "volume": [1000] * 15,
        "flag_qualidade": ["OK"] * 15,
    })

    relatorio = profiler.perfil("b3", df_custom=df_b3)

    achados_ids = [a.id for a in relatorio.achados]
    assert "B3_EXTREME_RETURNS_PETR4" in achados_ids

    assert "metricas_b3" in relatorio.tabelas
    m_df = relatorio.tabelas["metricas_b3"]
    assert len(m_df) == 1
    
    # Cálculo manual do Jarque-Bera
    retornos = pd.Series(close_prices).pct_change().dropna()
    n = len(retornos)
    s = retornos.skew()
    k = retornos.kurtosis()
    jb_expected = (n / 6.0) * (s**2 + (k**2) / 4.0)
    p_val_expected = math.exp(-jb_expected / 2.0)

    assert pytest.approx(m_df.iloc[0]["jb_stat"], rel=1e-3) == jb_expected
    assert pytest.approx(m_df.iloc[0]["jb_pvalue"], rel=1e-3) == p_val_expected


def test_profiler_cvm_bancos_info_e_pl_negativo(profiler: DataProfiler) -> None:
    df_cvm = pd.DataFrame({
        "cd_cvm": [1234, 1234, 19348, 19348],  # 19348 = ITUB4 (financeira/banco em COMPANIES)
        "DT_FIM_EXERC": ["2023-12-31", "2023-12-31", "2023-12-31", "2023-12-31"],
        "cd_conta": ["3.01", "2.03", "3.01", "2.03"],
        "vl_conta": [1000.0, -500.0, 5000.0, 10000.0],  # 1234 tem PL negativo (-500)
    })

    relatorio = profiler.perfil("cvm", df_custom=df_cvm)

    achados_ids = [a.id for a in relatorio.achados]
    assert "CVM_NEGATIVE_EQUITY_1234_2023-12-31" in achados_ids

    # O banco (ITUB4, cd_cvm=19348) deve gerar achado info para nulos estruturais (ADR-09)
    banco_achados = [a for a in relatorio.achados if a.id == "CVM_BANK_STRUCTURAL_NULLS_19348_2023-12-31"]
    assert len(banco_achados) == 1
    assert banco_achados[0].severidade == "info"


def test_profiler_cadastro_duplicatas_e_inativas(profiler: DataProfiler) -> None:
    df_cad = pd.DataFrame({
        "cd_cvm": [100, 100, 200],
        "cnpj": ["00.000.000/0001-00", "00.000.000/0001-00", "11.111.111/0001-11"],
        "denom_cia": ["EMPRESA A", "EMPRESA A", "EMPRESA B"],
        "sit_cad": ["ATIVO", "CANCELADA", "SUSPENSA"],
    })

    relatorio = profiler.perfil("cadastro", df_custom=df_cad)

    achados_ids = [a.id for a in relatorio.achados]
    assert "CADASTRO_DUPLICATE_CD_CVM" in achados_ids
    assert "CADASTRO_DUPLICATE_CNPJ" in achados_ids
    assert "CADASTRO_INACTIVE_COMPANIES" in achados_ids