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
> 🚧 A preencher no Card 2 (Trello)

---

## 4. Pipeline de Engenharia de Dados
> 🚧 A preencher no Card 2 (Trello)

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
