"""Funções puras de preparação de dados para o Dashboard Macro (D1)."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def _preparar_fato_dim(
    fato_macro: pd.DataFrame, dim_indicador: pd.DataFrame
) -> pd.DataFrame:
    """Realiza o merge de fato_macro com dim_indicador e formata a data."""
    if fato_macro.empty or dim_indicador.empty:
        return pd.DataFrame()

    df = fato_macro.merge(dim_indicador, on="sk_indicador", how="inner")
    if df.empty:
        return pd.DataFrame()

    if "data" in df.columns:
        df["dt"] = pd.to_datetime(df["data"])
    elif "sk_tempo" in df.columns:
        df["dt"] = pd.to_datetime(df["sk_tempo"].astype(str), format="%Y%m%d")
    else:
        return pd.DataFrame()

    return df.sort_values("dt")


def serie_diaria(
    fato_macro: pd.DataFrame, dim_indicador: pd.DataFrame, codigo: str
) -> pd.Series:
    """Extrai a série temporal diária de um indicador específico como pd.Series."""
    df = _preparar_fato_dim(fato_macro, dim_indicador)
    if df.empty:
        return pd.Series(dtype=float)

    sub = df[df["codigo"] == codigo]
    if sub.empty:
        return pd.Series(dtype=float)

    s = sub.set_index("dt")["valor"].astype(float)
    return s.sort_index()


def painel_mensal(
    fato_macro: pd.DataFrame, dim_indicador: pd.DataFrame
) -> pd.DataFrame:
    """Consolida os dados de fato_macro no grão mensal (ano_mes) por indicador.
    
    Respeita a regra de agregação (agg_mensal) definida em dim_indicador sem forward-fill.
    """
    df = _preparar_fato_dim(fato_macro, dim_indicador)
    if df.empty:
        return pd.DataFrame()

    df["ano_mes"] = df["dt"].dt.strftime("%Y-%m")

    colunas_esperadas = [
        "SELIC_META",
        "SELIC_EFETIVA",
        "IPCA_12M",
        "IPCA_MENSAL",
        "PTAX_VENDA",
        "IBC_BR_SA",
        "JURO_REAL_EXPOST",
        "POUPANCA",
    ]

    agregados = []
    for (ano_mes, codigo), group in df.groupby(["ano_mes", "codigo"]):
        agg_rule = group["agg_mensal"].iloc[0] if "agg_mensal" in group.columns else "ultimo"
        group_sorted = group.sort_values("dt")

        if agg_rule == "media":
            val = group_sorted["valor"].mean()
        elif agg_rule == "soma":
            val = group_sorted["valor"].sum()
        else:  # 'ultimo'
            val = group_sorted["valor"].iloc[-1]

        agregados.append({"ano_mes": ano_mes, "codigo": codigo, "valor": float(val)})

    if not agregados:
        return pd.DataFrame(columns=colunas_esperadas)

    df_agg = pd.DataFrame(agregados)
    pivot = df_agg.pivot(index="ano_mes", columns="codigo", values="valor")

    for col in colunas_esperadas:
        if col not in pivot.columns:
            pivot[col] = np.nan

    # Recalculo dinamico do Juro Real por Fisher se a coluna estiver totalmente nula
    if pivot["JURO_REAL_EXPOST"].isna().all() and "SELIC_META" in pivot.columns and "IPCA_12M" in pivot.columns:
        from src.etl.warehouse.metrics_calculator import juro_real_fisher
        pivot["JURO_REAL_EXPOST"] = juro_real_fisher(pivot["SELIC_META"], pivot["IPCA_12M"])

    return pivot[colunas_esperadas].sort_index()


def kpis_macro(
    painel: pd.DataFrame, diaria_selic: pd.Series, diaria_ptax: pd.Series
) -> Dict[str, Any]:
    """Calcula os valores atuais e deltas para os KPIs do Dashboard Macro."""
    res: Dict[str, Any] = {
        "selic_vigente": None,
        "selic_delta_12m": None,
        "selic_motivo": None,
        "ipca_12m": None,
        "ipca_delta_12m": None,
        "ipca_motivo": None,
        "juro_real": None,
        "juro_real_delta_12m": None,
        "juro_real_motivo": None,
        "ptax_atual": None,
        "ptax_medio": None,
        "ptax_delta_12m_pct": None,
        "ptax_vs_media_pct": None,
        "ptax_motivo": None,
    }

    # 1. Selic Meta Vigente
    clean_selic = diaria_selic.dropna()
    if not clean_selic.empty:
        selic_curr = float(clean_selic.iloc[-1])
        res["selic_vigente"] = selic_curr
        dt_last = clean_selic.index[-1]
        dt_12m = dt_last - pd.DateOffset(years=1)
        sub_12m = clean_selic[clean_selic.index <= dt_12m]
        if not sub_12m.empty:
            selic_prev = float(sub_12m.iloc[-1])
            res["selic_delta_12m"] = selic_curr - selic_prev
        else:
            res["selic_motivo"] = "Janela menor que 12 meses para Selic"

    # 2. IPCA 12m
    if not painel.empty and "IPCA_12M" in painel.columns:
        s_ipca = painel["IPCA_12M"].dropna()
        if not s_ipca.empty:
            res["ipca_12m"] = float(s_ipca.iloc[-1])
            if len(s_ipca) >= 13:
                res["ipca_delta_12m"] = float(s_ipca.iloc[-1] - s_ipca.iloc[-13])
            else:
                res["ipca_motivo"] = "Janela mensal menor que 12 meses"

    # 3. Juro Real Ex-Post (converte fração decimal para % a.a. nos KPIs)
    if not painel.empty and "JURO_REAL_EXPOST" in painel.columns:
        s_jr = painel["JURO_REAL_EXPOST"].dropna()
        if not s_jr.empty:
            val_jr = float(s_jr.iloc[-1])
            res["juro_real"] = val_jr * 100.0 if abs(val_jr) <= 1.0 else val_jr
            if len(s_jr) >= 13:
                val_prev = float(s_jr.iloc[-13])
                delta_jr = val_jr - val_prev
                res["juro_real_delta_12m"] = delta_jr * 100.0 if abs(delta_jr) <= 1.0 else delta_jr
            else:
                res["juro_real_motivo"] = "Janela mensal menor que 12 meses"

    # 4. PTAX
    clean_ptax = diaria_ptax.dropna()
    if not clean_ptax.empty:
        ptax_curr = float(clean_ptax.iloc[-1])
        ptax_mean = float(clean_ptax.mean())
        res["ptax_atual"] = ptax_curr
        res["ptax_medio"] = ptax_mean
        if ptax_mean != 0:
            res["ptax_vs_media_pct"] = ((ptax_curr / ptax_mean) - 1.0) * 100.0

        dt_last_ptax = clean_ptax.index[-1]
        dt_12m_ptax = dt_last_ptax - pd.DateOffset(years=1)
        sub_ptax_12m = clean_ptax[clean_ptax.index <= dt_12m_ptax]
        if not sub_ptax_12m.empty:
            ptax_prev = float(sub_ptax_12m.iloc[-1])
            if ptax_prev != 0:
                res["ptax_delta_12m_pct"] = ((ptax_curr / ptax_prev) - 1.0) * 100.0
        else:
            res["ptax_motivo"] = "Janela menor que 12 meses para PTAX"

    return res


def ciclos_selic(
    selic_diaria: pd.Series, dias_estavel: int = 90
) -> pd.DataFrame:
    """Segmenta a série da Selic em ciclos de aperto, corte e manutenção.
    
    Identifica blocos de taxa constante. Intervalos contínuos de estabilidade
    com duração maior ou igual a dias_estavel são classificados como 'manutencao'.
    Intervalos de mudança contínua são classificados como 'aperto' ou 'corte'
    e fundidos em blocos consolidados.
    """
    clean = selic_diaria.dropna().sort_index()
    if clean.empty:
        return pd.DataFrame(columns=["inicio", "fim", "tipo", "taxa_inicio", "taxa_fim"])

    # Agrupa por blocos de valor contínuo
    mudancas = clean.ne(clean.shift()).cumsum()

    blocos = []
    prev_val = None

    for _, group in clean.groupby(mudancas):
        dt_ini = group.index[0]
        dt_fim = group.index[-1]
        val = float(group.iloc[0])
        dias = (dt_fim - dt_ini).days + 1

        if prev_val is None:
            tipo = "manutencao"
        elif dias >= dias_estavel:
            tipo = "manutencao"
        elif val > prev_val:
            tipo = "aperto"
        elif val < prev_val:
            tipo = "corte"
        else:
            tipo = "manutencao"

        blocos.append({
            "inicio": dt_ini,
            "fim": dt_fim,
            "tipo": tipo,
            "taxa_inicio": val if prev_val is None else prev_val,
            "taxa_fim": val,
        })
        prev_val = val

    if not blocos:
        return pd.DataFrame(columns=["inicio", "fim", "tipo", "taxa_inicio", "taxa_fim"])

    # Funde blocos consecutivos do mesmo tipo
    ciclos_fundidos = []
    atual = blocos[0].copy()

    for b in blocos[1:]:
        if b["tipo"] == atual["tipo"]:
            atual["fim"] = b["fim"]
            atual["taxa_fim"] = b["taxa_fim"]
        else:
            ciclos_fundidos.append(atual)
            atual = b.copy()
    ciclos_fundidos.append(atual)

    return pd.DataFrame(ciclos_fundidos)


def janelas_acima_media(
    ptax_diaria: pd.Series, minimo_dias: int = 5
) -> pd.DataFrame:
    """Identifica intervalos contínuos em que a PTAX ficou acima da média do período."""
    clean = ptax_diaria.dropna().sort_index()
    if clean.empty:
        return pd.DataFrame(columns=["inicio", "fim", "dias", "ptax_max", "ptax_medio"])

    media = clean.mean()
    acima = clean > media

    blocos = (acima != acima.shift()).cumsum()
    janelas = []

    for _, group in clean[acima].groupby(blocos[acima]):
        dias = (group.index[-1] - group.index[0]).days + 1
        if dias >= minimo_dias:
            janelas.append({
                "inicio": group.index[0],
                "fim": group.index[-1],
                "dias": dias,
                "ptax_max": float(group.max()),
                "ptax_medio": float(group.mean()),
            })

    return pd.DataFrame(janelas)


def correlacao(
    painel: pd.DataFrame, colunas: Optional[List[str]] = None, modo: str = "niveis"
) -> Dict[str, Any]:
    """Calcula a matriz de correlação de Pearson no painel mensal."""
    if painel.empty:
        return {"matriz": pd.DataFrame(), "n_obs": 0}

    cols = colunas if colunas else [c for c in painel.columns if painel[c].notna().any()]
    df_sub = painel[cols].dropna()

    if modo == "variacoes":
        df_calc = df_sub.pct_change().dropna()
    else:
        df_calc = df_sub

    if df_calc.empty:
        return {"matriz": pd.DataFrame(), "n_obs": 0}

    matriz = df_calc.corr(method="pearson")
    return {"matriz": matriz, "n_obs": len(df_calc)}


def correlacao_defasada(
    painel: pd.DataFrame, x: str, y: str, max_defasagem: int = 12
) -> pd.DataFrame:
    """Calcula a correlação de Pearson entre x antecedendo y em k meses."""
    if painel.empty or x not in painel.columns or y not in painel.columns:
        return pd.DataFrame(columns=["defasagem", "r", "n_obs"])

    resultados = []
    df_clean = painel[[x, y]].dropna()

    for k in range(0, max_defasagem + 1):
        x_shifted = df_clean[x].shift(k)
        valid = pd.DataFrame({"x": x_shifted, "y": df_clean[y]}).dropna()
        if len(valid) >= 3:
            r = float(valid["x"].corr(valid["y"]))
            resultados.append({"Defasagem (meses)": k, "Correlação de Pearson (r)": r, "Observações (n)": len(valid)})
        else:
            resultados.append({"Defasagem (meses)": k, "Correlação de Pearson (r)": np.nan, "Observações (n)": len(valid)})

    return pd.DataFrame(resultados)


def juro_real_maximos(painel: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Retorna os n períodos com maior Juro Real Ex-Post no painel mensal."""
    if painel.empty or "JURO_REAL_EXPOST" not in painel.columns:
        return pd.DataFrame(columns=["ano_mes", "JURO_REAL_EXPOST"])

    df = painel[["JURO_REAL_EXPOST"]].dropna().reset_index()
    return df.sort_values("JURO_REAL_EXPOST", ascending=False).head(n)