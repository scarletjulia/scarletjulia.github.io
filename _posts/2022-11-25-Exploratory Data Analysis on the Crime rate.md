---
layout: post
title: "Da ocorrência ao indicador: dados de crimes de São Francisco"
featured-img: object_detection
summary: "Modelagem de 150 mil ocorrências em fatos, dimensões e indicadores temporais e geográficos."
categories: [Analytics Engineering, Modelagem Dimensional, Python, Qualidade de Dados, Geodados]
---

Uma análise confiável de segurança pública depende de uma base consistente: identificadores únicos, datas válidas, categorias padronizadas e coordenadas dentro da região esperada. Neste estudo, preparei **150.500 ocorrências e 13 colunas** para responder perguntas sobre categoria, distrito, dia da semana, resolução e distribuição geográfica dos incidentes em São Francisco.

### Entendendo o esquema

O conjunto contém os seguintes campos principais:

| Campo | Papel no conjunto de dados |
| --- | --- |
| `IncidntNum` | identificador do incidente |
| `Category` e `Descript` | classificação geral e descrição detalhada |
| `Date`, `Time` e `DayOfWeek` | dimensões temporais |
| `PdDistrict` | distrito policial |
| `Resolution` | desfecho registrado |
| `Address` | endereço informado |
| `X`, `Y` e `Location` | representação geográfica |
| `PdId` | identificador atribuído pelo departamento de polícia |

Esse inventário funciona como o início de um contrato de dados. Antes de agregar, eu validaria unicidade, tipos, datas, categorias desconhecidas e limites de latitude e longitude. Também verificaria se `DayOfWeek` corresponde à data, evitando manter duas versões conflitantes da mesma informação.

### Preparação da camada analítica

As transformações podem ser organizadas em um fluxo simples e reproduzível:

{% highlight python %}
required = [
    "IncidntNum", "Category", "Date", "Time",
    "PdDistrict", "Resolution", "X", "Y"
]

missing = set(required) - set(df.columns)
if missing:
    raise ValueError(f"Colunas obrigatórias ausentes: {sorted(missing)}")

df["occurred_at"] = pd.to_datetime(
    df["Date"] + " " + df["Time"],
    errors="coerce"
)

df["Category"] = df["Category"].str.strip().str.upper()
df["PdDistrict"] = df["PdDistrict"].str.strip().str.upper()
{% endhighlight %}

Na sequência, uma tabela fato de ocorrências poderia se relacionar a dimensões de tempo, categoria e distrito. Isso evita repetir atributos descritivos e facilita o consumo por dashboards.

### Modelo dimensional

A granularidade de `fct_ocorrencia` seria **uma linha por incidente registrado**. As dimensões compartilhadas manteriam descrições consistentes entre dashboards:

- `dim_tempo`: data, dia da semana, mês, trimestre e ano;
- `dim_categoria_crime`: categoria e descrição padronizadas;
- `dim_distrito_policial`: código e nome do distrito;
- `dim_resolucao`: situação e agrupamento do desfecho;
- `dim_localizacao`: endereço e coordenadas validadas.

Sobre esse modelo, marts específicos poderiam publicar ocorrências por dia, distrito e categoria. Métricas como `total_ocorrencias` e `percentual_resolvido` precisariam de definição explícita, período de cobertura e data da última atualização.

### Indicadores publicados

`LARCENY/THEFT` foi a categoria mais frequente, com **40.409 ocorrências**, seguida por `OTHER OFFENSES`, com **19.599**, e `NON-CRIMINAL`, com **17.866**.

![Categorias mais frequentes](https://user-images.githubusercontent.com/114709169/204068253-cf5ca369-fd7d-4959-8361-43fc87c7f8db.png)

Por distrito policial, `SOUTHERN` concentrou **28.445 registros**, seguido por `NORTHERN`, com **20.100**, e `MISSION`, com **19.503**.

![Ocorrências por distrito policial](https://user-images.githubusercontent.com/114709169/204068273-bf100813-73cf-4ec9-9da9-70cdb8c60915.png)

O cruzamento entre categoria e distrito mostra que o mesmo indicador geral pode esconder perfis locais distintos. Em `TENDERLOIN`, por exemplo, `LARCENY/THEFT` aparece com 1.825 ocorrências, `NON-CRIMINAL` com 1.379 e `OTHER OFFENSES` com 1.237.

![Categorias por distrito](https://user-images.githubusercontent.com/114709169/204068342-6b19bba0-6825-43a6-94d3-b727e37dcfe2.png)

A dimensão temporal permite comparar categorias por dia da semana. `LARCENY/THEFT` registrou 6.477 ocorrências na sexta-feira, 6.384 no sábado e 5.538 na quinta-feira.

![Ocorrências por dia da semana](https://user-images.githubusercontent.com/114709169/204068386-88f0a78e-84f9-4440-a38a-ecc6c993f099.png)

Por fim, as coordenadas permitem construir mapas de densidade. Antes dessa etapa, pontos ausentes ou fora dos limites de São Francisco devem ser isolados para não distorcer a visualização.

![Densidade geográfica das ocorrências](https://user-images.githubusercontent.com/114709169/204068442-d5f2070b-57d8-45f8-9756-70f929ef2702.png)

### Cuidados de interpretação

Contagem de registros não é sinônimo de taxa de criminalidade. Para comparar regiões de forma justa, seria necessário incluir população, área, fluxo de pessoas e mudanças no processo de registro. Da mesma forma, uma ocorrência não resolvida no conjunto pode representar atraso de atualização, e não necessariamente ausência de ação.

Essas limitações devem acompanhar a tabela ou o dashboard como metadados. Um consumidor precisa saber o período de cobertura, a data da última atualização e as regras aplicadas aos registros.

### Evolução para um pipeline recorrente

Eu implementaria a ingestão incremental por data de atualização, mantendo três camadas:

1. **Raw:** cópia imutável da fonte;
2. **Trusted:** datas, categorias e coordenadas validadas, com duplicidades tratadas;
3. **Curated:** agregações por tempo, categoria e distrito, prontas para visualização.

Testes automáticos acompanhariam volume, unicidade de IDs, percentual de nulos e limites geográficos. A publicação usaria uma chave composta ou estratégia de *upsert* para que reprocessamentos não duplicassem incidentes.

### Tecnologias

Python, Pandas, NumPy, Matplotlib, Plotly e Folium foram utilizados na exploração e visualização. O estudo tomou como referência o artigo [San Francisco Crime Analysis with Data Science](https://thecleverprogrammer.com/2020/05/26/san-francisco-crime-analysis-with-data-science/).

### Aprendizados

O maior ganho veio de separar a pergunta analítica da preparação do dado. Quando esquema, granularidade e regras de qualidade estão explícitos, os mesmos registros podem alimentar mapas, séries temporais e indicadores sem criar uma transformação diferente para cada gráfico.
