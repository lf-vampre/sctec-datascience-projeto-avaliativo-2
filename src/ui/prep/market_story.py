"""Gerador de relato analítico e storytelling de mercado e risco (sem linguagem causal).

Módulo de funções puras (sem Streamlit, sem I/O).
"""

from typing import Any, Dict, Optional
import pandas as pd

from src.utils.formatting import format_percent


def _fmt_pct(val: Optional[float]) -> str:
    if val is None or pd.isna(val):
        return "N/A"
    return format_percent(val * 100.0)


def gerar_story_mercado(
    kpis: Dict[str, Any],
    tabela_rr: pd.DataFrame,
    df_sma: Optional[pd.DataFrame] = None,
    ticker_sma: Optional[str] = None,
) -> Dict[str, str]:
    """Gera textos analíticos (Contexto, Insight, Ação) com base nas métricas de mercado."""
    if tabela_rr.empty:
        return {
            "contexto": "Sem dados suficientes para consolidação do contexto de mercado.",
            "insight": "Sem observações suficientes para extração de insights.",
            "acao": "Recomenda-se expandir o período ou a seleção de ativos.",
        }

    tab_act = tabela_rr[tabela_rr["ticker"] != "Carteira"].copy()

    # Contexto
    ret_cart = kpis.get("retorno_medio_carteira")
    str_ret_cart = _fmt_pct(ret_cart)
    
    vol_med = kpis.get("volatilidade_media")
    str_vol_med = f"{vol_med * 100.0:.2f}% a.a.".replace(".", ",") if vol_med is not None else "N/A"

    destaque = kpis.get("ativo_destaque", "N/A")
    ret_dest = kpis.get("ativo_destaque_retorno")
    str_ret_dest = _fmt_pct(ret_dest)

    pior = kpis.get("ativo_pior", "N/A")
    ret_pior = kpis.get("ativo_pior_retorno")
    str_ret_pior = _fmt_pct(ret_pior)

    contexto = (
        f"No período analisado, a carteira equiponderada de ativos B3 registrou retorno acumulado médio de "
        f"{str_ret_cart}, acompanhada de volatilidade anualizada média de {str_vol_med}. O ativo com maior "
        f"desempenho nominal foi {destaque} ({str_ret_dest}), enquanto a menor variação observada foi de {pior} ({str_ret_pior})."
    )

    # Insight (Sharpe, Drawdown e Caudas)
    best_sharpe_row = tab_act.sort_values("sharpe", ascending=False).iloc[0] if not tab_act.empty else None
    resiliente_row = tab_act.assign(abs_dd=tab_act["drawdown_maximo"].abs()).sort_values("abs_dd", ascending=True).iloc[0] if not tab_act.empty else None

    str_sharpe = (
        f"O melhor índice de Sharpe empírico foi observado em {best_sharpe_row['ticker']} ({best_sharpe_row['sharpe']:.2f})."
        if best_sharpe_row is not None and pd.notna(best_sharpe_row["sharpe"])
        else "Índice de Sharpe não disponível para os filtros aplicados."
    )

    str_resil = (
        f"Sob a perspectiva de controle de queda, {resiliente_row['ticker']} apresentou o menor drawdown máximo no período "
        f"({resiliente_row['drawdown_maximo']*100.0:.2f}%)."
        if resiliente_row is not None and pd.notna(resiliente_row["drawdown_maximo"])
        else "Informações de drawdown não consolidadas."
    )

    insight = f"{str_sharpe} {str_resil} As distribuições de retornos diários revelam assimetrias e dispersões de cauda que devem ser ponderadas no dimensionamento das posições."

    # Ação (Tendência SMA)
    posicao_sma = ""
    if df_sma is not None and not df_sma.empty and ticker_sma:
        last_row = df_sma.iloc[-1]
        c_val = last_row.get("close")
        s21 = last_row.get("sma_21")
        s50 = last_row.get("sma_50")

        if pd.notna(c_val) and pd.notna(s21) and pd.notna(s50):
            if c_val > s21 and c_val > s50:
                posicao_sma = f"Para {ticker_sma}, o último preço de fechamento situou-se acima de ambas as médias móveis (SMA 21 e SMA 50), alinhado com a tendência de curto/médio prazo."
            elif c_val < s21 and c_val < s50:
                posicao_sma = f"Para {ticker_sma}, o preço de fechamento encerrou abaixo das médias móveis de 21 e 50 períodos, sinalizando patamares inferiores em relação ao histórico recente."
            else:
                posicao_sma = f"Para {ticker_sma}, o preço opera entre as médias de 21 e 50 períodos."

    acao = (
        f"Recomenda-se monitorar a sustentação das métricas de risco ajustado ao retorno (Sharpe) e os limites de tolerância a perdas (drawdown). "
        f"{posicao_sma} Avaliações contínuas da liquidez e da volatilidade histórica auxiliam na recalibragem defensiva da carteira."
    )

    return {
        "contexto": contexto,
        "insight": insight,
        "acao": acao,
    }