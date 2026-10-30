"""Carregamento da camada Ouro para a UI: Neon via st.connection, contingência em Parquet e cache.

Único módulo da UI que acessa banco/arquivo. Nunca lê data/_sandbox/ (ADR-13).
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import pandas as pd
import streamlit as st

from src.config import settings
from src.etl.warehouse.persistence import Persistence
from src.models.contracts import Filtros
from src.utils import paths

_TTL_STATUS_S = 60

DIMENSOES: Tuple[str, ...] = ("dim_tempo", "dim_empresa", "dim_indicador")

# Whitelist de tabelas e colunas aceitas na montagem do SQL (dicionário de dados da Ouro)
TABELAS: Dict[str, Tuple[str, ...]] = {
    "dim_tempo": (
        "sk_tempo", "data", "ano", "semestre", "trimestre", "mes", "ano_mes", "dia_util_b3",
    ),
    "dim_empresa": (
        "sk_empresa", "ticker", "cd_cvm", "cnpj", "denom_cia", "setor_cvm", "setor_analitico",
        "tipo_plano", "exportadora_commodities", "tem_cvm", "tem_b3",
    ),
    "dim_indicador": (
        "sk_indicador", "codigo", "nome", "fonte", "tipo", "unidade", "granularidade",
        "agg_mensal", "sgs_codigo", "cd_conta", "regra_calculo",
    ),
    "fato_macro": ("sk_tempo", "sk_indicador", "valor"),
    "fato_cotacoes": (
        "sk_tempo", "sk_empresa", "open", "high", "low", "close", "volume",
        "volume_fin_aprox", "retorno_diario", "sma_21", "sma_50",
    ),
    "fato_demonstrativos": ("sk_tempo", "sk_empresa", "sk_indicador", "valor"),
}

_OPERADORES = {"=", ">=", "<=", "in"}

Regra = Tuple[str, str, Any]


class DadosIndisponiveis(Exception):
    """Neon e Parquet indisponíveis para a tabela solicitada."""


@dataclass
class Carga:
    """Resultado de uma leitura da Ouro com a origem dos dados."""

    dados: pd.DataFrame
    fonte: Literal["neon", "parquet"]
    atualizado_em: Optional[datetime]


# ------------------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------------------
def _ler_manifest() -> Dict[str, Any]:
    caminho = paths.GOLD_DIR / "_manifest.json"
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _parse_iso(valor: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(valor) if valor else None
    except (TypeError, ValueError):
        return None


def ultima_atualizacao(tabela: Optional[str] = None) -> Optional[datetime]:
    """Data da última gravação da Ouro (manifest). Sem tabela, retorna a mais recente entre todas."""
    manifest = _ler_manifest()
    if tabela is not None:
        return _parse_iso(manifest.get(tabela, {}).get("atualizado_em"))
    datas = [_parse_iso(item.get("atualizado_em")) for item in manifest.values() if isinstance(item, dict)]
    datas = [d for d in datas if d is not None]
    return max(datas) if datas else None


@st.cache_data(ttl=_TTL_STATUS_S, show_spinner=False)
def fonte_em_uso() -> str:
    """'neon' se a conexão responde; caso contrário 'parquet'."""
    try:
        st.connection("postgresql", type="sql").query("SELECT 1", ttl=0)
        return "neon"
    except Exception:
        return "parquet"


# ------------------------------------------------------------------------------
# Validação e tradução de filtros
# ------------------------------------------------------------------------------
def _validar(tabela: str, colunas: Optional[Sequence[str]]) -> Tuple[str, ...]:
    """Valida tabela e colunas contra a whitelist e retorna as colunas finais."""
    if tabela not in TABELAS:
        raise ValueError(f"Tabela '{tabela}' fora da whitelist da Ouro.")
    permitidas = TABELAS[tabela]
    if not colunas:
        return permitidas
    invalidas = [c for c in colunas if c not in permitidas]
    if invalidas:
        raise ValueError(f"Colunas fora da whitelist de '{tabela}': {invalidas}")
    return tuple(colunas)


def _sk_tempo(data_iso: str) -> int:
    return int(date.fromisoformat(data_iso).strftime("%Y%m%d"))


def _montar_regras(tabela: str, filtros: Optional[Filtros]) -> Tuple[List[Regra], bool]:
    """Converte Filtros em regras (coluna, operador, valor). Retorna (regras, vazio).

    vazio=True quando algum filtro aplicável está sem seleção (resultado vazio por definição).
    """
    if filtros is None:
        return [], False

    colunas = TABELAS[tabela]
    regras: List[Regra] = []

    if "sk_tempo" in colunas:
        ini, fim = _sk_tempo(filtros.periodo[0]), _sk_tempo(filtros.periodo[1])
        if tabela == "fato_demonstrativos":
            # Exercício anual ancorado em 31/12: período cobre o ano cheio
            ini = (ini // 10000) * 10000 + 101
            fim = (fim // 10000) * 10000 + 1231
        regras += [("sk_tempo", ">=", ini), ("sk_tempo", "<=", fim)]

    if tabela in ("fato_cotacoes", "fato_demonstrativos"):
        if not filtros.tickers or not filtros.setores:
            return [], True
        emp = load_dim("dim_empresa").dados
        selecionadas = emp[emp["ticker"].isin(filtros.tickers) & emp["setor_analitico"].isin(filtros.setores)]
        sks = sorted(int(v) for v in selecionadas["sk_empresa"].unique())
        if not sks:
            return [], True
        regras.append(("sk_empresa", "in", sks))

    if tabela == "fato_macro":
        if not filtros.indicadores_bacen:
            return [], True
        ind = load_dim("dim_indicador").dados
        selecionados = ind[ind["codigo"].isin(filtros.indicadores_bacen)]
        sks = sorted(int(v) for v in selecionados["sk_indicador"].unique())
        if not sks:
            return [], True
        regras.append(("sk_indicador", "in", sks))

    return regras, False


def _sql_where(tabela: str, regras: List[Regra]) -> Tuple[str, Dict[str, Any]]:
    """WHERE parametrizado: colunas só da whitelist, valores sempre como parâmetros."""
    clausulas: List[str] = []
    params: Dict[str, Any] = {}
    for i, (coluna, op, valor) in enumerate(regras):
        if coluna not in TABELAS[tabela] or op not in _OPERADORES:
            raise ValueError(f"Filtro inválido: ({coluna}, {op}).")
        nome = f"p_{i}"
        if op == "in":
            clausulas.append(f'"{coluna}" = ANY(:{nome})')
            params[nome] = list(valor)
        else:
            clausulas.append(f'"{coluna}" {op} :{nome}')
            params[nome] = valor
    return (" WHERE " + " AND ".join(clausulas)) if clausulas else "", params


# ------------------------------------------------------------------------------
# Leitura (Neon → Parquet)
# ------------------------------------------------------------------------------
def _ler_neon(tabela: str, colunas: Tuple[str, ...], regras: List[Regra]) -> pd.DataFrame:
    cols_sql = ", ".join(f'"{c}"' for c in colunas)
    where_sql, params = _sql_where(tabela, regras)
    sql = f'SELECT {cols_sql} FROM "gold"."{tabela}"{where_sql}'
    conn = st.connection("postgresql", type="sql")
    return conn.query(sql, params=params, ttl=0)


def _ler_parquet(tabela: str, colunas: Tuple[str, ...], regras: List[Regra]) -> pd.DataFrame:
    return Persistence().load(
        "gold", tabela, filters=regras or None, columns=list(colunas), somente_parquet=True
    )


def _carregar(tabela: str, colunas: Tuple[str, ...], regras: List[Regra]) -> Carga:
    """Tenta o Neon; qualquer falha cai silenciosamente para o Parquet versionado."""
    atualizado_em = ultima_atualizacao(tabela)

    try:
        return Carga(_ler_neon(tabela, colunas, regras), "neon", atualizado_em)
    except Exception:
        pass

    try:
        df = _ler_parquet(tabela, colunas, regras)
    except Exception as exc:
        raise DadosIndisponiveis(
            "Dados indisponíveis no momento. Execute o DataOps para gerar a camada Ouro."
        ) from exc

    if df.attrs.get("fonte") == "empty":
        raise DadosIndisponiveis(
            "Dados indisponíveis no momento. Execute o DataOps para gerar a camada Ouro."
        )
    return Carga(df, "parquet", atualizado_em)


# ------------------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------------------
# O status da fonte entra na chave do cache: quando o Neon cai ou volta, a chave muda
# e a carga é refeita em até _TTL_STATUS_S, sem esperar o TTL cheio dos dados.
@st.cache_data(ttl=settings.CACHE_TTL_GOLD_SECONDS, show_spinner=False)
def _load_gold_cached(
    tabela: str,
    filtros: Optional[Filtros],
    colunas: Optional[Sequence[str]],
    fonte_status: str,
) -> Carga:
    cols = _validar(tabela, colunas)
    regras, vazio = _montar_regras(tabela, filtros)
    if vazio:
        return Carga(pd.DataFrame(columns=list(cols)), fonte_status, ultima_atualizacao(tabela))
    return _carregar(tabela, cols, regras)


@st.cache_data(ttl=settings.CACHE_TTL_DIM_SECONDS, show_spinner=False)
def _load_dim_cached(nome: str, fonte_status: str) -> Carga:
    return _carregar(nome, TABELAS[nome], [])


def load_gold(
    tabela: str,
    filtros: Optional[Filtros] = None,
    colunas: Optional[Sequence[str]] = None,
) -> Carga:
    """Carrega uma tabela da Ouro com filtros em pushdown (Neon → Parquet), cacheada por TTL."""
    return _load_gold_cached(tabela, filtros, colunas, fonte_em_uso())


def load_dim(nome: str) -> Carga:
    """Carrega uma dimensão completa da Ouro, com TTL maior que os fatos."""
    if nome not in DIMENSOES:
        raise ValueError(f"'{nome}' não é uma dimensão da Ouro.")
    return _load_dim_cached(nome, fonte_em_uso())