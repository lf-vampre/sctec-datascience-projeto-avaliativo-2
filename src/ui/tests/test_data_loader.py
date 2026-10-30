"""Testes do data_loader da UI (st.connection e Persistence simulados)."""

import json
from datetime import datetime

import pandas as pd
import pytest
import streamlit as st
from pandas.testing import assert_frame_equal

from src.models.contracts import Filtros
from src.ui import data_loader as dl

FATO_MACRO = pd.DataFrame(
    {"sk_tempo": [20230101, 20230201], "sk_indicador": [1, 1], "valor": [13.75, 13.75]}
)
DIM_EMPRESA = pd.DataFrame(
    {
        "sk_empresa": [1, 2, 3],
        "ticker": ["WEGE3", "ITUB4", "PETR4"],
        "setor_analitico": ["Industria", "Financeiro", "Energia"],
    }
)
DIM_INDICADOR = pd.DataFrame({"sk_indicador": [1, 2], "codigo": ["SELIC_META", "IPCA_12M"]})
TABELAS_FAKE = {
    "fato_macro": FATO_MACRO,
    "fato_cotacoes": pd.DataFrame({"sk_tempo": [20230102], "sk_empresa": [2], "close": [30.0]}),
    "fato_demonstrativos": pd.DataFrame(
        {"sk_tempo": [20231231], "sk_empresa": [2], "sk_indicador": [1], "valor": [1.0]}
    ),
    "dim_empresa": DIM_EMPRESA,
    "dim_indicador": DIM_INDICADOR,
}


class FakeConn:
    """Simula a conexão do st.connection e registra as consultas."""

    def __init__(self, tabelas, falhar=False):
        self.tabelas = tabelas
        self.falhar = falhar
        self.calls = []

    def query(self, sql, params=None, ttl=0):
        self.calls.append((sql, params))
        if self.falhar:
            raise RuntimeError("neon indisponivel")
        if sql.strip() == "SELECT 1":
            return pd.DataFrame({"x": [1]})
        for nome, df in self.tabelas.items():
            if f'"gold"."{nome}"' in sql:
                return df.copy()
        raise AssertionError(f"consulta inesperada: {sql}")

    def consultas_em(self, tabela):
        return [c for c in self.calls if f'"gold"."{tabela}"' in c[0]]


class FakePersistence:
    """Simula Persistence.load e registra os argumentos recebidos."""

    calls = []
    tabelas = {}
    falhar = False

    def load(self, layer, name, filters=None, columns=None, modo="producao", somente_parquet=False):
        FakePersistence.calls.append(
            {
                "layer": layer, "name": name, "filters": filters, "columns": columns,
                "modo": modo, "somente_parquet": somente_parquet,
            }
        )
        if FakePersistence.falhar:
            raise RuntimeError("parquet ausente")
        df = FakePersistence.tabelas.get(name)
        if df is None:
            df = pd.DataFrame()
            df.attrs["fonte"] = "empty"
            return df
        df = df.copy()
        df.attrs["fonte"] = "parquet"
        return df


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    st.cache_data.clear()
    FakePersistence.calls = []
    FakePersistence.tabelas = dict(TABELAS_FAKE)
    FakePersistence.falhar = False
    monkeypatch.setattr(dl, "Persistence", FakePersistence)
    monkeypatch.setattr(dl.paths, "GOLD_DIR", tmp_path)
    yield
    st.cache_data.clear()


@pytest.fixture
def neon(monkeypatch):
    conn = FakeConn(dict(TABELAS_FAKE))
    monkeypatch.setattr(dl.st, "connection", lambda *a, **k: conn)
    return conn


@pytest.fixture
def neon_fora(monkeypatch):
    conn = FakeConn(dict(TABELAS_FAKE), falhar=True)
    monkeypatch.setattr(dl.st, "connection", lambda *a, **k: conn)
    return conn


def _filtros(**kw):
    base = dict(
        periodo=("2019-01-01", "2023-12-31"),
        tickers=("WEGE3", "ITUB4"),
        setores=("Industria", "Financeiro"),
        indicadores_bacen=("SELIC_META",),
    )
    base.update(kw)
    return Filtros(**base)


# ------------------------------------------------------------------------------
# Whitelist
# ------------------------------------------------------------------------------
def test_whitelist_rejeita_tabela_invalida(neon):
    with pytest.raises(ValueError):
        dl.load_gold("pg_catalog; DROP TABLE x")
    assert neon.consultas_em("pg_catalog; DROP TABLE x") == []


def test_whitelist_rejeita_coluna_invalida(neon):
    with pytest.raises(ValueError):
        dl.load_gold("fato_macro", colunas=["valor; DROP TABLE x"])
    assert neon.consultas_em("fato_macro") == []


def test_load_dim_rejeita_nome_que_nao_e_dimensao(neon):
    with pytest.raises(ValueError):
        dl.load_dim("fato_macro")


# ------------------------------------------------------------------------------
# Neon x Parquet
# ------------------------------------------------------------------------------
def test_neon_disponivel_retorna_fonte_neon(neon):
    carga = dl.load_gold("fato_macro", _filtros())
    assert carga.fonte == "neon"
    assert_frame_equal(carga.dados, FATO_MACRO)

def test_neon_indisponivel_cai_para_parquet_com_mesmos_dados(monkeypatch):
    # Neon disponível
    conn_ok = FakeConn(dict(TABELAS_FAKE))
    monkeypatch.setattr(dl.st, "connection", lambda *a, **k: conn_ok)
    carga_neon = dl.load_gold("fato_macro", _filtros())
    assert carga_neon.fonte == "neon"

    # Neon indisponível (mesmo filtro, cache limpo)
    st.cache_data.clear()
    conn_fora = FakeConn(dict(TABELAS_FAKE), falhar=True)
    monkeypatch.setattr(dl.st, "connection", lambda *a, **k: conn_fora)
    carga_pq = dl.load_gold("fato_macro", _filtros())

    assert carga_pq.fonte == "parquet"
    assert_frame_equal(
        carga_pq.dados.reset_index(drop=True),
        carga_neon.dados.reset_index(drop=True),
    )

def test_contingencia_nao_levanta_erro_nem_tenta_neon_de_novo(neon_fora):
    carga = dl.load_gold("fato_macro")
    assert carga.fonte == "parquet"
    assert all(c["somente_parquet"] for c in FakePersistence.calls)


def test_falha_dupla_gera_dados_indisponiveis(neon_fora):
    FakePersistence.falhar = True
    with pytest.raises(dl.DadosIndisponiveis):
        dl.load_gold("fato_macro")


def test_parquet_vazio_gera_dados_indisponiveis(neon_fora):
    FakePersistence.tabelas = {}
    with pytest.raises(dl.DadosIndisponiveis):
        dl.load_gold("fato_macro")


def test_fonte_em_uso_reflete_neon(monkeypatch):
    conn_fora = FakeConn(dict(TABELAS_FAKE), falhar=True)
    monkeypatch.setattr(dl.st, "connection", lambda *a, **k: conn_fora)
    assert dl.fonte_em_uso() == "parquet"

    st.cache_data.clear()
    conn_ok = FakeConn(dict(TABELAS_FAKE))
    monkeypatch.setattr(dl.st, "connection", lambda *a, **k: conn_ok)
    assert dl.fonte_em_uso() == "neon"

# ------------------------------------------------------------------------------
# Cache
# ------------------------------------------------------------------------------
def test_mesmos_filtros_nao_repetem_a_consulta(neon):
    f = _filtros()
    dl.load_gold("fato_macro", f)
    dl.load_gold("fato_macro", f)
    assert len(neon.consultas_em("fato_macro")) == 1


def test_filtros_diferentes_geram_nova_consulta(neon):
    dl.load_gold("fato_macro", _filtros())
    dl.load_gold("fato_macro", _filtros(periodo=("2020-01-01", "2021-12-31")))
    assert len(neon.consultas_em("fato_macro")) == 2


# ------------------------------------------------------------------------------
# SQL parametrizado e filtros
# ------------------------------------------------------------------------------
def test_sql_usa_parametros_e_nao_interpola_valores(neon):
    dl.load_gold("fato_macro", _filtros())
    sql, params = neon.consultas_em("fato_macro")[0]
    assert '"sk_tempo" >= :p_0' in sql
    assert '"sk_tempo" <= :p_1' in sql
    assert '"sk_indicador" = ANY(:p_2)' in sql
    assert "20190101" not in sql and "20231231" not in sql
    assert params == {"p_0": 20190101, "p_1": 20231231, "p_2": [1]}


def test_pushdown_no_parquet_usa_mesmas_regras(neon_fora):
    dl.load_gold("fato_macro", _filtros())
    chamada = [c for c in FakePersistence.calls if c["name"] == "fato_macro"][0]
    assert chamada["filters"] == [
        ("sk_tempo", ">=", 20190101),
        ("sk_tempo", "<=", 20231231),
        ("sk_indicador", "in", [1]),
    ]


def test_empresas_usam_intersecao_de_tickers_e_setores(neon):
    dl.load_gold("fato_cotacoes", _filtros(tickers=("WEGE3", "ITUB4"), setores=("Financeiro",)))
    _, params = neon.consultas_em("fato_cotacoes")[0]
    assert params["p_2"] == [2]


def test_demonstrativos_usam_ano_cheio(neon):
    dl.load_gold("fato_demonstrativos", _filtros(periodo=("2019-03-01", "2023-06-30")))
    _, params = neon.consultas_em("fato_demonstrativos")[0]
    assert params["p_0"] == 20190101
    assert params["p_1"] == 20231231


def test_cotacoes_usam_data_exata(neon):
    dl.load_gold("fato_cotacoes", _filtros(periodo=("2019-03-01", "2023-06-30")))
    _, params = neon.consultas_em("fato_cotacoes")[0]
    assert params["p_0"] == 20190301
    assert params["p_1"] == 20230630


def test_selecao_vazia_de_empresas_retorna_vazio_sem_consultar_fato(neon):
    carga = dl.load_gold("fato_cotacoes", _filtros(tickers=()))
    assert carga.dados.empty
    assert neon.consultas_em("fato_cotacoes") == []


def test_selecao_vazia_de_indicadores_retorna_vazio(neon):
    carga = dl.load_gold("fato_macro", _filtros(indicadores_bacen=()))
    assert carga.dados.empty
    assert neon.consultas_em("fato_macro") == []


def test_tickers_vazios_nao_afetam_fato_macro(neon):
    carga = dl.load_gold("fato_macro", _filtros(tickers=(), setores=()))
    assert not carga.dados.empty


# ------------------------------------------------------------------------------
# Sandbox, manifest e dimensões
# ------------------------------------------------------------------------------
def test_sandbox_nunca_e_lido(neon_fora):
    dl.load_gold("fato_macro", _filtros())
    dl.load_gold("fato_cotacoes", _filtros())
    assert FakePersistence.calls
    for chamada in FakePersistence.calls:
        assert chamada["layer"] == "gold"
        assert chamada["modo"] == "producao"


def test_ultima_atualizacao_le_manifest_de_producao(tmp_path):
    manifest = {
        "fato_macro": {"atualizado_em": "2026-10-28T10:00:00"},
        "dim_tempo": {"atualizado_em": "2026-10-29T08:30:00"},
    }
    (tmp_path / "_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert dl.ultima_atualizacao("fato_macro") == datetime(2026, 10, 28, 10, 0, 0)
    assert dl.ultima_atualizacao() == datetime(2026, 10, 29, 8, 30, 0)


def test_ultima_atualizacao_sem_manifest_retorna_none():
    assert dl.ultima_atualizacao() is None
    assert dl.ultima_atualizacao("fato_macro") is None


def test_load_dim_carrega_dimensao_completa(neon):
    carga = dl.load_dim("dim_empresa")
    assert carga.fonte == "neon"
    assert len(carga.dados) == 3
    sql, params = neon.consultas_em("dim_empresa")[0]
    assert "WHERE" not in sql
    assert params == {}