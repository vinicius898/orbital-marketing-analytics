# orbital-marketing-analytics

# 🚀 Marketing Data Platform: Atribuição Multicanal com Cadeias de Markov

## 📌 O Problema de Negócio
No ecossistema de marketing digital, a atribuição "Last-Click" (Último Clique) superestima canais de fundo de funil e ignora o impacto de campanhas de descoberta. O resultado é uma alocação ineficiente do orçamento de mídia paga. 

O objetivo deste projeto é processar logs brutos de navegação, estruturar a jornada completa do cliente no funil de vendas e utilizar **Cadeias de Markov** para distribuir o crédito das conversões de forma probabilística e matemática, revelando o verdadeiro ROAS (Return on Ad Spend) de cada canal.

## 🏗️ Arquitetura de Dados e Stack Tecnológica
Para garantir escalabilidade e confiabilidade dos dados, a arquitetura foi desenhada simulando um ambiente de Big Data:

* **Data Warehouse (BigQuery):** Armazenamento dos logs de eventos e origens de tráfego (UTMs).
* **Processamento Distribuído (Databricks / PySpark):** Limpeza de dados aninhados (nested schemas), Window Functions para ordenação cronológica e agregação de jornadas complexas.
* **Modelagem Estatística (Python / Pandas / Numpy):** Construção vetorial da Matriz de Transição e cálculo do **Efeito de Remoção** (Removal Effect) para inferência causal.
* **Visualização (Looker Studio / Plotly):** Dashboards executivos focados em inteligência de negócio e diagramas de Sankey para mapeamento visual de fluxos.

## 🧮 O Motor Estocástico
O peso definitivo de um canal não é medido por quantas vezes ele foi o último clique, mas sim pela probabilidade de conversão do sistema caso esse canal deixasse de existir (Efeito de Remoção). As conversões reais são então redistribuídas proporcionalmente à influência matemática de cada nó da rede.

## 📊 Visualização e Impacto
Os resultados consolidados foram exportados e conectados ao **Looker Studio**, gerando um painel interativo que contrasta o modelo tradicional com o modelo probabilístico. Essa visão permite que a equipe de Growth remaneje o orçamento de aquisição de leads com base em dados acionáveis, reduzindo o CAC global.

---
*Este projeto demonstra a capacidade de transformar grandes volumes de dados brutos em informações precisas e acionáveis, automatizando pipelines de dados e documentando componentes arquiteturais de ponta a ponta.*
