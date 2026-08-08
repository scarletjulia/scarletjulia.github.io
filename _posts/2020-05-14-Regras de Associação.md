---
layout: post
title: "Pipeline distribuído para minerar padrões de crimes na Inglaterra"
featured-img: bandeira_inglaterra
summary: "Transformação de 124 mil ocorrências em modelos analíticos e padrões frequentes com SparkR e FP-Growth."
description: "Pipeline distribuído com SparkR e FP-Growth para transformar 124 mil ocorrências em modelos analíticos e padrões frequentes."
series: "Data Pipelines at Scale"
last_modified_at: 2026-08-08
categories: [Analytics Engineering, Transformação de Dados, Spark, Qualidade de Dados, Mineração de Dados]
---

Como transformar milhares de registros públicos em informação analisável sem perder contexto? Neste estudo, trabalhei com ocorrências da polícia do Reino Unido e organizei um fluxo de ingestão, limpeza e processamento distribuído para descobrir padrões frequentes nos dados.

O projeto analisou registros de **julho de 2015 a junho de 2018** referentes a Swindon, no condado de Wiltshire. A fonte foi o portal de [dados abertos da polícia do Reino Unido](https://data.police.uk/data/).

### Fonte e estrutura dos dados

Os arquivos continham informações como identificador, mês da ocorrência, força policial responsável, longitude, latitude, localização, tipo de crime e última ação registrada.

![Mapa da região analisada](https://dl.dropbox.com/s/0938ovd3ra8u4fa/mapa.png?dl=0)

![Amostra do conjunto de dados](https://dl.dropbox.com/s/8ko5co5c209v4kt/dataSet.png?dl=0)

Para um pipeline recorrente, eu registraria para cada arquivo:

- período de referência e data de ingestão;
- origem e checksum do objeto recebido;
- esquema esperado e versão do esquema;
- contagem de linhas aceitas, rejeitadas e deduplicadas.

Esse controle evita reprocessamentos silenciosos e permite rastrear exatamente qual fonte produziu cada resultado.

### Limpeza com regra de negócio

Durante o *data wrangling*, identifiquei valores ausentes na coluna de última ação. Os registros de comportamento antissocial foram excluídos da etapa de associação porque a ausência não permitia concluir se o caso estava ou não resolvido.

![Registros de comportamento antissocial](https://dl.dropbox.com/s/arrfn8idl0s1brx/qtd_comportamento_anti_social.png?dl=0)

Essa decisão precisa ser documentada: excluir registros melhora a consistência do conjunto usado pelo algoritmo, mas também altera sua cobertura. Em produção, eu manteria os registros na camada bruta, marcaria o motivo da rejeição na camada tratada e publicaria uma métrica sobre a perda de dados.

Após a filtragem, a base usada no processamento ficou com **8 colunas e 124.185 registros**.

![Resumo estatístico após o tratamento](https://dl.dropbox.com/s/bn8g5l7urhyq8lk/describe.png?dl=0)

### Por que FP-Growth

Regras de associação procuram combinações de atributos que aparecem juntas com frequência. Duas métricas orientam o processo:

- **suporte:** proporção de registros em que a combinação aparece;
- **confiança:** frequência com que o consequente aparece quando o antecedente está presente.

O Apriori gera e testa conjuntos candidatos em várias passagens pela base. O FP-Growth reduz esse custo ao representar os padrões frequentes em uma estrutura compacta, a FP-Tree. Essa característica o torna interessante quando o volume e o número de combinações aumentam.

### Processamento distribuído

Utilizei **R**, **SparkR** e o algoritmo **FP-Growth**, com confiança mínima de `0,70` e suporte mínimo de `0,01`. O Spark distribui o processamento, enquanto o FP-Growth evita enumerar todas as combinações possíveis.

Um fluxo produtivo para esse processamento poderia ser organizado assim:

```text
Arquivos mensais -> validação de esquema -> camada bruta
                 -> padronização e qualidade -> camada tratada
                 -> FP-Growth no Spark -> regras publicadas
```

Os parâmetros de suporte e confiança devem ser versionados junto ao resultado. Sem isso, duas execuções sobre os mesmos dados podem gerar conjuntos de regras diferentes sem que a causa fique evidente.

![Distribuição geográfica das ocorrências](https://dl.dropbox.com/s/mcyl9lggekvsueh/mapa_crimes.png?dl=0)

### Da transformação ao produto analítico

O resultado do processamento pode ser publicado em dois modelos complementares:

| Modelo | Granularidade | Uso principal |
| --- | --- | --- |
| `fct_ocorrencia_criminal` | uma ocorrência registrada | análises por período, local e categoria |
| `mart_regras_associacao` | uma regra por período e conjunto de parâmetros | comparação de suporte, confiança e estabilidade |

Dimensões de tempo, localização e categoria permitem reaproveitar as mesmas definições em diferentes análises. No `mart_regras_associacao`, eu manteria também `min_support`, `min_confidence`, versão do algoritmo e data de processamento. Assim, a regra deixa de ser apenas uma saída de notebook e passa a ser um produto analítico comparável ao longo do tempo.

### Observabilidade e evolução

Para tornar o pipeline confiável, eu acompanharia:

- atraso entre o mês da ocorrência e sua disponibilidade;
- percentual de coordenadas e categorias nulas;
- duplicidade do identificador da ocorrência;
- volume por mês e por tipo de crime;
- quantidade de regras geradas e variação em relação à execução anterior.

Também particionaria os dados por ano e mês, preservaria o arquivo original e tornaria o processamento idempotente. Dessa forma, reexecutar um período corrigido substituiria apenas a partição correspondente, sem duplicar o histórico.

### Aprendizados

O algoritmo é apenas uma parte da solução. A confiabilidade das regras depende da origem, do tratamento dos nulos, da rastreabilidade dos filtros e da capacidade de repetir o processamento. Esse é o ponto em que mineração de dados e Engenharia de Dados se encontram.
