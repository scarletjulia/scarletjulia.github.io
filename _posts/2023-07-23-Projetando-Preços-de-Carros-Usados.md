---
layout: post
title: "Pipeline de dados para previsão de preços de carros usados"
featured-img: carros_usados
summary: "Do diagnóstico de encoding à preparação de uma camada confiável para análises e modelos de regressão."
categories: [Engenharia de Dados, ETL, Python, Qualidade de Dados, Machine Learning]
---

Este projeto nasceu de um desafio de Ciência de Dados da Indicium, concluído em sete dias. Meu objetivo foi analisar anúncios de veículos usados e construir uma base confiável para responder perguntas de negócio e treinar modelos de regressão.

O [notebook completo](https://github.com/scarletjulia/Lighthouse_Indicium/blob/main/LH_CD_SCARLET_JULIA.ipynb) registra a análise e os tratamentos realizados. Aqui, apresento o trabalho com foco no fluxo do dado: leitura, validação, transformação e entrega para o modelo.

![Pátio de uma concessionária de veículos usados]({{ '/assets/img/posts/carros-usados/acervo-concessionaria.jpg' | relative_url }})

*Imagem: Davidrice557, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:UK_Car_Dealers.jpg), disponibilizada sob [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.pt-br). As visualizações analíticas abaixo foram exportadas do [notebook público do projeto](https://github.com/scarletjulia/Lighthouse_Indicium) e estão versionadas neste repositório.*

### O desafio começa na ingestão

Os dados chegaram em dois arquivos:

- treino: **29.584 registros**, incluindo a variável `preco`;
- teste: **9.862 registros**, sem a variável-alvo.

Apesar da extensão `.csv`, os arquivos usavam tabulação como separador e codificação UTF-16. Detectar essas características antes da leitura evita colunas corrompidas e caracteres inválidos.

{% highlight python %}
def detect_encoding(file_path):
    with open(file_path, "rb") as file:
        return chardet.detect(file.read())["encoding"]

treino = pd.read_csv(
    "cars_train.csv",
    delimiter="\t",
    encoding="utf-16",
)

teste = pd.read_csv(
    "cars_test.csv",
    delimiter="\t",
    encoding="utf-16",
)
{% endhighlight %}

Em produção, encoding, delimitador, colunas obrigatórias e tipos fariam parte do contrato da fonte. Uma falha nesses pontos interromperia o processamento antes que um dado incorreto chegasse às tabelas de consumo.

### Perfil e qualidade da base

A inspeção inicial revelou diferenças de completude. `num_fotos`, por exemplo, tinha 29.407 valores preenchidos no treino, enquanto `veiculo_alienado` não possuía valor válido. Também havia forte assimetria em `preco`, que variava de aproximadamente R$ 9,9 mil a R$ 1,36 milhão.

As principais regras de qualidade para esse conjunto são:

- validar anos de fabricação e modelo;
- rejeitar hodômetros negativos ou incompatíveis;
- padronizar categorias, marcas e estados;
- separar ausência real de “não se aplica”;
- garantir que treino e teste usem o mesmo esquema de atributos;
- impedir que a variável-alvo participe das transformações de entrada.

Uma coluna totalmente vazia não deve ser preenchida automaticamente. Primeiro é preciso verificar a documentação da fonte; caso não haja informação recuperável, a decisão de removê-la deve ficar registrada.

### Transformações reproduzíveis

No notebook, treino e teste foram unidos para aplicar transformações consistentes, mantendo uma coluna de origem para separá-los novamente. Variáveis categóricas foram codificadas e valores ausentes tratados antes do treinamento. Em um fluxo produtivo, transformações que aprendem estatísticas ou vocabulários devem ser ajustadas somente no treino e depois aplicadas ao teste, evitando vazamento de informação.

Uma versão produtiva encapsularia essas etapas em funções ou em um pipeline versionado, evitando diferenças entre os dados usados no treinamento e os recebidos na inferência.

```text
arquivos recebidos
    -> validação de formato e esquema
    -> normalização de tipos e categorias
    -> regras de qualidade
    -> atributos versionados
    -> treino / inferência
```

### Perguntas de negócio

Para carros de marcas populares, São Paulo apresentou a maior oferta e um preço médio relativamente alto. No índice usado no estudo, o estado alcançou `0,739091`, combinando volume de anúncios e preço.

![Quantidade de carros populares e preço médio por estado]({{ '/assets/img/posts/carros-usados/carros-populares-por-estado.png' | relative_url }})

São Paulo também apresentou oferta relevante de picapes automáticas, com 1.712 unidades e preço médio aproximado de R$ 188,4 mil. Para interpretar “melhor estado para comprar”, porém, preço, oferta e variedade precisam ser ponderados de acordo com a necessidade do consumidor.

![Distribuição de preços de picapes automáticas por estado]({{ '/assets/img/posts/carros-usados/preco-picapes-automaticas.png' | relative_url }})

Minas Gerais ficou entre os estados com maior volume de veículos ainda cobertos por garantia de fábrica. O dado descreve os anúncios disponíveis; sozinho, ele não demonstra preferência de compra dos consumidores.

### Hipóteses avaliadas

O ano de fabricação apresentou relação positiva e estatisticamente significativa com o preço, mas explicou apenas **5,7%** de sua variabilidade quando analisado isoladamente.

Veículos com revisão em concessionária tiveram preço mediano de R$ 136,21 mil, contra R$ 105,42 mil no grupo sem esse registro. Para revisões dentro da agenda, as medianas foram R$ 134,59 mil e R$ 109,73 mil. Essas diferenças são associações observadas; não provam que a revisão, por si só, causou o aumento.

![Impacto das revisões em concessionária no preço]({{ '/assets/img/posts/carros-usados/revisoes-concessionaria-preco.png' | relative_url }})

![Impacto das revisões feitas dentro da agenda no preço]({{ '/assets/img/posts/carros-usados/revisoes-agenda-preco.png' | relative_url }})

A hipótese de que mais fotos indicariam preço maior não se confirmou: anúncios com até a média de fotos tiveram mediana de R$ 117,74 mil, contra R$ 107,15 mil nos anúncios acima da média.

![Relação entre o número de fotos e o preço do veículo]({{ '/assets/img/posts/carros-usados/numero-fotos-preco.png' | relative_url }})

### Camada de consumo para os modelos

Comparei diferentes regressores com validação cruzada. Entre os *baselines*, o LightGBM obteve o melhor resultado médio:

| Modelo | RMSE | MAE | R² |
| --- | ---: | ---: | ---: |
| Regressão Linear | 71.510 | 51.897 | 0,233 |
| Gradient Boosting | 65.766 | 47.402 | 0,351 |
| XGBoost | 65.132 | 46.442 | 0,363 |
| LightGBM | **64.112** | **45.887** | **0,383** |

Na etapa seguinte, apliquei transformação logarítmica ao preço, dividi treino e validação e treinei o LightGBM. O ponto importante para Engenharia de Dados é garantir que o mesmo conjunto de atributos, nomes de colunas e tratamentos seja reproduzido na inferência.

### Como eu evoluiria o projeto

Uma arquitetura de produção teria:

1. **Raw:** arquivos originais versionados por data de recebimento;
2. **Trusted:** esquema validado, categorias normalizadas e registros inválidos separados;
3. **Feature:** atributos calculados com a mesma versão para treino e inferência;
4. **Serving:** previsões acompanhadas da versão do modelo e do instante de processamento.

Também monitoraria mudança de esquema, volume, nulos, distribuição de preço e *drift* dos principais atributos. A execução seria idempotente: processar novamente o mesmo arquivo não criaria anúncios duplicados.

### Aprendizados

O projeto mostrou que uma boa previsão depende de decisões anteriores ao treinamento. Reconhecer o formato real do arquivo, documentar ausências, manter transformações consistentes e separar associação de causalidade são práticas que tornam o resultado mais confiável e sustentável.
