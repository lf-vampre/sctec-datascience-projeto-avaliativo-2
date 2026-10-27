![Logos](./images/logos.png)

<br>
<br>

# Plataforma Financeira Integrada (Tríade BACEN + B3 + CVM)

## 1. Título e Resumo Executivo

A **Plataforma Financeira Integrada** é uma solução Fullstack de Dados desenvolvida em Python e Streamlit que unifica dados macroeconômicos do Banco Central do Brasil (BACEN), cotações de mercado da B3 e demonstrações financeiras corporativas da Comissão de Valores Mobiliários (CVM).

A aplicação resolve a fragmentação de fontes públicas isoladas, oferecendo uma visão integrada, auditável e padronizada para suporte a decisões de investimentos e análise macro-fundamentalista. A plataforma é dividida em dois modos independentes com carregamento sob demanda (*lazy loading*):

- **DataOps Control Tower:** Interface para orquestração, execução e monitoramento do pipeline de ETL (Ingestão de dados por API → Bronze → Prata → Ouro) com logs estruturados, estatísticas de saúde e Profiling (EDA).

- **BI Executivo:** Painel interativo composto por 4 dashboards especializados (Macro, Fundamentalista, Mercado e Integrado) construídos sobre um modelo Star Schema.

---

## 2. Contexto de Negócio e Pergunta Orientadora
> 🚧 A preencher no Card 7 (Trello)

---

## 3. Fonte de Dados e Licença

| Fonte | Tipo | Origem Oficial | URL Base | Séries / Relatórios / Tabelas | Período Selecionado | Método de Extração | Termos / Licença |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BACEN SGS** | Oficial | Banco Central do Brasil | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados` | Selic (432, 1178), IPCA (433, 13522), Câmbio (1), IBC-Br (24364), Poupança (196) | 2019-01-01 a 2023-12-31 | API REST JSON (SGS) | Dados Abertos Governamentais (Uso Público) |
| **B3 (Yahoo Finance)** | Não Oficial | Yahoo Finance API | `yfinance.download()` | Cotações diárias (Open, High, Low, Close, Volume) | 2021-01-01 a 2023-12-31 | Python `yfinance` (v1.7+) | Termos de Serviço do Yahoo Finance (Uso Educacional/Pesquisa) |
| **CVM DFP** | Oficial | CVM (Dados Abertos) | `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/` | `dfp_cia_aberta_{ano}.zip` (`DRE_con`, `BPA_con`, `BPP_con`) | 2021-01-01 a 2023-12-31 | Download HTTP ZIP + Parse CSV Stream | Dados Abertos CVM (Uso Público) |
| **CVM Cadastro** | Oficial | CVM (Dados Abertos) | `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv` | `cad_cia_aberta.csv` | Atual | Download HTTP CSV (`cp1252`) | Dados Abertos CVM (Uso Público) |

> **Nota sobre o Yahoo Finance (`yfinance`):** Trata-se de uma biblioteca não oficial mantida pela comunidade para raspagem/acesso à API pública do Yahoo Finance. Sujeita a limitações de *rate limit*, bloqueios de User-Agent e mudanças estruturais nos retornos sem aviso prévio.

### Por que baixar o `cad_cia_aberta.csv`?

As demonstrações financeiras da CVM (DFPs) utilizam exclusivamente o código interno da CVM (`CD_CVM`) e o `CNPJ_CIA`. Nenhuma fonte oficial da CVM realiza a ponte direta entre o código de negociação em bolsa (**ticker da B3**, ex.: `PETR4`, `WEGE3`) e a companhia aberta.

A utilização do cadastro oficial (`cad_cia_aberta.csv`) permite:
1. **Mapeamento Ticker → CD_CVM:** Confirmar a existência legal e o status do registro da companhia na CVM.
2. **Obtenção de Metadados:** Prover dados cadastrais essenciais como CNPJ, Razão Social, Nome Comercial e Setor de Atividade para a tabela dimensional `dim_empresa`.
3. **Filtragem Eficiente:** Filtrar os arquivos ZIP volumosos da CVM apenas para as companhias selecionadas no projeto, reduzindo drásticamente a utilização de RAM, volume de armazenamento local e escritas no banco de dados Neon.

---

## 4. Pipeline de Engenharia de Dados

### Arquitetura da Camada Bronze

A camada **Bronze** adota a Arquitetura Medalhão para ingestão e armazenamento de dados brutos (*raw layer*):

- **Extratores Orientados a Objetos (POO):** Cada fonte possui sua classe especialista herdada de `BaseExtractor` (`BacenExtractor`, `B3Extractor`, `CvmExtractor`, `CadastroExtractor`).
- **Preservação de Dados Crus:** Todos os dados são ingeridos na forma original (tipagem textual de segurança para CVM/Cadastro e estruturas originais do BACEN/B3), adicionando apenas metadados de governança (`_ingest_ts` e `_run_id`).
- **Persistência Dupla:** Armazenamento local otimizado em arquivos `.parquet` particionados (`data/bronze/`) e espelhamento no banco relacional Neon.
- **Mecanismo de TTL (Time-To-Live):** Evita chamadas redundantes a APIs externas reaproveitando arquivos Bronze válidos dentro do janela definida (`BRONZE_TTL_DAYS`).
- **Gestão Eficiente de Memória:** Coleta explicita de lixo (`gc.collect()`) e liberação de ponteiros de memória (`release()`) ao processar anos/arquivos volumosos.
- **Limitações e inconsistências encontradas:** As Limitações Conhecidas e Observações das Extrações (Camada Bronze) estáo listadas no tópico *8. Discussão e Limitações da Análise*.

---

## 5. Dicionário de Dados
> 🚧 A preencher no Card 4 (Trello)

---

## 6. Tecnologias e Bibliotecas
> 🚧 A preencher no Card 12 (Trello)

---

## 7. Principais Resultados e Evidências Numéricas
> 🚧 A preencher no Card 10 (Trello)

---

## 8. Discussão e Limitações da Análise
> 🚧 A preencher no Card 10 (Trello)

- **Instituições Financeiras:** Devido ao plano de contas específico (COSIF), bancos possuem métricas não aplicáveis (Margem EBIT, Liquidez Corrente, Dívida Líquida) exibidas como N/A.

- **Janela de Amostra:** A análise de mercado limita-se à janela temporal configurada (2019–2023), impactando a representatividade estatística.

- **Agrupamento Setorial:** Classificação analítica própria para garantia de comparabilidade.

### Limitações Conhecidas e Observações das Extrações (Camada Bronze)

#### 1. Indisponibilidade de Tickers na B3 (Yahoo Finance / `yfinance`)
- **`EMBR3` e `JBSS3`:** Durante a extração em produção via `yfinance`, as chamadas para esses tickers retornaram erros HTTP 404 e ausência de metadados de fuso horário (*timezone*).
- **Tratamento:** O `B3Extractor` loga um aviso (`WARNING`), ignora o ticker problemático e prossegue com a ingestão dos demais ativos sem interromper a execução do pipeline.

#### 2. Divergências e Inconsistências no Cadastro CVM (`cad_cia_aberta.csv`)
- **Mapeamento de Tickers (`GGBR4`):** O ticker `GGBR4` (Gerdau S.A. - CD_CVM 3310) apresentou divergência de identificação no cadastro ativo recente da CVM.
- **Empresas Canceladas ou Duplicadas:** Foram identificados registros históricos duplicados (ex.: CD_CVM `9512`) e companhias com situação cadastral `CANCELADA`.
- **Tratamento:** O `CadastroExtractor` e o `CvmExtractor` emitem alertas de validação e filtram apenas os dados aplicáveis, garantindo que o processamento das demonstrações financeiras (DFPs) não seja interrompido por inconsistências da fonte oficial.

---

## 9. Aplicação Profissional e Decisões de Negócio
> 🚧 A preencher no Card 10 (Trello)

---

## 10. Demonstração do Data App (Streamlit)
> 🚧 A preencher no Card 12 (Trello)

---

## 11. Como Executar Localmente
> 🚧 A preencher no Card 12 (Trello)

---

## 12. Estrutura de Pastas

```
sctec-datascience-projeto-avaliativo-2/
├── app.py                     # Entrypoint da aplicação e roteamento
├── requirements.txt           # Dependências com versões fixadas
├── .gitignore                 # Regras de exclusão do Git
├── README.md                  # Documentação principal
├── .streamlit/                # Configurações nativas do Streamlit e secrets
│   ├── config.toml            # Tema base e parâmetros do servidor
│   └── secrets.toml.example   # Modelo de variáveis de ambiente e conexões
├── data/                      # Armazenamento em camadas
│   ├── bronze/                # Dados brutos das APIs e arquivos (ignorado no git)
│   ├── silver/                # Dados limpos, tipados e padronizados (ignorado no git)
│   ├── gold/                  # Modelo dimensional Star Schema (VERSIONADO)
│   └── _sandbox/              # Execuções de teste do DataOps
├── images/                    # Imagens da documentação (README.md)
└── src/                       # Código-fonte modularizado
    ├── config/                # Mapeamento do universo, contas e parâmetros centrais
    ├── models/                # Dataclasses e contratos de dados
    ├── etl/                   # Pipeline de dados (sem dependência da UI)
    │   ├── extractors/        # Módulos de ingestão de dados brutos
    │   ├── cleaners/          # Módulos de limpeza e padronização
    │   ├── warehouse/         # Carga do Star Schema e cálculo de métricas
    │   ├── eda/               # Profiling de qualidade e análise exploratória (substitui notebooks/)
    │   └── tests/             # Testes das camadas ETL
    ├── ui/                    # Interface gráfica do usuário
    │   ├── dashboards/        # Módulos de dashboards do BI Executivo
    │   ├── charts/            # Construção de figuras e gráficos Plotly
    │   ├── components/        # Componentes e wrappers reutilizáveis de UI
    │   ├── prep/              # Preparação de dados para visualização
    │   └── styles/            # Folhas de estilo CSS customizadas
    └── utils/                 # Utilitários de caminhos, memória e formatação
```

> **Nota:** A pasta `notebooks/` (solicitada na documentação do projeto) foi substituída pelo módulo `src/etl/eda/`, permitindo a execução do Análise Exploratória de Dados (EDA) e Profiling diretamente na interface do DataOps Control Tower.

---

## 13. Gestão Ágil e Links do Projeto
- **Quadro Trello do Projeto:** [Acessar Trello](https://trello.com/invite/b/)
- **Streamlit Cloud (Data App):** *A preencher no Card 12*
- **Vídeo de Demonstração (Pitch):** *A preencher no Card 13*

Todo o fluxo de implementação do projeto foi distribuido em 13 cards colocados na coluna `Backlog` do Trello. Cada card com a descrição da branch específica, o checklist de tarefas e o cronograma (data prevista para iniciar e finalizar as tarefas).

Na data prevista, o card é movido para coluna `A Fazer`, desta forma é possível visualizar se o cronograma está sendo cumprido ou está atrasado. Somente 1 card pode estar na coluna `Em Andamento` enquanto está sendo executado. Uma vez concluído é colocado na coluna `Concluído`.


![Print do Quadro Inicial do Trello](images/trello01.png)  
*(Demonstrativo de uma tarefa concluída, uma sendo executada em atraso, duas em espera e backlog)*

---

## 14. Autoria e Créditos
- **Autor:** Luiz Felipe F V Vieira
