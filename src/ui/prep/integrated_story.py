"""Gerador de relatos analíticos descritivos (Contexto -> Insight -> Ação) para o Dashboard Integrado (D4)."""

from typing import Any, Dict
import pandas as pd


def gerar_story_integrada(
    kpis: Dict[str, Any],
    tabela_aperto: pd.DataFrame,
    tabela_setorial: pd.DataFrame,
    df_estresse_ret: pd.DataFrame,
    df_ranking: pd.DataFrame,
) -> Dict[str, str]:
    """Gera síntese narrativa descritiva sem termos causais nem recomendações de investimento."""
    # Contexto
    selic_v = kpis.get("selic_vigente")
    selic_str = f"{selic_v:.2f}% a.a." if selic_v is not None else "N/A"
    rec_tot = kpis.get("receita_consolidada")
    rec_str = f"R\\$ {rec_tot/1e9:.2f} B" if rec_tot is not None else "N/A"
    lucro_tot = kpis.get("lucro_consolidado")
    lucro_str = f"R\\$ {lucro_tot/1e9:.2f} B" if lucro_tot is not None else "N/A"

    contexto = (
        f"Durante a trajetória observada da política monetária (Selic vigente em {selic_str}), "
        f"a carteira consolidada registrou Receita Líquida Industrial de {rec_str} e Lucro Líquido Consolidado de {lucro_str}."
    )

    # Insight
    detalhes_insight = []
    if not tabela_aperto.empty and "despesa_financeira_b100" in tabela_aperto.columns:
        row_ult = tabela_aperto.iloc[-1]
        desp_b100 = row_ult.get("despesa_financeira_b100")
        if pd.notna(desp_b100):
            detalhes_insight.append(f"o índice de Despesa Financeira atingiu {desp_b100:.1f} (Base 100)")

    if not df_ranking.empty and "setor_analitico" in df_ranking.columns:
        top_setor = df_ranking.iloc[0]["setor_analitico"]
        top_score = df_ranking.iloc[0]["score_final"]
        detalhes_insight.append(f"o setor de {top_setor} registrou a maior pontuação multidimensional média ({top_score:.1f} pts no score final consolidado)")

    if detalhes_insight:
        insight = "Em termos de dinâmica conjunta, " + " e ".join(detalhes_insight) + "."
    else:
        insight = "As métricas refletem o comportamento concomitante dos setores frente às variações de juros e câmbio no período."

    # Ação
    acao = (
        "Recomenda-se acompanhar a evolução descritiva dos indicadores de solvência e rentabilidade "
        "frente às variações macroeconômicas, sem inferir causalidade nem utilizar as observações como recomendação de investimento."
    )

    return {
        "contexto": contexto,
        "insight": insight,
        "acao": acao,
    }