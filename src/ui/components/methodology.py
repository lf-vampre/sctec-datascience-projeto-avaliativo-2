import streamlit as st

def render_aba_dados_metodologia_macro():
    """
    Renders the 'Dados & Metodologia' tab for Dashboard 1 — Inteligência Macroeconômica.
    """
    
    # Seção 1: Guia dos Filtros Locais
    with st.expander("🎛️ Guia de Uso dos Filtros Locais e Escopo de Atuação", expanded=False):
        st.markdown("""
        ### Funcionamento dos Filtros Locais (Dashboard 1)
        
        Os filtros disponíveis no painel retrátil no topo deste dashboard atuam exclusivamente sobre os componentes visuais da visão **Inteligência Macroeconômica**. Não há impacto cruzado nos demais dashboards (CVM, B3 ou Integrado).
        
        * **Defasagem Câmbio x Inflação (meses):**
          * **Escopo:** Afeta unicamente o gráfico de *Dispersão: PTAX x IPCA 12M* (Aba Câmbio PTAX).
          * **Uso:** Desloca a série temporal do IPCA 12M em $N$ meses no tempo para analisar o efeito de *pass-through* cambial (o tempo de resposta da inflação frente às variações do Dólar PTAX).
        * **Modo da Correlação:**
          * **Escopo:** Afeta a *Matriz de Correlação de Pearson* (Aba Correlações).
          * **Opções:** 
            * **Níveis:** Calcula a correlação estatística direta entre os valores absolutos observados das séries.
            * **Variações:** Aplica a primeira diferença mensal ($\Delta = x_t - x_{t-1}$) para eliminar tendências de não-estacionariedade e avaliar a correlação entre as oscilações de curto prazo.
        * **Indicadores no Heatmap:**
          * **Escopo:** Afeta a *Matriz de Correlação de Pearson* (Aba Correlações).
          * **Uso:** Multiseletor que permite filtrar dinamicamente quais variáveis macroeconômicas serão incluídas no mapa de calor.
        """)

    # Seção 2: Interpretação das Abas e Gráficos
    with st.expander("📊 Guia de Interpretação dos Gráficos e Estrutura das Abas", expanded=False):
        st.markdown("""
        ### 1. Visão Geral
        * **KPIs Globais:** Exibem o valor mais recente do período (Selic Meta, IPCA 12M, Juro Real Ex-Post e Dólar PTAX) acompanhado da variação (*delta*) em relação a 12 meses anteriores (em p.p. ou variação percentual).
        * **Gráfico Política Monetária:** Combina a curva da **Selic Meta** (% a.a.) e **IPCA 12M** (% a.a.) em linhas com o **Juro Real Ex-Post** em barras. Permite identificar visualmente o grau de aperto ou afrouxamento monetário do Banco Central.

        ### 2. Câmbio (PTAX)
        * **Evolução do Dólar PTAX:** Gráfico de linha temporal da taxa PTAX Venda diária/mensal. A linha tracejada indica a média histórica do período (R$ 4,93) e as áreas sombreadas destacam os ciclos em que a moeda norte-americana operou acima da média.
        * **Dispersão PTAX x IPCA 12M:** Diagrama de dispersão onde cada ponto representa um mês. O eixo X indica o PTAX, o eixo Y a taxa de IPCA 12M, a cor codifica o ano (2019 a 2023) e o tamanho da bolha é proporcional ao patamar da Selic.

        ### 3. Atividade Econômica
        * **IBC-Br vs. Selic Meta e Ciclos Monetários:** Gráfico de dois eixos conectando o índice de atividade econômica do BACEN (IBC-Br com ajuste sazonal, eixo esquerdo) com a Selic Meta (eixo direito). As faixas verticais sombreadas categorizam a postura do COPOM em 3 fases:
          * **Ciclo de Aperto (Rosa):** Período de elevação contínua da taxa básica de juros.
          * **Ciclo de Corte (Verde):** Período de redução da Selic.
          * **Manutenção (Cinza):** Período de estabilidade da taxa.

        ### 4. Correlações
        * **Matriz de Pearson:** Mapa de calor apresentando o coeficiente de correlação linear $r \in [-1, 1]$ entre os pares de variáveis selecionadas.
        * **Matriz de Defasagem (PTAX x IPCA 12M):** Tabela paramétrica que exibe a variação da correlação de Pearson conforme se aplica um deslocamento temporal de 0 a 9+ meses na inflação.
        """)

    # Seção 3: Metodologia e Fórmulas de Cálculo
    with st.expander("🧮 Metodologia de Cálculo e Fontes de Dados", expanded=False):
        st.markdown("### Juro Real Ex-Post (Equação de Fisher Exata)")
        st.markdown(
            "Em conformidade com a diretriz metodológica o Juro Real Ex-Post é "
            "calculado utilizando a **Equação de Fisher Exata**, garantindo o rigor estatístico "
            "e eliminando distorções presentes na simples subtração linear ($i - \\pi$), "
            "especialmente em cenários de juros ou inflação elevados."
        )
        
        st.latex(r"r_{\text{real}} = \frac{1 + i}{1 + \pi} - 1")
        
        st.markdown("""
        **Onde:**
        * $r_{\text{real}}$ = Taxa de Juro Real Ex-Post acumulada (% a.a.).
        * $i$ = Taxa Selic Meta anualizada no final do período em fração (SGS 432 / 100).
        * $\pi$ = Inflação oficial (IPCA acumulado em 12 meses) em fração (SGS 13522 / 100).
        """)

        st.markdown("> **Exemplo comparativo (Selic = 14,75% e IPCA 12M = 4,40%):**")
        st.markdown("> * **Fisher Exato:**")
        st.latex(r"\frac{1 + 0{,}1475}{1 + 0{,}0440} - 1 = 9{,}91\% \text{ a.a.}")
        st.markdown(
            "> * **Diferença Simples ($i - \pi$):** $14{,}75\% - 4{,}40\% = \\mathbf{10{,}35\\%\\text{ a.a.}}$ (Superestima o juro real em 44 bps)."
        )
        
        st.markdown("---")
        
        st.markdown("### Fontes Primárias dos Dados (BACEN SGS)")
        st.markdown("""
        Todas as variáveis deste dashboard são extraídas via API oficial do Sistema Gerenciador de Séries Temporais (SGS) do Banco Central do Brasil:
        
        | Código SGS | Indicador | Frequência | Tipo de Agregação Mensal |
        |---|---|---|---|
        | **432** | Taxa Selic Meta | Diária | Valor do último dia útil do mês |
        | **1178** | Taxa Selic Efetiva (Over) | Diária | Valor acumulado / último dia |
        | **433** | IPCA Mensal | Mensal | Valor nativo da série |
        | **13522** | IPCA Acumulado 12 Meses | Mensal | Valor nativo da série |
        | **1** | Taxa de Câmbio - PTAX Venda | Diária | Média aritmética das cotações diárias |
        | **24364** | IBC-Br (com ajuste sazonal) | Mensal | Valor nativo da série |
        | **196** | Rendimento da Caderneta de Poupança | Mensal | Valor nativo da série |
        """)
        
        st.caption(
            "Nota sobre não-causalidade: As análises de correlação de Pearson e dispersão estatística "
            "indicam associação matemática entre variáveis econômicas, não estabelecendo relação de causalidade direta ou determinística."
        )

def render_aba_dados_metodologia_cvm():
    """
    Renders the 'Dados & Metodologia' tab for Dashboard 2 — Análise Fundamentalista & Contábil.
    """
    # Seção 1: Guia dos Filtros Locais
    with st.expander("🎛️ Guia de Uso dos Filtros Locais e Escopo de Atuação", expanded=False):
        st.markdown("""
        ### Funcionamento dos Filtros Locais (Dashboard 2)
        
        Os filtros no topo desta página refinam as análises contábeis dentro do recorte temporal e corporativo definido pelo **Filtro Global da Sidebar**.
        
        * **Exercício Foco (KPIs & Dispersão):**
          * **Escopo:** Seleciona o ano de referência ancorado para os 4 KPIs consolidados do topo, o gráfico de *Distribuição Setorial da Receita Líquida* (Aba Visão Geral), a *Matriz Margem Líquida vs. ROE* (Aba Rentabilidade) e a análise de *Solvência e Liquidez* (Aba Solvência).
          * **Uso:** Permite isolar um exercício contábil específico para comparações transversais entre empresas. As séries temporais de linha (como a *Evolução Temporal da Margem Líquida*) permanecem exibindo o período temporal completo definido na Sidebar.
        * **Agrupamento EBIT:**
          * **Escopo:** Afeta a distribuição dos boxplots de Margem EBIT na aba *Rentabilidade*.
          * **Opções:** 
            * **Setor Analítico:** Agrupa as companhias pelas categorias setoriais padronizadas do projeto (Consumo & Varejo/Serviços, Energia, Indústria & Bens de Capital, Materiais Básicos).
            * **Commodities vs Serviços:** Reorganiza a visualização comparando empresas produtoras/exportadoras de commodities primárias contra empresas voltadas a serviços e mercado interno.
        * **Limiar de Liquidez Corrente (x):**
          * **Escopo:** Afeta o gráfico combinatório de solvência e a tabela de atenção na aba *Solvência*.
          * **Uso:** Ajusta dinamicamente a linha tracejada horizontal de corte (ex: 1,50x) para sinalizar visualmente e filtrar companhias industriais que operam abaixo do patamar de liquidez desejado.
        """)

    # Seção 2: Interpretação das Abas e Gráficos
    with st.expander("📊 Guia de Interpretação dos Gráficos e Estrutura das Abas", expanded=False):
        st.markdown("""
        ### 1. Visão Geral
        * **KPIs Globais:** Exibem a Receita Líquida Total (exclusivo companhias industriais/comerciais), Lucro Líquido Consolidado, ROE Médio da Carteira e Liquidez Corrente Média para o exercício foco, acompanhados da variação percentual ou em p.p. em relação ao ano anterior.
        * **Receita Líquida vs. Intermediação Financeira:** Apresenta barras anuais agrupadas por empresa. A *Receita de Intermediação Financeira* (bancos) é segregada da *Receita Líquida* (indústrias), impedindo distorções na agregação de receitas de naturezas contábeis distintas.
        * **Distribuição Setorial da Receita Líquida:** Gráfico de rosca demonstrando a representatividade percentual de cada setor sobre o faturamento total consolidado das empresas industriais.

        ### 2. Rentabilidade
        * **Matriz Margem Líquida vs. ROE:** Diagrama de dispersão posicionando cada empresa em quatro quadrantes analíticos no exercício foco:
          * **Líder:** Margem Alta e ROE Alto.
          * **Giro:** Margem Baixa e ROE Alto (alta eficiência no uso do capital).
          * **Nicho:** Margem Alta e ROE Baixo.
          * **Desafio:** Margem Baixa e ROE Baixo.
        * **Evolução Temporal da Margem Líquida:** Gráfico de linhas rastreando a trajetória de eficiência operacional percentual das empresas ao longo do tempo.
        * **Distribuição da Margem EBIT por Grupo:** Painel de boxplots com eixos Y independentes por agrupamento, exibindo mediana, quartis e *outliers* de rentabilidade operacional.

        ### 3. Solvência
        * **Níveis de Solvência e Liquidez Corrente:** Visualização combinada que confronta o volume de **Dívida Líquida** em R$ (barras) contra a **Liquidez Corrente** (linha com marcador) no exercício foco, com suporte à linha de parâmetro ajustável.
        * **Empresas com Pontos de Atenção na Liquidez:** Tabela que lista automaticamente empresas que possuem índice de Liquidez Corrente abaixo do limiar configurado e/ou Dívida Líquida positiva.
        """)

    # Seção 3: Metodologia de Cálculo e Regras Contábeis
    with st.expander("🧮 Metodologia de Cálculo, Regras Contábeis (CVM DFP)", expanded=False):
        st.markdown("### Definição Matemática dos Indicadores Fundamentalistas")
        
        st.markdown("""
        As demonstrações financeiras anuais padronizadas (DFP/CVM) são consolidadas em moeda corrente original (com ajuste de escala $\\times 1.000$ quando informado em milhares de Reais).

        * **Margem Líquida (%):**
        """)
        st.latex(r"\text{Margem Líquida} = \frac{\text{Lucro Líquido (DRE 3.11)}}{\text{Receita Líquida (DRE 3.01)}} \times 100")
        
        st.markdown("* **Margem EBIT (%):**")
        st.latex(r"\text{Margem EBIT} = \frac{\text{EBIT / Resultado Operacional (DRE 3.05)}}{\text{Receita Líquida (DRE 3.01)}} \times 100")

        st.markdown("* **Return on Equity — ROE (%):** (Ancorado no Patrimônio Líquido do fim do exercício)")
        st.latex(r"\text{ROE} = \frac{\text{Lucro Líquido (DRE 3.11)}}{\text{Patrimônio Líquido (BPP 2.03)}} \times 100")
        
        st.markdown("* **Liquidez Corrente (x):**")
        st.latex(r"\text{Liquidez Corrente} = \frac{\text{Ativo Circulante (BPA 1.01)}}{\text{Passivo Circulante (BPP 2.01)}}")

        st.markdown("* **Dívida Líquida (R$):** ")
        st.latex(r"\text{Dívida Líquida} = (\text{Empréstimos/Debêntures CP + LP}) - (\text{Caixa e Equivalentes} + \text{Aplicações Financeiras})")

        st.markdown("---")

        st.markdown("### Regras Especiais e Tratamento de Instituições Financeiras (COSIF)")
        st.markdown("""
        * **Segregação do Setor Financeiro (Plano COSIF):** Instituições bancárias operam sob estrutura demonstrativa distinta. Desta forma:
          * **Métricas Nulas/Inaplicáveis:** Margem EBIT, Liquidez Corrente e Dívida Líquida **não se aplicam a bancos** e são tratadas como `N/A` ou nulas para evitar distorções metodológicas.
          * **Receita de Intermediação Financeira:** Apresentada de forma isolada na aba Visão Geral e excluída da soma de Receita Líquida dos KPIs e do gráfico de Donut.
          * **Métricas Preservadas:** O **Lucro Líquido** e o **ROE** das instituições financeiras são plenamente comparáveis e integrados às métricas consolidadas da carteira.
        * **Tratamento de Patrimônio Líquido Negativo ($PL \le 0$):** Casos em que o Patrimônio Líquido é nulo ou negativo têm o cálculo do ROE automaticamente desconsiderado para evitar distorções causadas por inversão de sinal matemático.
        """)

def render_aba_dados_metodologia_b3():
    """
    Renders the 'Dados & Metodologia' tab for Dashboard 3 — Mercado e Risco (B3).
    """
    # Seção 1: Guia dos Filtros Locais
    with st.expander("🎛️ Guia de Uso dos Filtros Locais e Escopo de Atuação", expanded=False):
        st.markdown("""
        ### Funcionamento dos Filtros Locais (Dashboard 3)
        
        Os filtros no topo desta página aplicam refinamentos específicos em visualizações das abas de Mercado e Risco, operando dentro da seleção de empresas e janela temporal estabelecidas no **Filtro Global da Sidebar**.
        
        * **Destaque na Base 100:**
          * **Escopo:** Afeta o gráfico *Rentabilidade Comparativa Normalizada* (Aba Rentabilidade).
          * **Uso:** Destaca com traço espesso e cor diferenciada a curva temporal de um ativo específico ou da *Carteira Equiponderada*, suavizando as demais para facilitar a comparação visual.
        * **Distribuição dos retornos (Histograma) / Ativo:**
          * **Escopo:** Afeta os 5 KPIs de momentos estatísticos e o gráfico de *Distribuição dos Retornos Diários* (Aba Distribuição dos retornos).
          * **Uso:** Alterna a análise entre a carteira consolidada ou a série de retornos de uma empresa individual.
        * **Ativos no Drawdown:**
          * **Escopo:** Afeta exclusivamente o gráfico temporal *Evolução do Drawdown no Tempo* (Aba Drawdown).
          * **Uso:** Multiseletor que permite isolar e comparar as trajetórias de perda a partir do pico histórico das empresas selecionadas. A tabela *Ranking de Resiliência* permanece exibindo a totalidade dos ativos filtrados.
        * **Ativo para Análise de Tendência (SMA):**
          * **Escopo:** Afeta o gráfico *Preço vs. Médias Móveis* (Aba Tendência).
          * **Uso:** Seleciona o ativo para exibição de suas cotações de fechamento diárias acompanhadas das médias móveis simples de 21 e 50 períodos.
        """)

    # Seção 2: Interpretação das Abas e Gráficos
    with st.expander("📊 Guia de Interpretação dos Gráficos e Estrutura das Abas", expanded=False):
        st.markdown("""
        ### 1. Rentabilidade
        * **KPIs Consolidados:** Exibem a rentabilidade acumulada média da carteira equiponderada, o ativo com maior desempenho (*Destaque*), o ativo com menor variação (*Menor Perf.*) e a volatilidade anualizada média no período.
        * **Rentabilidade Comparativa Normalizada (Base 100):** Indexa todos os ativos no valor inicial de $100$ na primeira data útil da janela temporal, permitindo comparar o crescimento relativo percentual de ações com faixas de preço absoluto distintas.

        ### 2. Risco e Retorno
        * **Relação Risco vs. Retorno (Dispersão):** Confronta a Volatilidade Anualizada (%) no eixo X contra o Retorno Acumulado (%) no eixo Y. O tamanho de cada bolha reflete o Volume Financeiro Médio Diário (R$) e a posição indica o perfil de eficiência da ação.
        * **Tabela de Risco e Retorno Ajustado:** Consolida as métricas numéricas de rentabilidade, volatilidade, Índice de Sharpe, Drawdown Máximo, Assimetria (*Skewness*), Curtose (*Kurtosis*), VaR 95% e Volume Diário.

        ### 3. Distribuição dos Retornos
        * **KPIs Estatísticos:** Exibem a Assimetria (viés de cauda), Curtose (espesura de cauda/risco de evento extremo), VaR 95% (Percentil 5%), Retorno Mínimo Diário e Retorno Máximo Diário.
        * **Histograma com Boxplot Marginal:** Ilustra a frequência dos retornos percentuais diários com uma visualização de caixa no topo para identificação de mediana, intervalo interquartil (IQR) e *outliers*.

        ### 4. Drawdown
        * **Evolução do Drawdown no Tempo:** Gráfico percentual contínuo que mede a queda percentual do preço de um ativo em relação à sua máxima histórica anterior (*Peak-to-Trough*).
        * **Ranking de Resiliência:** Tabela ordenada pelo menor Drawdown Máximo (em módulo), identificando os papéis mais defensivos contra quedas acentuadas de mercado.

        ### 5. Tendência
        * **Preço vs. Médias Móveis (SMA 21 / SMA 50):** Exibe a série temporal de preço de fechamento sobreposta pela Média Móvel Simples de 21 dias (curto prazo) e 50 dias (médio prazo) para identificação de tendências e pontos de cruzamento (*Golden/Death Cross*).
        """)

    # Seção 3: Metodologia de Cálculo e Métricas Financeiras
    with st.expander("🧮 Metodologia de Cálculo, Métricas Financeiras e Fontes (B3 / yfinance)", expanded=False):
        st.markdown("### Retorno Acumulado e Volatilidade Anualizada")
        st.markdown("* **Retorno Acumulado (%):** Calculado com base na variação discreta do preço de fechamento ajustado ($P$) entre o início ($t_0$) e o fim ($t_N$) da janela filtrada.")
        st.latex(r"R_{\text{acum}} = \left( \frac{P_{t_N}}{P_{t_0}} - 1 \right) \times 100")

        st.markdown("* **Volatilidade Anualizada (% a.a.):** Desvio padrão ($\sigma_d$) dos retornos diários logarítmicos ou percentuais, escalado para o ano útil de 252 pregões.")
        st.latex(r"\sigma_{\text{anual}} = \sigma_{d} \times \sqrt{252}")

        st.markdown("---")

        st.markdown("### Índice de Sharpe Empírico")
        st.markdown(
            "Em conformidade com a diretriz metodológica a taxa livre de risco nominal utilizada "
            "é a **Selic Efetiva diária (SGS 1178)**, atuando como proxy do CDI. O cálculo mensura a razão "
            "entre o excesso de retorno diário sobre o benchmark e a volatilidade total do ativo."
        )

        st.latex(r"\text{Sharpe} = \frac{\bar{R}_{i,d} - \bar{R}_{f,d}}{\sigma_{i,d}} \times \sqrt{252}")

        st.markdown("**Onde:**")
        st.markdown("* $\\bar{R}_{i,d}$ = Retorno diário médio do ativo $i$.")
        st.markdown("* $\\bar{R}_{f,d}$ = Taxa diária equivalente da Selic Efetiva:")
        st.latex(r"R_{f,d} = (1 + \text{Selic Efetiva})^{1/252} - 1")
        st.markdown("* $\\sigma_{i,d}$ = Desvio padrão dos retornos diários do ativo $i$.")

        st.markdown("---")

        st.markdown("### Drawdown e Risco de Cauda (VaR 95%)")
        st.markdown("* **Drawdown em um momento $t$ (%):**")
        st.latex(r"DD_t = \frac{P_t - \max_{0 \le s \le t}(P_s)}{\max_{0 \le s \le t}(P_s)}")

        st.markdown("* **Value at Risk — VaR 95% Diário (Histórico):** Representa a perda máxima esperada para um dia ao nível de confiança de 95%, calculado como o 5º percentil ($P_5$) da distribuição dos retornos diários.")

        st.markdown("---")

        st.markdown("### Fontes Primárias e Limitações de Mercado")
        st.markdown(
            "* **Dados de Cotação:** Coletados via biblioteca `yfinance` para o mercado B3 (`.SA`), utilizando preços de fechamento ajustados por proventos (dividendos e desdobramentos)."
        )
        st.markdown(
            "* **Estimativa de Volume Financeiro:** Como a API fornece o volume de ações negociadas ($Qty$), o volume financeiro diário em Reais é aproximado por:"
        )
        st.latex(r"\text{Volume}_{\text{fin}} \approx \text{Close} \times Qty")
        st.markdown(
            "* **Aviso Legal de Rendimento:** Rentabilidade passada não representa garantia de rentabilidade futura."
        )

def render_aba_dados_metodologia_integrado():
    """
    Renders the 'Dados & Metodologia' tab for Dashboard 4 — Visão Integrada da Tríade.
    """
    # Seção 1: Guia dos Filtros Locais
    with st.expander("🎛️ Guia de Uso dos Filtros Locais e Escopo de Atuação", expanded=False):
        st.markdown("""
        ### Funcionamento dos Filtros Locais (Dashboard 4)
        
        Os filtros no topo desta página orquestram as análises integradas cruzando dados do BACEN, CVM e B3, atuando dentro do recorte global estabelecido na Sidebar.
        
        * **Exercício Foco (KPIs & Contábil):**
          * **Escopo:** Afeta exclusivamente os KPIs contábeis de topo (**Receita Consolidada** e **Lucro Consolidado**) e os dois gráficos da aba *Contabilidade e Mercado*.
          * **Nota:** Os KPIs macroeconômicos (**Selic Meta Vigente** e **IPCA 12M Acumulado**) permanecem exibindo a leitura do ponto mais recente do período selecionado.
        * **Modo Dispersão EBIT vs Retorno:**
          * **Escopo:** Alterna a forma de cálculo e exibição nos gráficos da aba *Contabilidade e Mercado*.
          * **Opções:** 
            * **Ano de Foco:** Analisa a rentabilidade operacional (Margem EBIT) e o desempenho em bolsa restritos ao exercício ancorado.
            * **Período Completo:** Plota a margem média histórica da empresa contra o retorno acumulado em toda a janela temporal filtrada.
        * **Janela Estresse Cambial (Dias) & Limiar Alta PTAX (%):**
          * **Escopo:** Alteram unicamente o gráfico *Comportamento de Exportadoras em Períodos de Estresse Cambial* (Aba Câmbio e Exportadoras).
          * **Uso:** Parametrizam o algoritmo de identificação de choques cambiais, estabelecendo a janela mista de observação em dias úteis e o desvio percentual mínimo do Dólar PTAX para categorizar um período como "Estresse Cambial".
        * **Pesos do Ranking Setorial (Bolsa, Resiliência Macro, Solidez Contábil):**
          * **Escopo:** Alteram dinamicamente a ponderação dos pilares no gráfico *Ranking Setorial Multidimensional* (Aba Ranking Setorial).
          * **Uso:** Permitem ao analista customizar o peso relativo ($0,00$ a $3,00$) atribuído à performance acionária, à resiliência frente aos ciclos monetários e aos indicadores de solvência contábil, recalculando instantaneamente o Score Final Consolidado e a ordenação dos setores.
        """)

    # Seção 2: Interpretação das Abas e Gráficos
    with st.expander("📊 Guia de Interpretação dos Gráficos e Estrutura das Abas", expanded=False):
        st.markdown("""
        ### 1. Visão Integrada
        * **KPIs da Tríade:** Consolidação executiva combinando a política monetária recente do BACEN com o faturamento e lucro corporativo das empresas listadas na B3.
        * **Trajetória Conjunta Macro-Cambial:** Gráfico multieixo temporal correlacionando a Selic Meta (% a.a.), IPCA 12M (% a.a.) e o Dólar PTAX Venda (R$), permitindo acompanhar regimes de aperto monetário e desvalorização cambial.
        * **Rentabilidade Comparativa Normalizada (Base 100):** Evolução contínua da carteira de ativos cotados na B3 indexada no ponto inicial.

        ### 2. Contabilidade e Mercado
        * **Lucro Líquido e ROE por Companhia:** Gráfico de barras duplas apresentando o resultado nominal (R$ Milhões) e a taxa de retorno sobre o patrimônio (% ROE) de cada empresa no exercício foco.
        * **Eficiência Operacional (EBIT %) vs. Desempenho em Bolsa:** Dispersão relacionando a margem operacional das companhias com a rentabilidade de suas ações na bolsa.

        ### 3. Juros e Setores
        * **Retorno Setorial em Bolsa vs. Taxa Selic Média Anual:** Confronta o desempenho das ações agrupadas por setor econômico com a taxa básica de juros média praticada pelo COPOM em cada ano.
        * **Evolução Contábil durante o Ciclo da Selic:** Gráfico combinado correlacionando o índice de Despesa Financeira, Lucro Líquido, Alavancagem Média (Dívida Líquida / PL) e a Selic Média Anual.

        ### 4. Câmbio e Exportadoras
        * **Comportamento de Exportadoras em Estresse Cambial:** Compara o retorno diário médio das empresas exportadoras de commodities versus demais setores em dias classificados como dentro ou fora da janela de choque cambial.
        * **Margem EBIT Anual vs. PTAX Média:** Avalia a evolução temporal da rentabilidade operacional dos setores produtores de commodities frente às oscilações da taxa média do Dólar.

        ### 5. Ranking Setorial
        * **Ranking Setorial Multidimensional:** Painel de barras horizontais empilhadas/ponderadas que classifica a saúde e atratividade dos setores industriais e financeiros através de 3 pilares parametrizáveis:
          * **Pilar Retorno em Bolsa:** Performance de valorização acionária.
          * **Pilar Resiliência Macro:** Capacidade de manutenção de margem em ciclos adversos de juros e inflação.
          * **Pilar Solidez Contábil:** Níveis de liquidez corrente e estrutura de endividamento.
        """)

    # Seção 3: Metodologia Integrada e Regras da Tríade
    with st.expander("🧮 Metodologia Integrada e Algoritmos de Ponderação", expanded=False):
        st.markdown("### Algoritmo do Score Setorial Multidimensional")
        st.markdown(
            "O ranking setorial aplica a normalização Min-Max ($[0, 100]$) sobre as métricas dos três pilares, "
            "calculando a pontuação final agregada ($S_{\text{final}}$) por meio de uma média ponderada pelos pesos locais configurados:"
        )

        st.latex(r"S_{\text{final}} = \frac{w_B \cdot P_{\text{Bolsa}} + w_M \cdot P_{\text{Macro}} + w_C \cdot P_{\text{Contábil}}}{w_B + w_M + w_C}")

        st.markdown("""
        **Onde:**
        * $P_{\text{Bolsa}}, P_{\text{Macro}}, P_{\text{Contábil}}$ = Pontuações normalizadas de cada setor nos pilares correspondentes ($0$ a $100$).
        * $w_B, w_M, w_C$ = Pesos atribuídos aos pilares através dos filtros locais.
        
        > **Nota de Solidez Parcial:** Setores contendo instituições financeiras recebem a sinalização de *Solidez Parcial*, uma vez que indicadores operacionais industriais (EBIT, Liquidez Corrente e Dívida Líquida) não se aplicam ao plano COSIF.
        """)

        st.markdown("---")

        st.markdown("### Métricas de Estresse Cambial e Regras de Negócio")
        st.markdown("""
        * **Identificação de Estresse Cambial:** Um período é categorizado sob estresse quando a variação percentual móvel do Dólar PTAX em uma janela de $N$ dias ultrapassa o limiar $L\%$ definido pelo usuário:
        """)
        st.latex(r"\Delta \text{PTAX}_{t, N} = \frac{\text{PTAX}_t - \text{PTAX}_{t-N}}{\text{PTAX}_{t-N}} \ge \frac{L}{100}")

        st.markdown("---")

        st.markdown("### Consolidação das Decisões Metodológicas da Tríade")
        st.markdown(
            "* **Juro Real Ex-Post:** Calculado rigorosamente pela Equação de Fisher:"
        )
        st.latex(r"r_{\text{real}} = \frac{1 + i}{1 + \pi} - 1")
        st.markdown(
            "* **Taxa Livre de Risco:** Utiliza a Selic Efetiva diária (SGS 1178) como benchmark para métricas de excesso de retorno e Sharpe."
        )
        st.markdown(
            "* **Premissas Contábeis:** Dívida Líquida definida como $(\\text{Empréstimos CP + LP}) - (\\text{Caixa} + \\text{Aplicações})$; ROE calculado sobre o Patrimônio Líquido de fim de exercício."
        )
        st.markdown(
            "* **Segregação Financeira:** Receita de Intermediação Financeira mantida de forma isolada e rotulada como \"não comparável\" com a Receita Líquida Industrial."
        )

        st.caption(
            "Aviso de Não-Causalidade e Isenção: As análises estatísticas integradas entre BACEN, B3 e CVM "
            "apresentam associações históricas entre variáveis econômicas e contábeis, sem estabelecer relação "
            "de causalidade direta e sem constituir recomendação de investimento."
        )