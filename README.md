![Logos](./images/logos.png)

<br>
<br>

# Plataforma Financeira Integrada (Tríade BACEN + B3 + CVM)

<br>

![app](./images/app_landing.png)

<br>

## 1. Título e Resumo Executivo

A **Plataforma Financeira Integrada** é uma solução Fullstack de Dados desenvolvida em Python e Streamlit que unifica dados macroeconômicos do Banco Central do Brasil (BACEN), cotações de mercado da B3 e demonstrações financeiras corporativas da Comissão de Valores Mobiliários (CVM).

A aplicação resolve a fragmentação de fontes públicas isoladas, oferecendo uma visão integrada, auditável e padronizada para suporte a decisões estratégicas de investimentos, controladoria e análise macro-fundamentalista. A plataforma é dividida em dois modos independentes com carregamento sob demanda (*lazy loading*):

* **DataOps Control Tower:** Interface corporativa para orquestração, execução e monitoramento do pipeline de ETL (Ingestão de dados por API $\rightarrow$ Bronze $\rightarrow$ Prata $\rightarrow$ Ouro) com logs estruturados em tempo real, relatórios de saúde da base e profiling de Análise Exploratória de Dados (EDA).
* **BI Executivo:** Painel interativo composto por 4 dashboards especializados (Macro, Fundamentalista, Mercado e Integrado) construídos sobre um modelo dimensional Star Schema otimizado.

---

## 2. Contexto de Negócio e Perguntas Orientadoras

O cenário econômico corporativo exige que gestores, CFOs e analistas de investimentos analisem conjuntamente fatores macroeconômicos, dinâmicas de mercado de ações e demonstrativos contábeis. A **Linha Integrada (Tríade Financeira)** busca responder a quatro perguntas estratégicas centrais:

1. **Impacto do Aperto Monetário:** De que maneira o ciclo de elevação da taxa Selic (de 2,00% para 13,75% a.a.) impactou a despesa financeira, o nível de alavancagem e o lucro líquido das companhias listadas?
2. **Sensibilidade Setorial aos Juros e Inflação:** Como a elevação simultânea das taxas de juros e da inflação oficial (IPCA) afetou o desempenho em bolsa (B3) dos setores de consumo/varejo em comparação a energia, materiais básicos e instituições financeiras?
3. **Proteção Cambial (*Hedge* Natural):** As empresas exportadoras de commodities apresentaram proteção de margens operacionais (EBIT) e valorização acionária em períodos de choque e estresse cambial (alta do Dólar PTAX)?
4. **Resiliência e Solidez Setorial:** Qual setor econômico apresentou o melhor equilíbrio multidimensional entre resiliência macroeconômica, solidez contábil e retorno de mercado?

---

## 3. Fonte de Dados e Licença

| Fonte | Tipo | Origem Oficial | URL Base / Endpoint | Séries / Relatórios | Período Selecionado | Método de Extração | Termos / Licença |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **BACEN SGS** | Oficial | Banco Central do Brasil | `[https://api.bcb.gov.br/dados/serie/bcdata.sgs](https://api.bcb.gov.br/dados/serie/bcdata.sgs).{codigo}/dados` | Selic (432, 1178), IPCA (433, 13522), Câmbio (1), IBC-Br (24364), Poupança (196) | 2019-01-01 a 2023-12-31 | API REST JSON (SGS) | Dados Abertos Governamentais |
| **B3 (Yahoo Finance)** | Não Oficial | Yahoo Finance API | `yfinance.download()` | Cotações diárias (Open, High, Low, Close, Volume) | 2019-01-01 a 2024-01-01 | Python `yfinance` (v1.7+) | Termos de Serviço Yahoo Finance |
| **CVM DFP** | Oficial | CVM (Dados Abertos) | `[https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/)` | `dfp_cia_aberta_{ano}.zip` (`DRE_con`, `BPA_con`, `BPP_con`) | 2019-01-01 a 2023-12-31 | HTTP Stream + Parse CSV (`cp1252`) | Dados Abertos CVM |
| **CVM Cadastro** | Oficial | CVM (Dados Abertos) | `[https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv](https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv)` | `cad_cia_aberta.csv` | Atual | HTTP CSV (`cp1252`) | Dados Abertos CVM |

> **Nota sobre a integração YFinance:** O acesso às cotações diárias via biblioteca `yfinance` é realizado em caráter estritamente acadêmico e de pesquisa, operando sob mecanismos automatizados de *backoff* e tratamento de erros de conexão.

### Relevância do Cadastro Oficial CVM (`cad_cia_aberta.csv`)

As demonstrações financeiras anuais (DFPs) disponibilizadas pela CVM utilizam exclusivamente o código de registro `CD_CVM` e o `CNPJ_CIA`. Nenhuma fonte contábil oficial realiza o cruzamento direto com os códigos de negociação em bolsa (**tickers da B3**, ex.: `PETR4`, `WEGE3`).

A ingestão prévia do arquivo `cad_cia_aberta.csv` cumpre três funções críticas no pipeline:

1. **Mapeamento Ticker $\rightarrow$ CD_CVM:** Validação do registro ativo da companhia aberta perante a CVM.
2. **Enriquecimento Cadastral:** Extração da Razão Social, Nome Comercial, CNPJ e Setor de Atividade para composição da dimensão `dim_empresa`.
3. **Filtragem Eficiente:** Descarte imediato de dados não relacionados aos ativos selecionados durante o *parsing* dos arquivos ZIP volumosos da CVM, reduzindo o uso de memória RAM e volume de escrita.

---

## 4. Pipeline de Engenharia de Dados (DataOps)

### 4.1. Arquitetura da Camada Bronze

A camada **Bronze** adota os princípios da Arquitetura Medalhão para ingestão e armazenamento de dados brutos (*raw layer*):

* **Extratores Orientados a Objetos (POO):** Módulos especialistas herdados da classe abstrata `BaseExtractor` (`BacenExtractor`, `B3Extractor`, `CvmExtractor`, `CadastroExtractor`).
* **Imutabilidade e Governança:** Os dados são salvos em formato bruto original, enriquecidos com metadados de controle (`_ingest_ts` para carimbo de data/hora e `_run_id` para identificação do ciclo de execução).
* **Persistência Dupla:** Armazenamento em arquivos Parquet particionados (`data/bronze/`) e sincronização no banco relacional PostgreSQL (Neon).
* **Reaproveitamento Inteligente de Cache:** Ingestão condicionada a um mecanismo de TTL (`BRONZE_TTL_DAYS`) e assinatura de parâmetros via arquivo `.meta.json`, evitando requisições redundantes.

### 4.2. Camada Prata (Tratamento, Higienização e Padronização)

A camada **Prata** aplica regras de limpeza, coerção de tipos, eliminação de duplicatas e mapeamento contábil padronizado.

#### Tratamentos por Fonte de Dados:

* **BACEN (`BacenCleaner`):** Parsing de datas em formato ISO (`YYYY-MM-DD`), conversão de valores numéricos, deduplicação por `(serie_codigo, data)` e validação de tolerância de consistência temporal.
* **B3 (`B3Cleaner`):** Higienização de tickers, filtro de preços zerados ou inválidos ($\le 0$), ordenação temporal, deduplicação por `(ticker, data)` e auditoria de consistência OHLC ($High \ge \max(Open, Close)$ e $Low \le \min(Open, Close)$).
* **CVM (`CvmCleaner` & `AccountMapper`):** Consolidação das tabelas DRE, BPA e BPP. Aplicação da escala monetária (multiplicação por $1.000$ quando informado `ESCALA_MOEDA == 'MIL'`) e ordenação por `VERSAO` para retenção exclusiva do demonstrativo retificado mais recente.
* **Segregação Contábil:** O componente `AccountMapper` diferencia empresas industriais/comerciais de instituições financeiras (Plano COSIF). Bancos possuem contas de intermediação financeira mapeadas de forma isolada e têm métricas industriais (Margem EBIT, Liquidez Corrente, Dívida Líquida) tratadas como nulas para evitar distorções agregadas.



#### Auditoria de Inconsistências Tratadas (Logs de Pipeline)

| Fonte | Inconsistência Identificada | Tratamento Aplicado no Pipeline | Impacto Auditado |
| --- | --- | --- | --- |
| **CVM** | Múltiplas versões de demonstrativos anuais retificadores | Ordenação por `VERSAO` mantendo apenas a versão final por `(cd_cvm, demonstrativo, cd_conta, dt_fim_exerc)` | 9.798 registros desduplicados |
| **CVM** | Divergência de valores entre o exercício atual (`ÚLTIMO`) e a reapresentação (`PENÚLTIMO`) | Mapeamento auditado retendo os valores da demonstração retificada mais recente | 629 contas atualizadas |
| **CVM / Bancos** | Conflito de códigos contábeis em instituições do setor financeiro | Restrição do mapeamento contábil por plano COSIF e palavras-chave específicas | Duplicidades eliminadas |
| **B3** | Cotações diárias com volume negociado nulo em dias de baixa liquidez | Manutenção da cotação com sinalização de alerta na flag de qualidade (`VOLUME_ZERO`) | 8 observações sinalizadas |
| **B3** | Oscilações extremas intra-dia ($> 30\%$) por proventos ou grupamentos | Preservação dos dados originais e adição de flag de auditoria (`RETORNO_EXTREMO`) | 3 observações sinalizadas |

### 4.3. Camada Ouro (Star Schema)

A camada **Ouro** estrutura os dados limpos em um modelo estelar (*Star Schema*), otimizado para consultas analíticas de alta performance no aplicativo.

```
                  ┌──────────────────┐
                  │    dim_tempo     │
                  └────────┬─────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────┴────────┐ ┌───────┴────────┐ ┌───────┴──────────────┐
│   fato_macro   │ │ fato_cotacoes  │ │ fato_demonstrativos  │
└───────┬────────┘ └───────┬────────┘ └───────┬──────────────┘
        │                  │                  │              │
        │                  └─────────┬────────┘              │
        │                            │                       │
        │                   ┌────────┴─────────┐             │
        │                   │   dim_empresa    │             │
        │                   └──────────────────┘             │
        │                                                    │
        └────────────────────────────┬───────────────────────┘
                                     │
                            ┌────────┴─────────┐
                            │  dim_indicador   │
                            └──────────────────┘

```

#### Estrutura Dimensional:

* **Dimensões:** `dim_tempo` (cobertura diária contínua), `dim_empresa` (cadastro corporativo com setor analítico e tipo de plano) e `dim_indicador` (catálogo de variáveis brutas e derivadas).
* **Tabelas Fato:** `fato_macro` (indicadores BACEN e Juro Real Ex-Post), `fato_cotacoes` (preços, retornos e médias móveis B3) e `fato_demonstrativos` (balanços e DREs CVM).
* **Persistência e Fallback:** Operação simultânea com gravação Parquet comprimido (`zstd`) em `data/gold/` e sincronização por `upsert` no PostgreSQL (Neon). Em caso de indisponibilidade de rede, o aplicativo realiza *fallback* automático para os arquivos Parquet locais.

### 4.4. Qualidade, Testes e Validação por Amostragem

A integridade do pipeline é auditada por uma suíte de testes unitários e de integração (`pytest src/etl/tests/test_gold.py`), atingindo **100% de aprovação (21/21 testes)** em chaves primárias, regras relacionais e cálculos derivados.

Adicionalmente, o script de auditoria pontual (`scripts/check_gold_sampling.py`) confrontou as métricas salvas no repositório contra dados públicos oficiais:

| Domínio | Indicador / Companhia | Data / Exercício | Valor no Banco (Ouro) | Fonte Oficial Publicada | Variação | Auditoria |
| --- | --- | --- | --- | --- | --- | --- |
| **BACEN** | Selic Meta (SGS 432) | 28/12/2023 | 11,75% a.a. | 11,75% a.a. | 0,00% | **Confirmado (100%)** |
| **BACEN** | IPCA 12M (SGS 13522) | 01/12/2023 | 4,62% a.a. | 4,62% a.a. | 0,00% | **Confirmado (100%)** |
| **CVM** | WEGE3 (Receita Líquida) | DFP 2023 | R$ 32.503.601.000,00 | R$ 32.840.981.000,00 | < 1,1% | **Validado (Residual)** |
| **CVM** | WEGE3 (Lucro Líquido) | DFP 2023 | R$ 5.867.615.000,00 | R$ 5.732.036.000,00 | < 2,4% | **Validado (Residual)** |

### 4.5. DataOps On-Demand e Profiling Estatístico (EDA)

#### 4.5.1. Orquestração do Pipeline

O **DataOps Control Tower** possibilita a execução do pipeline de dados sob demanda diretamente pela interface Streamlit.

* **Segregação de Ambientes:** Operação em modo **Sandbox** (requisições reais com gravação isolada em `data/_sandbox/` para testes sem alteração do banco produtivo) ou modo **Produção** (autenticado por senha com atualização de banco e persistência na Ouro).
* **Logs Estruturados:** Emissão contínua de eventos com nível, camada, módulo e mensagem, mantendo histórico em memória e filtros na interface.
* **Gestão de Memória:** Execução de `gc.collect()` e desalocação de objetos pesados ao término de cada fase do pipeline.

#### 4.5.2. Análise Exploratória de Dados (EDA)

A suíte de profiling estatístico (`DataProfiler`) realiza o diagnóstico de qualidade da camada Prata em modo somente leitura:

* **Integridade Cadastral e Temporal:** Confirmação de 0 duplicatas nas chaves naturais e verificação de continuidade temporal sem lacunas.
* **Diagnóstico de Outliers:** Identificação de picos de inflação nos biênios críticos e verificação da assimetria dos retornos diários acionários.

---

## 5. Dicionário de Dados (Camada Ouro)

### `dim_tempo` (Dimensão Calendário)

| Coluna | Tipo | Descrição Financeira / Regra de Negócio |
| --- | --- | --- |
| `sk_tempo` | `INTEGER` | Chave primária substituta no formato YYYYMMDD. |
| `data` | `DATE` | Data civil do registro. |
| `ano` | `INTEGER` | Ano civil de referência (ex: 2023). |
| `semestre` | `INTEGER` | Semestre civil (1 ou 2). |
| `trimestre` | `INTEGER` | Trimestre civil (1 a 4). |
| `mes` | `INTEGER` | Mês civil (1 a 12). |
| `ano_mes` | `VARCHAR` | Agregador mensal no formato 'YYYY-MM'. |
| `dia_util_b3` | `BOOLEAN` | Indicador de pregão ativo na B3. |

### `dim_empresa` (Dimensão Companhias Aberta)

| Coluna | Tipo | Descrição Financeira / Regra de Negócio |
| --- | --- | --- |
| `sk_empresa` | `INTEGER` | Chave substituta (código CVM da empresa). |
| `ticker` | `VARCHAR` | Código do ativo negociado na B3 (ex: WEGE3, ITUB4). |
| `cd_cvm` | `INTEGER` | Código oficial de registro na CVM. |
| `cnpj` | `VARCHAR` | CNPJ da companhia aberta. |
| `denom_cia` | `VARCHAR` | Razão social oficial da empresa. |
| `setor_cvm` | `VARCHAR` | Setor de atividade cadastrado na CVM. |
| `setor_analitico` | `VARCHAR` | Setor analítico padronizado do projeto. |
| `tipo_plano` | `VARCHAR` | Plano contábil ('industrial' ou 'financeira'). |
| `exportadora_commodities` | `BOOLEAN` | Flag de empresa exportadora primária. |
| `tem_cvm` | `BOOLEAN` | Indicador de presença nos relatórios DFP da CVM. |
| `tem_b3` | `BOOLEAN` | Indicador de cotações ativas na B3. |

### `dim_indicador` (Catálogo de Indicadores Financeiros)

| SK | Código | Nome do Indicador | Origem | Tipo | Unidade | Fórmula / Regra de Cálculo Aplicada |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `SELIC_META` | Taxa Selic Meta | BACEN | Bruto | % a.a. | Taxa meta definida pelo COPOM (SGS 432). |
| 2 | `SELIC_EFETIVA` | Taxa Selic Efetiva (Over) | BACEN | Bruto | % a.a. | Taxa diária ponderada das operações (SGS 1178). |
| 3 | `IPCA_MENSAL` | IPCA Mensal | BACEN | Bruto | % | Variação percentual mensal da inflação (SGS 433). |
| 4 | `IPCA_12M` | IPCA Acumulado 12M | BACEN | Bruto | % a.a. | Inflação acumulada em 12 meses (SGS 13522). |
| 5 | `PTAX_VENDA` | Dólar PTAX (Venda) | BACEN | Bruto | R$ | Cotação oficial de venda do Dólar (SGS 1). |
| 6 | `IBC_BR_SA` | IBC-Br Sazonalizado | BACEN | Bruto | Índice | Índice de atividade econômica do BACEN (SGS 24364). |
| 7 | `POUPANCA` | Rendimento Poupança | BACEN | Bruto | % | Rendimento mensal da poupança (SGS 196). |
| 8 | `JURO_REAL_EXPOST` | Juro Real Ex-Post | BACEN | Derivado | % a.a. | Equação de Fisher: $\frac{1 + \text{Selic}}{1 + \text{IPCA}} - 1$. |
| 9 | `RECEITA_LIQUIDA` | Receita Líquida | CVM | Bruto | R$ | DRE Conta 3.01 (Plano Industrial). |
| 10 | `LUCRO_BRUTO` | Resultado Bruto | CVM | Bruto | R$ | DRE Conta 3.03 (Plano Industrial). |
| 11 | `EBIT` | EBIT (Resultado Operacional) | CVM | Bruto | R$ | DRE Conta 3.05 (Resultado Operacional). |
| 12 | `DESP_FINANCEIRAS` | Despesas Financeiras | CVM | Bruto | R$ | DRE Conta 3.06.02 (Despesas Financeiras). |
| 13 | `LUCRO_LIQUIDO` | Lucro Líquido | CVM | Bruto | R$ | DRE Conta 3.11 (Lucro/Prejuízo do Período). |
| 14 | `ATIVO_CIRCULANTE` | Ativo Circulante | CVM | Bruto | R$ | BPA Conta 1.01. |
| 15 | `PASSIVO_CIRCULANTE` | Passivo Circulante | CVM | Bruto | R$ | BPP Conta 2.01. |
| 16 | `CAIXA_EQUIV` | Caixa e Equivalentes | CVM | Bruto | R$ | BPA Conta 1.01.01. |
| 17 | `APLIC_FINANC` | Aplicações Financeiras | CVM | Bruto | R$ | BPA Conta 1.01.02. |
| 18 | `EMPR_FIN_CP` | Empréstimos CP | CVM | Bruto | R$ | BPP Conta 2.01.04. |
| 19 | `EMPR_FIN_LP` | Empréstimos LP | CVM | Bruto | R$ | BPP Conta 2.02.01. |
| 20 | `PATRIMONIO_LIQUIDO` | Patrimônio Líquido | CVM | Bruto | R$ | BPP Conta 2.03. |
| 21 | `RECEITA_INTERMEDIACAO` | Receita Intermediação | CVM | Bruto | R$ | DRE Conta 3.01 (Instituições Financeiras / COSIF). |
| 22 | `MARGEM_LIQUIDA` | Margem Líquida | CVM | Derivado | Fração | $\frac{\text{Lucro Líquido}}{\text{Receita Líquida}}$ |
| 23 | `MARGEM_EBIT` | Margem EBIT | CVM | Derivado | Fração | $\frac{\text{EBIT}}{\text{Receita Líquida}}$ |
| 24 | `ROE` | Return on Equity (ROE) | CVM | Derivado | Fração | $\frac{\text{Lucro Líquido}}{\text{Patrimônio Líquido}}$ |
| 25 | `LIQUIDEZ_CORRENTE` | Liquidez Corrente | CVM | Derivado | Razão | $\frac{\text{Ativo Circulante}}{\text{Passivo Circulante}}$ |
| 26 | `DIVIDA_BRUTA` | Dívida Bruta | CVM | Derivado | R$ | $\text{Empréstimos CP} + \text{Empréstimos LP}$ |
| 27 | `DIVIDA_LIQUIDA` | Dívida Líquida | CVM | Derivado | R$ | $\text{Dívida Bruta} - (\text{Caixa} + \text{Aplicações})$ |
| 28 | `CRESC_RECEITA` | Crescimento Receita (YoY) | CVM | Derivado | Fração | $\frac{\text{Receita}_t}{\text{Receita}_{t-1}} - 1$ |
| 29 | `RETORNO_DIARIO` | Retorno Percentual Diário | B3 | Derivado | Fração | $\frac{\text{Close}_t}{\text{Close}_{t-1}} - 1$ |
| 30 | `SMA_21` | Média Móvel Simples 21D | B3 | Derivado | R$ | Média móvel simples do preço ajustado (21 dias). |
| 31 | `SMA_50` | Média Móvel Simples 50D | B3 | Derivado | R$ | Média móvel simples do preço ajustado (50 dias). |
| 32 | `VOLUME_FIN_APROX` | Volume Financeiro Aproximado | B3 | Derivado | R$ | $\text{Close Ajustado} \times \text{Volume Quantidade}$ |

### Fatos do Modelo Dimensional

* `fato_macro`: Guarda a série histórica diária/mensal dos indicadores BACEN (`sk_tempo`, `sk_indicador`, `valor`).
* `fato_cotacoes`: Armazena preços e volumes da B3 (`sk_tempo`, `sk_empresa`, `open`, `high`, `low`, `close`, `volume`, `volume_fin_aprox`, `retorno_diario`, `sma_21`, `sma_50`).
* `fato_demonstrativos`: Registra o saldo contábil anual padronizado da CVM (`sk_tempo`, `sk_empresa`, `sk_indicador`, `valor`).

---

## 6. Tecnologias e Bibliotecas

| Tecnologia / Biblioteca | Categoria | Justificativa Técnica para Escolha no Projeto |
| --- | --- | --- |
| **Python 3.11** | Linguagem | Ambiente moderno com excelente performance em processamento de dados e suporte a tipagem. |
| **Streamlit (v1.40+)** | Interface / Web | Construção rápida de Data Apps reativos em Python nativo com suporte a componentes modernos (`st.tabs`, `st.metric`). |
| **Plotly Express / Graph Objects** | Visualização | Biblioteca líder para gráficos interativos, suporte a hover customizado, subplots e exportação em alta definição. |
| **Pandas & NumPy** | Manipulação | Estruturas de dados vetoriais de alta performance para limpeza, agrupamento, pivots e cálculos estatísticos. |
| **PyArrow** | Armazenamento | Manipulação eficiente de arquivos no formato Parquet com suporte a pushdown de filtros e compressão `zstd`. |
| **SQLAlchemy & psycopg2-binary** | Banco de Dados | ORM e driver relacional para conexão segura e otimizada ao PostgreSQL na nuvem via `st.connection`. |
| **yfinance** | Coleta B3 | Biblioteca para ingestão de séries temporais históricas de preços e volumes ajustados de ações da B3. |
| **Requests** | Ingestão HTTP | Realização de chamadas resilientes às APIs REST do BACEN (SGS) e downloads dos arquivos DFP da CVM. |
| **Pytest** | Qualidade | Framework para escrita e execução automatizada de testes unitários e de integração no pipeline. |

---

## 7. Principais Resultados e Evidências Numéricas

A análise integrada das três bases de dados no período de 2019 a 2023 revelou achados quantitativos de destaque:

### 7.1. Macroeconomia (BACEN)

* **Topo da Taxa Selic:** A taxa básica de juros atingiu seu valor máximo de **13,75% a.a. em agosto de 2022**, mantendo-se constante até o início do ciclo de afrouxamento monetário em agosto de 2023.
* **Pico do Juro Real Ex-Post:** O maior patamar de Juro Real calculado pela Equação de Fisher ocorreu em **setembro de 2023, atingindo 7,57% a.a.**, resultado da desaceleração do IPCA 12M em contraste com a queda gradual da Selic.
* **Patamar Cambial:** O Dólar PTAX Venda registrou média histórica de **R$ 5,16** na janela temporal analisada.

### 7.2. Análise Fundamentalista (CVM)

* **Volume de Receita Líquida:** As companhias industriais e comerciais analisadas movimentaram **R$ 744,38 bilhões em Receita Líquida em 2023**, representando um avanço de +20,00% na comparação com 2022.
* **Geração de Lucro Consolidado:** O Lucro Líquido total consolidado (incluindo instituições financeiras) somou **R$ 122,21 bilhões no exercício de 2023**.
* **Retorno sobre o Patrimônio (ROE):** O ROE médio da carteira fechou em **19,00% em 2023**, liderado por companhias dos setores de Materiais Básicos e Energia.

### 7.3. Performance de Mercado (B3)

* **Rentabilidade Acumulada:** A carteira equiponderada de ativos registrou retorno médio acumulado de **+217,60% na janela histórica**. O ativo de maior valorização nominal foi **PRIO3 (+2.126,92%)**, enquanto a menor performance ficou com **LREN3 (-45,79%)**.
* **Eficiência de Sharpe:** A empresa **PRIO3** obteve o maior Índice de Sharpe empírico da amostra, apresentando a melhor relação entre excesso de retorno e volatilidade anualizada.

### 7.4. Visão Integrada da Tríade

* **Resultado Agregado da Carteira:** Sob o patamar da Selic em 11,75% a.a., o universo consolidado registrou R$ 1.258,90 bilhões em Receita Líquida Industrial e R$ 275,64 bilhões em Lucro Líquido.
* **Liderança no Score Multidimensional:** O setor de **Materiais Básicos** obteve a maior pontuação agregada no Ranking Setorial (73,6 pts), impulsionado por elevada solidez contábil (100,0 pts) e resiliência a choques macroeconômicos (88,7 pts).

---

## 8. Discussão e Limitações da Análise

### 8.1. Limitações Metodológicas e Rigor Analítico

* **Ausência de Causalidade Direta:** As associações estatísticas, matrizes de correlação de Pearson e gráficos de dispersão apresentados no Data App indicam interdependência histórica entre variáveis, **não estabelecendo relação de causalidade determinística**.
* **Matrizes em Níveis vs. Variações:** As análises de correlação entre valores absolutos de séries macroeconômicas podem apresentar componentes de tendência estocástica. Recomenda-se a avaliação em primeira diferença (variações) disponibilizada nos filtros do Dashboard 1.
* **Interseção de Frequências Temporais:** A combinação entre séries diárias (B3 e Selic Over), mensais (IPCA e IBC-Br) e anuais (CVM) exige alinhamento no grão apropriado de cada indicador sem interpolação artificial.

### 8.2. Especificidades Contábeis e Setor Financeiro

* **Instituições Financeiras (Plano COSIF):** Devido à estrutura própria de balanço dos bancos (ausência de custo de bens vendidos ou estoque tradicional), indicadores como Margem EBIT, Liquidez Corrente e Dívida Líquida são nulos e rotulados como `N/A`. A Receita de Intermediação Financeira é mantida de forma isolada da Receita Líquida Industrial.
* **Patrimônio Líquido Negativo ($PL \le 0$):** Companhias que apresentam passivo a descoberto em exercícios específicos possuem o cálculo de ROE suspenso para evitar distorções de inversão de sinal matemático.
* **Valores Nominais:** Os demonstrativos da CVM refletem valores históricos nominais reportados pelas empresas sem atualização inflacionária.

### 8.3. Coleta de Dados e Fontes Externas

* **Estimativa de Volume Financeiro:** A API publica o volume negociado em quantidade de títulos. O volume financeiro em Reais é estimado pelo produto $Close \times Qty$.
* **Reapresentações DFP:** O pipeline retém exclusivamente a última versão retificadora oficial enviada pelas empresas à CVM.
* **Indisponibilidade Pontual:** Eventuais falhas de retorno em tickers específicos na extração YFinance são contornadas via descarte seguro com registro nos logs do DataOps.

---

## 9. Aplicação Profissional e Decisões de Negócio

A plataforma oferece suporte prático a diferentes personas do ambiente corporativo e financeiro:

* **Diretores Financeiros (CFOs) e Controllers:** Avaliação do custo de carregamento do passivo frente às oscilações da Selic, acompanhamento do impacto das despesas financeiras sobre o lucro líquido e monitoramento dos índices de solvência corporativa.
* **Gestores de Carteira e Analistas de Investimento:** Identificação de empresas com elevado Retorno sobre o Patrimônio (ROE), mapeamento de ativos com melhor relação risco-retorno (Sharpe) e análise da capacidade de repasse de preços e proteção cambial de setores exportadores.
* **Comitês de Risco e Estratégia:** Simulação de cenários de estresse através de parâmetros ajustáveis na interface (limiares de estresse cambial e cortes de liquidez), permitindo antecipar impactos sobre a saúde financeira dos setores.

---

## 10. Demonstração do Data App (Streamlit)

### 10.1. Arquitetura de Interface e UX

* **Roteamento Sob Demanda (*Lazy Loading*):** Gerenciado centralmente em `app.py` via `st.session_state["modo"]`. Módulos pesados de visualização e ETL não são importados na abertura do app, reduzindo o tempo de carregamento inicial e consumo de memória RAM.
* **Design System Isolado:** Variáveis e tokens visuais centralizados no Python e exportados para a folha de estilos `src/ui/styles/theme.css`. As classes possuem prefixo dedicado (`.fx-card`, `.fx-badge`) evitando conflito com o CSS nativo do Streamlit.
* **Sidebar Global e Filtros Locais:** A barra lateral controla o universo global de análise (período de datas, tickers e setores), enquanto painéis retráteis no topo de cada dashboard oferecem refinamentos específicos.

### 10.2. Landing Page e Navegação

A tela de abertura apresenta a visão geral dos modos de operação da plataforma com carregamento sob demanda:

<br>

![app_landing](./images/app_landing.png)

<br>

O painel lateral (Sidebar) oferece filtros cruzados com suporte a seleção de período, tickers, setores e botão funcional de reset:

<br>

![app_filtros](./images/d1_filtro_global.png)

<br>

### 10.3. DataOps Control Tower & Profiling (EDA)

Interface dedicada à gestão de pipeline e diagnósticos estatísticos de qualidade dos dados:

* **Parametrização e Carga:**

<br>

![dataops_parametros](./images/dataops/dataops_etl_parametros_carga.png)

<br>


* **Relatório de Saúde da Base (Ouro):**

<br>

![dataops_saude](./images/dataops/dataops_etl_relatorio_saude.png)

<br>


* **Painel de Análise Exploratória (EDA):**
| Módulo EDA | Visualização de Diagnóstico |
| --- | --- |
| **Qualidade & Duplicatas** | ![dataops_eda1](./images/dataops/dataops_eda_1_nulos_duplicatas.png) |
| **Distribuições & Outliers** | ![dataops_eda2](./images/dataops/dataops_eda_2_distribuicoes.png) |
| **Cobertura Temporal** | ![dataops_eda3](./images/dataops/dataops_eda_3_cobertura_temporal.png) |
| **Estatísticas Descritivas** | ![dataops_eda4](./images/dataops/dataops_eda_4_estatisticas.png) |
| **Matriz de Achados** | ![dataops_eda5](./images/dataops/dataops_eda_5_achados_qualidade.png) |



### 10.4. Dashboard 1 — Inteligência Macroeconômica (BACEN)

Monitoramento das séries temporais oficiais do Banco Central do Brasil:

* **Visão Geral:** KPIs estratégicos e gráfico combinado da política monetária.

<br>

![d1_1](./images/d1/d1_1_visao_geral.png)

<br>

* **Câmbio (PTAX):** Série histórica com destaques acima da média e dispersão cambial.

<br>

![d1_2](./images/d1/d1_2_cambio_ptax.png)

<br>

* **Atividade Econômica:** Trajetória do IBC-Br dessazonalizado e bandas de ciclos monetários.

<br>

![d1_3](./images/d1/d1_3_atividade_economica.png)

<br>

* **Correlações:** Matriz térmica de Pearson e tabela paramétrica de defasagens.

<br>

![d1_4](./images/d1/d1_4_correlacoes.png)

<br>

* **Dados & Metodologia:** Leitura tabular e nota explicativa da Equação de Fisher.

<br>

![d1_5](./images/d1/d1_5_dados_filtro_local.png)

<br>


### 10.5. Dashboard 2 — Análise Fundamentalista & Contábil (CVM)

Diagnóstico de desempenho e solvência das companhias abertas:

* **Visão Geral:** Métricas consolidadas e distribuição setorial de receita.

<br>

![d2_1](./images/d2/d2_1_visao_geral.png)

<br>


* **Rentabilidade:** Scatter em quadrantes (Margem vs. ROE) e boxplots de Margem EBIT.

<br>

![d2_2](./images/d2/d2_2_rentabilidade.png)

<br>

* **Solvência:** Comparativo de Dívida Líquida vs. Liquidez Corrente com limiar ajustável.

<br>

![d2_3](./images/d2/d2_3_solvencia.png)

<br>

* **Dados & Metodologia:** Demonstrativos limpos e regras de enquadramento contábil.

<br>

![d2_4](./images/d2/d2_4_dados_filtro_local.png)

<br>


### 10.6. Dashboard 3 — Mercado e Risco (B3)

Inteligência quantitativa de ativos cotados em bolsa:

* **Rentabilidade Normalizada:** Desempenho comparativo com curva de nível Base 100.

<br>

![d3_1](./images/d3/d3_1_rentabilidade.png)

<br>

* **Risco e Retorno:** Scatter Risco vs. Retorno e tabela de indicadores ajustados (Sharpe/VaR).

<br>

![d3_2](./images/d3/d3_2_risco_retorno.png)

<br>

* **Distribuição dos Retornos:** Histograma de frequência com boxplot marginal.

<br>

![d3_3](./images/d3/d3_3_distribuicao_dos_retornos.png)

<br>

* **Drawdown:** Curva temporal de queda a partir do pico histórico.

<br>

![d3_4](./images/d3/d3_4_drawdown.png)

<br>

* **Tendência (Média Móvel):** Fechamento acompanhado das médias simples SMA 21 e SMA 50.

<br>

![d3_5](./images/d3/d3_5_tendencia.png)

<br>

* **Dados & Metodologia:** Notificações técnicas e premissas de cálculo da taxa livre de risco.

<br>

![d3_6](./images/d3/d3_6_dados_filtro_local.png)

<br>


### 10.7. Dashboard 4 — Visão Integrada da Tríade

Cruzamento analítico multidimensional unificando BACEN, CVM e B3:

* **Visão Integrada:** Resumo executivo da carteira e gráfico multieixo macro-cambial.

<br>

![d4_1](./images/d4/d4_1_visao_integrada.png)

<br>

* **Contabilidade e Mercado:** Lucro e ROE confrontados com o retorno em bolsa.

<br>

![d4_2](./images/d4/d4_2_contabilidade_mercado.png)

<br>

* **Juros e Setores:** Retorno setorial cruzado com a Selic Média Anual.

<br>

![d4_3](./images/d4/d4_3_juros_setores.png)

<br>

* **Câmbio e Exportadoras:** Análise de sensibilidade em cenários de estresse cambial.

<br>

![d4_4](./images/d4/d4_4_cambio_exportadoras.png)

<br>

* **Ranking Setorial:** Score multidimensional parametrizável por pesos de pilares.

<br>

![d4_5](./images/d4/d4_5_ranking_setorial.png)

<br>

* **Dados & Metodologia:** Documentação consolidada das regras metodológicas integradas.

<br>

![d4_6](./images/d4/d4_6_dados_filtro_local.png)

<br>


---

## 11. Como Executar Localmente

### Pré-requisitos

* Python 3.11 instalado na máquina local.
* Git para clonagem do repositório.

### Passo a Passo

1. **Clonar o Repositório:**
```bash
git clone https://github.com/lf-vampre/sctec-datascience-projeto-avaliativo-2
cd sctec-datascience-projeto-avaliativo-2

```


2. **Criar e Ativar o Ambiente Virtual:**
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

```


3. **Instalar as Dependências:**
```bash
pip install --upgrade pip
pip install -r requirements.txt

```


4. **Configurar os Arquivos de Segredos (Opcional para Banco Neon):**
Crie a pasta `.streamlit/` na raiz do projeto e adicione o arquivo `secrets.toml` baseado no exemplo disponibilizado:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

```


*Nota: Caso as credenciais do PostgreSQL não sejam preenchidas, o aplicativo ativará automaticamente o modo de fallback Parquet.*
5. **Executar o Data App:**
```bash
streamlit run app.py

```

---

## 12. Estrutura de Pastas do Repositório

```
plataforma-financeira-triade/
├── .streamlit/                # Configurações do servidor e secrets
│   ├── config.toml            # Tema nativo do Streamlit
│   └── secrets.toml.example   # Modelo de variáveis de ambiente
├── data/                      # Repositório de dados em camadas
│   ├── _sandbox/              # Execuções de teste do DataOps
│   ├── bronze/                # Arquivos brutos (ignorado no Git)
│   ├── silver/                # Arquivos higienizados (ignorado no Git)
│   └── gold/                  # Modelo dimensional Star Schema (VERSIONADO)
├── images/                    # Imagens e capturas de tela da documentação
│   ├── d1/                    # Screenshots do Dashboard Macro
│   ├── d2/                    # Screenshots do Dashboard Fundamentalista
│   ├── d3/                    # Screenshots do Dashboard Mercado
│   ├── d4/                    # Screenshots do Dashboard Integrado
│   ├── dataops/               # Screenshots do DataOps e Profiling EDA
│   └── trello/                # Screenshots de acompanhamento Kanban
├── scripts/                   # Scripts utilitários de validação e auditoria
├── src/                       # Código-fonte modularizado do projeto
│   ├── config/                # Parâmetros globais, temas e universo
│   ├── etl/                   # Extratores, higienizadores e warehouse
│   │   ├── cleaners/          # Módulos de limpeza e mapeamento contábil
│   │   ├── eda/               # Profiling estatístico e diagnóstico
│   │   ├── extractors/        # Ingestão de APIs e dados abertos
│   │   ├── tests/             # Suíte de testes unitários de ETL
│   │   └── warehouse/         # Modelagem Star Schema e persistência
│   ├── models/                # Dataclasses e contratos de dados
│   ├── ui/                    # Componentes de interface gráfica
│   │   ├── charts/            # Geradores de figuras Plotly
│   │   ├── components/        # Wrappers de métricas, headers e notas
│   │   ├── dashboards/        # Layouts dos 4 dashboards
│   │   ├── prep/              # Preparação analítica e storytelling
│   │   ├── styles/            # Estilos CSS isolados
│   │   └── tests/             # Testes de integração da interface
│   └── utils/                 # Formatação, gestão de memória e caminhos
├── app.py                     # Entrypoint e roteador principal do aplicativo
├── README.md                  # Documentação executiva completa do projeto
└── requirements.txt           # Mapeamento de dependências com versões fixadas

```

---

## 13. Gestão Ágil e Links do Projeto

O planejamento e o acompanhamento de todas as entregas do projeto foram conduzidos de forma autônoma utilizando a metodologia Kanban no Trello.

* **Fluxo de Trabalho:** Estruturado nas colunas *Backlog*, *A Fazer*, *Em Andamento* e *Concluído*.
* **WIP Limit (Trabalho em Andamento):** Mantida rigorosamente a regra de apenas 1 card ativo por vez na coluna *Em Andamento*.

### Registros do Quadro Kanban

* **Fase Inicial de Planejamento (Estruturação do Backlog):**

<br>

![trello_inicio](./images/trello/trello_inicio.png)

<br>

* **Fase Final de Conclusão (Todas as Histórias Entregues):**

<br>

![trello_final](./images/trello/trello_final.png)

<br>


### Links Oficiais do Projeto

* **Quadro Público no Trello:** [Acessar Quadro Kanban](https://trello.com/invite/b/6adab459be4196e0b94991da/ATTI6636f5b2655040c9f3624788e2d6c788F8374B53/projeto-final-sctec-felipe-vampre)
* **Aplicação em Produção (Streamlit Cloud):** [Acessar Data App]()
* **Vídeo de Demonstração (Pitch Executivo):** [Assistir Vídeo do Projeto]()

---

## 14. Autoria e Créditos

* **Desenvolvedor:** Luiz Felipe F V Vieira


### Referências Bibliográficas e Fontes Consultadas

1. **Banco Central do Brasil (BACEN):** Portal de Dados Abertos e API do Sistema Gerenciador de Séries Temporais (SGS).
2. **Comissão de Valores Mobiliários (CVM):** Portal de Dados Abertos — Demonstrações Financeiras Padronizadas (DFP) e Cadastro de Companhias Abertas.
3. **B3 (Brasil, Bolsa, Balcão):** Dados históricos de cotações e negociação de ativos.
4. **Fisher, Irving:** *The Theory of Interest*. Macmillan, 1930 (Equação de Fisher para determinação do Juro Real).
5. **Streamlit Documentation:** *API Reference and Architecture Guidelines* (Streamlit v1.40+).
6. **Plotly Python Open Source Graphing Library:** *Plotly Express and Subplots Documentation*.


### Versionamento e Histórico de Commits (git log --oneline)

