"""Geração dinâmica de storytelling analítico (Contexto, Insight, Ação) para o Dashboard CVM (D2)."""

from typing import Any, Dict
import pandas as pd

from src.utils.formatting import format_currency, format_percent


def gerar_story_cvm(
    kpis: Dict[str, Any],
    crescimento: Dict[str, Any],
    dispersao: Dict[str, Any],
    solvencia_df: pd.DataFrame,
    dist_setorial: Dict[str, Any],
    limiar_liquidez: float = 1.5,
) -> Dict[str, str]:
    """Gera textos analíticos sem inferência de causalidade com base nos dados do exercício foco."""
    ano_foco = kpis.get("ano_foco", 2023)
    ano_ant = kpis.get("ano_anterior", 2022)

    # 1. CONTEXTO
    rec_tot = kpis.get("receita_liquida_total")
    rec_delta_pct = kpis.get("receita_delta_pct")
    lucro_tot = kpis.get("lucro_liquido_total")
    lucro_delta_pct = kpis.get("lucro_delta_pct")

    str_rec = format_currency(rec_tot, compact=True).replace("$", "\\$") if rec_tot is not None else "N/A"
    str_rec_pct = (
        f"{rec_delta_pct:+.2f}%".replace(".", ",")
        if rec_delta_pct is not None
        else "N/A"
    )

    str_lucro = format_currency(lucro_tot, compact=True).replace("$", "\\$") if lucro_tot is not None else "N/A"
    str_lucro_pct = (
        f"{lucro_delta_pct:+.2f}%".replace(".", ",")
        if lucro_delta_pct is not None
        else "N/A"
    )

    contexto = (
        f"No exercício de {ano_foco}, o universo de empresas industriais analisado registrou uma Receita Líquida "
        f"Consolidada de {str_rec} ({str_rec_pct} em relação a {ano_ant}, em base comparável). "
        f"O Lucro Líquido total (incluindo instituições financeiras) atingiu {str_lucro} ({str_lucro_pct} vs. {ano_ant}). "
        f"As métricas operacionais e de endividamento consideram exclusivamente as companhias industriais/comerciais, "
        f"conforme regras de padronização contábil (ADR-09)."
    )

    # 2. INSIGHT
    df_emp = crescimento.get("empresas", pd.DataFrame())
    setores_cresc = crescimento.get("setores", pd.DataFrame())
    contracoes = crescimento.get("contracoes", [])

    dstaq_cresc = "N/A"
    dstaq_queda = "N/A"
    if not df_emp.empty and "var_pct" in df_emp.columns:
        top_emp = df_emp.iloc[0]
        bot_emp = df_emp.iloc[-1]
        dstaq_cresc = f"{top_emp['ticker']} ({top_emp['var_pct']:+.2f}%)".replace(".", ",")
        dstaq_queda = f"{bot_emp['ticker']} ({bot_emp['var_pct']:+.2f}%)".replace(".", ",")

    setor_lider = "N/A"
    if not setores_cresc.empty and "var_pct" in setores_cresc.columns:
        top_setor = setores_cresc.iloc[0]
        setor_lider = f"{top_setor['setor_analitico']} ({top_setor['var_pct']:+.2f}%)".replace(".", ",")

    str_contracao = (
        f"Houve retração de receita em {len(contracoes)} empresa(s): {', '.join(contracoes)}."
        if contracoes
        else "Nenhuma empresa registrou retração nominal de receita no período."
    )

    med_roe = kpis.get("roe_medio")
    if med_roe is not None:
        roe_val = med_roe * 100.0 if abs(med_roe) <= 1.0 else med_roe
        str_roe = format_percent(roe_val)
    else:
        str_roe = "N/A"

    empresas_atencao = []
    if not solvencia_df.empty and "atencao_liquidez" in solvencia_df.columns:
        sub_at = solvencia_df[solvencia_df["atencao_liquidez"] & ~solvencia_df["caixa_liquido"]]
        empresas_atencao = sub_at["ticker"].tolist()

    limiar_str = f"{limiar_liquidez:.1f}".replace(".", ",")
    str_solv = (
        f"Empresas com Liquidez Corrente < {limiar_str}x e Dívida Líquida positiva: {', '.join(empresas_atencao)}."
        if empresas_atencao
        else f"Todas as empresas com Dívida Líquida positiva apresentam Liquidez Corrente acima de {limiar_str}x."
    )

    insight = (
        f"Destaques de variação de Receita ({ano_ant}-{ano_foco}): maior crescimento em {dstaq_cresc}; "
        f"menor desempenho em {dstaq_queda}. Por setor, o segmento de maior expansão foi {setor_lider}. {str_contracao} "
        f"O ROE médio da carteira situou-se em {str_roe}. Na análise de estrutura de capital, observa-se: {str_solv}"
    )

    # 3. AÇÃO
    acao = (
        f"Recomenda-se acompanhar a evolução temporal da margem de rentabilidade e os níveis de alavancagem financeira "
        f"das empresas sinalizadas nos pontos de atenção. Para companhias industriais com liquidez reduzida, cabe avaliar "
        f"o perfil de vencimento das dívidas no curto prazo em exercícios subsequentes."
    )

    return {
        "contexto": contexto,
        "insight": insight,
        "acao": acao,
    }