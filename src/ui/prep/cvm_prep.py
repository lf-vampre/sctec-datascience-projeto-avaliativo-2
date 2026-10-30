"""Funções puras de preparação de dados para o Dashboard Fundamentalista CVM (D2)."""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


def painel_anual(
    fato_demonstrativos: pd.DataFrame,
    dim_empresa: pd.DataFrame,
    dim_indicador: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    """Consolida os demonstrativos financeiros no grão empresa x ano.

    Retorna o DataFrame pivoteado e uma lista de avisos de qualidade.
    """
    avisos: List[str] = []

    if fato_demonstrativos.empty or dim_empresa.empty or dim_indicador.empty:
        return pd.DataFrame(), avisos

    df = fato_demonstrativos.merge(dim_empresa, on="sk_empresa", how="inner")
    df = df.merge(dim_indicador, on="sk_indicador", how="inner")

    if df.empty:
        return pd.DataFrame(), avisos

    # Extrai ano do sk_tempo (formato YYYYMMDD ou YYYY1231)
    df["ano"] = df["sk_tempo"] // 10000

    # Sinaliza exercícios que não terminam em 31/12
    exercicios_fora_dez = df[~df["sk_tempo"].astype(str).str.endswith("1231")]
    if not exercicios_fora_dez.empty:
        empresas_fora = exercicios_fora_dez["ticker"].unique().tolist()
        avisos.append(
            f"Exercício encerrado fora de 31/12 para as empresas: {', '.join(empresas_fora)}"
        )

    # Identifica PL para tratamento de ROE inválido (PL <= 0)
    pl_mask = (df["codigo"] == "PATRIMONIO_LIQUIDO") & (df["valor"] <= 0)
    if pl_mask.any():
        empresas_pl_neg = df.loc[pl_mask, ["ticker", "ano"]].drop_duplicates()
        for _, row in empresas_pl_neg.iterrows():
            avisos.append(
                f"PL <= 0 detectado para {row['ticker']} no ano {row['ano']}. ROE desconsiderado."
            )

    # Trata ROE com PL <= 0 desconsiderando a linha de ROE correspondente
    roe_inv_idx = df[
        (df["codigo"] == "ROE")
        & df.set_index(["sk_empresa", "ano"]).index.isin(
            df[pl_mask].set_index(["sk_empresa", "ano"]).index
        )
    ].index
    df.loc[roe_inv_idx, "valor"] = np.nan

    # Pivota indicadores para colunas
    cols_meta = [
        "sk_empresa",
        "ticker",
        "setor_analitico",
        "tipo_plano",
        "exportadora_commodities",
        "ano",
    ]

    pivot = df.pivot_table(
        index=cols_meta,
        columns="codigo",
        values="valor",
        aggfunc="first",
    ).reset_index()

    pivot.columns.name = None

    # Adiciona flag de comparabilidade de receita (ADR-09)
    pivot["comparavel_receita"] = pivot["tipo_plano"] != "financeira"

    # Garante a presença de colunas esperadas
    colunas_esperadas = [
        "RECEITA_LIQUIDA",
        "LUCRO_LIQUIDO",
        "EBIT",
        "MARGEM_LIQUIDA",
        "MARGEM_EBIT",
        "ROE",
        "LIQUIDEZ_CORRENTE",
        "DIVIDA_LIQUIDA",
        "RECEITA_INTERMEDIACAO",
        "PATRIMONIO_LIQUIDO",
    ]
    for col in colunas_esperadas:
        if col not in pivot.columns:
            pivot[col] = np.nan

    # Sinaliza empresas financeiras tratadas sob ADR-09
    fin_count = pivot[pivot["tipo_plano"] == "financeira"]["ticker"].nunique()
    if fin_count > 0:
        avisos.append(
            f"{fin_count} instituição(ões) financeira(s) no painel. "
            "RECEITA_INTERMEDIACAO tratada separadamente e métricas operacionais/dívida mantidas nulas."
        )

    return pivot.sort_values(["ticker", "ano"]), avisos


def kpis_cvm(painel: pd.DataFrame, ano_foco: int) -> Dict[str, Any]:
    """Calcula KPIs agregados e deltas anuais like-for-like para o exercício de foco."""
    res: Dict[str, Any] = {
        "ano_foco": ano_foco,
        "ano_anterior": ano_foco - 1,
        "receita_liquida_total": None,
        "receita_delta_anual": None,
        "receita_delta_pct": None,
        "lucro_liquido_total": None,
        "lucro_delta_anual": None,
        "lucro_delta_pct": None,
        "roe_medio": None,
        "roe_delta_pp": None,
        "roe_mediana": None,
        "liquidez_corrente_media": None,
        "liquidez_delta_abs": None,
        "n_empresas_receita": 0,
        "n_empresas_lucro": 0,
        "n_empresas_roe": 0,
        "n_empresas_liquidez": 0,
        "novas_empresas_foco": [],
    }

    if painel.empty:
        return res

    df_curr = painel[painel["ano"] == ano_foco]
    df_prev = painel[painel["ano"] == (ano_foco - 1)]

    if df_curr.empty:
        return res

    # Novas empresas em relação ao ano anterior
    if not df_prev.empty:
        emp_curr = set(df_curr["ticker"].unique())
        emp_prev = set(df_prev["ticker"].unique())
        res["novas_empresas_foco"] = sorted(list(emp_curr - emp_prev))

    # 1. Receita Líquida Total (Apenas Industriais / Comparáveis)
    ind_curr = df_curr[df_curr["comparavel_receita"] & df_curr["RECEITA_LIQUIDA"].notna()]
    if not ind_curr.empty:
        rec_tot = float(ind_curr["RECEITA_LIQUIDA"].sum())
        res["receita_liquida_total"] = rec_tot
        res["n_empresas_receita"] = len(ind_curr)

        # Delta Like-for-Like
        if not df_prev.empty:
            ind_prev = df_prev[df_prev["comparavel_receita"] & df_prev["RECEITA_LIQUIDA"].notna()]
            common_tickers = set(ind_curr["ticker"]).intersection(set(ind_prev["ticker"]))
            if common_tickers:
                rec_curr_lfl = float(ind_curr[ind_curr["ticker"].isin(common_tickers)]["RECEITA_LIQUIDA"].sum())
                rec_prev_lfl = float(ind_prev[ind_prev["ticker"].isin(common_tickers)]["RECEITA_LIQUIDA"].sum())
                res["receita_delta_anual"] = rec_curr_lfl - rec_prev_lfl
                if rec_prev_lfl != 0:
                    res["receita_delta_pct"] = ((rec_curr_lfl / rec_prev_lfl) - 1.0) * 100.0

    # 2. Lucro Líquido Consolidado (Todas as Empresas)
    lucro_curr = df_curr[df_curr["LUCRO_LIQUIDO"].notna()]
    if not lucro_curr.empty:
        lucro_tot = float(lucro_curr["LUCRO_LIQUIDO"].sum())
        res["lucro_liquido_total"] = lucro_tot
        res["n_empresas_lucro"] = len(lucro_curr)

        # Delta Like-for-Like
        if not df_prev.empty:
            lucro_prev = df_prev[df_prev["LUCRO_LIQUIDO"].notna()]
            common_tickers = set(lucro_curr["ticker"]).intersection(set(lucro_prev["ticker"]))
            if common_tickers:
                l_curr_lfl = float(lucro_curr[lucro_curr["ticker"].isin(common_tickers)]["LUCRO_LIQUIDO"].sum())
                l_prev_lfl = float(lucro_prev[lucro_prev["ticker"].isin(common_tickers)]["LUCRO_LIQUIDO"].sum())
                res["lucro_delta_anual"] = l_curr_lfl - l_prev_lfl
                if l_prev_lfl != 0:
                    res["lucro_delta_pct"] = ((l_curr_lfl / abs(l_prev_lfl)) - 1.0) * 100.0

    # 3. ROE Médio e Mediana (Empresas com ROE Válido)
    roe_curr = df_curr[df_curr["ROE"].notna()]
    if not roe_curr.empty:
        res["roe_medio"] = float(roe_curr["ROE"].mean())
        res["roe_mediana"] = float(roe_curr["ROE"].median())
        res["n_empresas_roe"] = len(roe_curr)

        # Delta Like-for-Like (p.p.)
        if not df_prev.empty:
            roe_prev = df_prev[df_prev["ROE"].notna()]
            common_tickers = set(roe_curr["ticker"]).intersection(set(roe_prev["ticker"]))
            if common_tickers:
                roe_curr_lfl = float(roe_curr[roe_curr["ticker"].isin(common_tickers)]["ROE"].mean())
                roe_prev_lfl = float(roe_prev[roe_prev["ticker"].isin(common_tickers)]["ROE"].mean())
                res["roe_delta_pp"] = roe_curr_lfl - roe_prev_lfl

    # 4. Liquidez Corrente Média (Apenas Industriais)
    liq_curr = df_curr[df_curr["comparavel_receita"] & df_curr["LIQUIDEZ_CORRENTE"].notna()]
    if not liq_curr.empty:
        res["liquidez_corrente_media"] = float(liq_curr["LIQUIDEZ_CORRENTE"].mean())
        res["n_empresas_liquidez"] = len(liq_curr)

        # Delta Like-for-Like (absoluto)
        if not df_prev.empty:
            liq_prev = df_prev[df_prev["comparavel_receita"] & df_prev["LIQUIDEZ_CORRENTE"].notna()]
            common_tickers = set(liq_curr["ticker"]).intersection(set(liq_prev["ticker"]))
            if common_tickers:
                liq_curr_lfl = float(liq_curr[liq_curr["ticker"].isin(common_tickers)]["LIQUIDEZ_CORRENTE"].mean())
                liq_prev_lfl = float(liq_prev[liq_prev["ticker"].isin(common_tickers)]["LIQUIDEZ_CORRENTE"].mean())
                res["liquidez_delta_abs"] = liq_curr_lfl - liq_prev_lfl

    return res


def crescimento_receita(
    painel: pd.DataFrame, ano_ini: int, ano_fim: int
) -> Dict[str, Any]:
    """Calcula variação total, CAGR e agrupamentos por setor entre dois anos."""
    if painel.empty:
        return {"empresas": pd.DataFrame(), "setores": pd.DataFrame(), "contracoes": []}

    df_sub = painel[
        (painel["ano"].isin([ano_ini, ano_fim])) & painel["comparavel_receita"]
    ]

    piv = df_sub.pivot(index=["ticker", "setor_analitico"], columns="ano", values="RECEITA_LIQUIDA")

    if ano_ini not in piv.columns or ano_fim not in piv.columns:
        return {"empresas": pd.DataFrame(), "setores": pd.DataFrame(), "contracoes": []}

    valid = piv.dropna(subset=[ano_ini, ano_fim]).reset_index()

    if valid.empty:
        return {"empresas": pd.DataFrame(), "setores": pd.DataFrame(), "contracoes": []}

    n_anos = ano_fim - ano_ini
    valid["var_abs"] = valid[ano_fim] - valid[ano_ini]
    valid["var_pct"] = (valid[ano_fim] / valid[ano_ini] - 1.0) * 100.0

    if n_anos > 0:
        valid["cagr_pct"] = (
            (valid[ano_fim] / valid[ano_ini]) ** (1.0 / n_anos) - 1.0
        ) * 100.0
    else:
        valid["cagr_pct"] = np.nan

    valid["contracao"] = valid[ano_fim] < valid[ano_ini]
    contracoes = valid[valid["contracao"]]["ticker"].tolist()

    # Agregação setorial por soma das receitas
    setores = (
        valid.groupby("setor_analitico")[[ano_ini, ano_fim]]
        .sum()
        .reset_index()
    )
    setores["var_abs"] = setores[ano_fim] - setores[ano_ini]
    setores["var_pct"] = (setores[ano_fim] / setores[ano_ini] - 1.0) * 100.0
    if n_anos > 0:
        setores["cagr_pct"] = (
            (setores[ano_fim] / setores[ano_ini]) ** (1.0 / n_anos) - 1.0
        ) * 100.0

    return {
        "empresas": valid.sort_values("var_pct", ascending=False),
        "setores": setores.sort_values("var_pct", ascending=False),
        "contracoes": contracoes,
    }


def margens_por_ano(painel: pd.DataFrame) -> pd.DataFrame:
    """Retorna a série temporal da Margem Líquida por empresa industrial."""
    if painel.empty:
        return pd.DataFrame(columns=["ticker", "ano", "MARGEM_LIQUIDA"])

    df_sub = painel[painel["comparavel_receita"] & painel["MARGEM_LIQUIDA"].notna()]
    return df_sub[["ticker", "setor_analitico", "ano", "MARGEM_LIQUIDA"]].sort_values(
        ["ticker", "ano"]
    )


def dispersao_margem_roe(painel: pd.DataFrame, ano_foco: int) -> Dict[str, Any]:
    """Prepara os pontos de dispersão Margem Líquida x ROE e classifica em quadrantes."""
    res: Dict[str, Any] = {
        "pontos": pd.DataFrame(),
        "mediana_margem": None,
        "mediana_roe": None,
    }

    if painel.empty:
        return res

    df_curr = painel[
        (painel["ano"] == ano_foco)
        & painel["comparavel_receita"]
        & painel["MARGEM_LIQUIDA"].notna()
        & painel["ROE"].notna()
    ].copy()

    if df_curr.empty:
        return res

    med_m = float(df_curr["MARGEM_LIQUIDA"].median())
    med_r = float(df_curr["ROE"].median())

    res["mediana_margem"] = med_m
    res["mediana_roe"] = med_r

    def _quadrante(row: pd.Series) -> str:
        m_alta = row["MARGEM_LIQUIDA"] >= med_m
        r_alto = row["ROE"] >= med_r
        if m_alta and r_alto:
            return "Líder (Margem Alta / ROE Alto)"
        if not m_alta and r_alto:
            return "Giro (Margem Baixa / ROE Alto)"
        if m_alta and not r_alto:
            return "Nicho (Margem Alta / ROE Baixo)"
        return "Desafio (Margem Baixa / ROE Baixo)"

    df_curr["quadrante"] = df_curr.apply(_quadrante, axis=1)
    res["pontos"] = df_curr[
        [
            "ticker",
            "setor_analitico",
            "RECEITA_LIQUIDA",
            "MARGEM_LIQUIDA",
            "ROE",
            "quadrante",
        ]
    ]

    return res


def distribuicao_ebit(
    painel: pd.DataFrame,
    anos: Optional[List[int]] = None,
    agrupamento: str = "setor",
) -> pd.DataFrame:
    """Prepara as observações de Margem EBIT para análise de distribuição por grupo."""
    if painel.empty:
        return pd.DataFrame()

    df_sub = painel[painel["comparavel_receita"] & painel["MARGEM_EBIT"].notna()]

    if anos:
        df_sub = df_sub[df_sub["ano"].isin(anos)]

    if df_sub.empty:
        return pd.DataFrame()

    if agrupamento == "commodities":
        df_sub["grupo"] = np.where(
            df_sub["exportadora_commodities"], "Commodities", "Demais Setores"
        )
    else:
        df_sub["grupo"] = df_sub["setor_analitico"]

    return df_sub[["ticker", "ano", "grupo", "MARGEM_EBIT"]].sort_values(["grupo", "ano"])


def solvencia(
    painel: pd.DataFrame, ano_foco: int, limiar_liquidez: float = 1.5
) -> pd.DataFrame:
    """Classifica e analisa os níveis de solvência e liquidez das empresas industriais."""
    if painel.empty:
        return pd.DataFrame()

    df_curr = painel[
        (painel["ano"] == ano_foco)
        & painel["comparavel_receita"]
        & (painel["LIQUIDEZ_CORRENTE"].notna() | painel["DIVIDA_LIQUIDA"].notna())
    ].copy()

    if df_curr.empty:
        return pd.DataFrame()

    df_curr["atencao_liquidez"] = df_curr["LIQUIDEZ_CORRENTE"] < limiar_liquidez
    df_curr["caixa_liquido"] = df_curr["DIVIDA_LIQUIDA"] < 0

    return df_curr[
        [
            "ticker",
            "setor_analitico",
            "DIVIDA_LIQUIDA",
            "LIQUIDEZ_CORRENTE",
            "atencao_liquidez",
            "caixa_liquido",
        ]
    ].sort_values("LIQUIDEZ_CORRENTE")


def distribuicao_setorial(
    painel: pd.DataFrame, ano_foco: int
) -> Dict[str, Any]:
    """Agrupa a Receita Líquida por setor no ano de foco e relata exclusões."""
    res: Dict[str, Any] = {
        "setores": pd.DataFrame(),
        "excluidos_bancos": [],
    }

    if painel.empty:
        return res

    df_curr = painel[painel["ano"] == ano_foco]
    if df_curr.empty:
        return res

    bancos = df_curr[~df_curr["comparavel_receita"]]["ticker"].unique().tolist()
    res["excluidos_bancos"] = bancos

    ind = df_curr[df_curr["comparavel_receita"] & df_curr["RECEITA_LIQUIDA"].notna()]
    if ind.empty:
        return res

    agg = (
        ind.groupby("setor_analitico")["RECEITA_LIQUIDA"]
        .sum()
        .reset_index()
        .sort_values("RECEITA_LIQUIDA", ascending=False)
    )

    tot = agg["RECEITA_LIQUIDA"].sum()
    if tot > 0:
        agg["participacao_pct"] = (agg["RECEITA_LIQUIDA"] / tot) * 100.0
    else:
        agg["participacao_pct"] = 0.0

    res["setores"] = agg
    return res