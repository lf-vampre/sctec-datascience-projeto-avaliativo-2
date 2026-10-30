"""Módulo de geração de storytelling analítico (Contexto -> Insight -> Ação) para o Dashboard Macro.

Funções puras (sem streamlit) que constroem textos baseados nos dados reais fornecidos.
"""

from typing import Any, Dict
import pandas as pd


def gerar_storytelling_macro(
    painel: pd.DataFrame,
    kpis: Dict[str, Any],
    juros_max: pd.DataFrame,
) -> Dict[str, str]:
    """Gera os textos de Contexto, Insight e Ação com base nos dados do Dashboard Macro.
    
    Evita linguagem causal e utiliza valores calculados dinamicamente.
    """
    if painel.empty:
        return {
            "contexto": "Dados macroeconômicos não disponíveis para o período selecionado.",
            "insight": "Sem dados suficientes para consolidação de insights.",
            "acao": "Verifique o carregamento da base Ouro ou ajuste os filtros da consulta.",
        }

    anos = sorted(painel.index.unique())
    ini_p, fim_p = anos[0], anos[-1]

    # Contexto
    selic_curr = kpis.get("selic_vigente")
    selic_str = f"{selic_curr:.2f}% a.a." if selic_curr is not None else "N/A"
    ipca_curr = kpis.get("ipca_12m")
    ipca_str = f"{ipca_curr:.2f}% a.a." if ipca_curr is not None else "N/A"

    contexto = (
        f"Análise das variáveis macroeconômicas no período de {ini_p} a {fim_p}. "
        f"A taxa Selic Meta encerrou o recorte em {selic_str}, enquanto a inflação oficial (IPCA 12m) "
        f"registrou {ipca_str}."
    )

    # Insight
    picos = []
    if "SELIC_META" in painel.columns and painel["SELIC_META"].notna().any():
        idx_max = painel["SELIC_META"].idxmax()
        val_max = painel.loc[idx_max, "SELIC_META"]
        picos.append(f"a taxa Selic atingiu seu topo em {idx_max} com {val_max:.2f}% a.a.")

    jr_picos = []
    if not juros_max.empty and "JURO_REAL_EXPOST" in juros_max.columns:
        top1 = juros_max.iloc[0]
        dt_jr = top1.get("ano_mes", "")
        val_jr = top1.get("JURO_REAL_EXPOST", 0.0)
        # Converte para percentual se estiver em fração
        val_jr_pct = val_jr * 100.0 if abs(val_jr) <= 1.0 else val_jr
        jr_picos.append(f"o maior Juro Real Ex-Post observado ocorreu em {dt_jr} ({val_jr_pct:.2f}% a.a.)")

    insights_lista = picos + jr_picos
    if insights_lista:
        insight = "Durante o intervalo analisado, " + " e ".join(insights_lista) + "."
    else:
        insight = "Observou-se flutuação contínua das taxas de juros e indicadores de preços no período."

    # Ação
    acao = (
        "Para a gestão financeira corporativa e planejamento de capital, recomenda-se "
        "o monitoramento contínuo das curvas de juros e do comportamento do câmbio. "
        "Em cenários de juro real elevado, estratégias focadas na otimização da dívida "
        "e preservação de caixa tendem a mitigar o custo de carregamento do passivo."
    )

    return {
        "contexto": contexto,
        "insight": insight,
        "acao": acao,
    }