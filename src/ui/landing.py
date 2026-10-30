import html
import streamlit as st
from src.ui.state import ir_para


def render() -> None:
    """Renderiza a Landing Page do projeto com seleção de modo sob demanda."""
    
    # Header / Hero
    st.markdown(
        """
        <div class="fx-hero" style="margin-top:-30px;">
            <div class="fx-hero-title" >Plataforma Financeira Integrada</div>
            <p class="fx-hero-subtitle">Análise Unificada de Dados da Tríade: BACEN &bull; B3 &bull; CVM</p>
            <div style="margin-top: 12px; display: flex; gap: 8px;">
                <span class="fx-badge fx-badge-info">BACEN (SGS)</span>
                <span class="fx-badge fx-badge-success">B3 (Cotações)</span>
                <span class="fx-badge fx-badge-warning">CVM (DFPs)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Selecione o Modo de Operação")
    st.write("Escolha uma das visões abaixo para iniciar a navegação no sistema:")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="fx-card">
                <div class="fx-header" style="font-size: 1.125rem;">📊 Data App BI Executivo</div>
                <p style="color: var(--fx-color-text-secondary); font-size: 0.875rem;">
                    4 dashboards analíticos interativos cobrindo Macroeconomia, Fundamentalista, 
                    Mercado e Visão Integrada das 3 fontes. Dados em Star Schema (Camada Ouro) consumidos
                    via conexão PostgreSQL, com fallback em arquivos .parquet.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Acessar BI Executivo", key="btn_modo_bi", type="primary", use_container_width=True):
            ir_para("bi")
            st.rerun()

    with col2:
        st.markdown(
            """
            <div class="fx-card">
                <div class="fx-header" style="font-size: 1.125rem;">⚙️ DataOps Control Tower</div>
                <p style="color: var(--fx-color-text-secondary); font-size: 0.875rem;">
                    Orquestração do pipeline de dados em camadas (Bronze &rarr; Prata &rarr; Ouro).
                    Limpeza, tratamento e verificação dos dados (ETL / EAD)
                    Acompanhamento de logs, execução step-by-step, gestão de memória e painel de saúde da base.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Acessar DataOps", key="btn_modo_dataops", type="primary", use_container_width=True):
            ir_para("dataops")
            st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: var(--fx-color-text-muted); font-size: 0.875rem; margin-top:-30px;">
            Desenvolvido por Felipe Vampré para o Projeto Avaliativo  &bull; SCTEC / SENAI
        </div>
        """,
        unsafe_allow_html=True,
    )