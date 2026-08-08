---
layout: post
title: "Fontes heterogêneas: projetando um pipeline de dados confiável"
featured-img: python
summary: "Integração de CSV, API e PostgreSQL até um mart de vendas com métricas documentadas e testáveis."
categories: [Analytics Engineering, ELT, PySpark, SQL, Qualidade de Dados]
---

Integrar dados não é apenas conectar sistemas. Cada fonte possui seu próprio ritmo, formato, semântica e forma de falhar. Um arquivo CSV pode mudar o nome de uma coluna; uma API pode paginar ou limitar requisições; um banco transacional pode atualizar registros já processados.

Neste artigo, projeto um pipeline para unificar três fontes heterogêneas de uma empresa de varejo:

- **CSV:** cadastro de produtos enviado diariamente;
- **API REST/JSON:** cotações de moedas atualizadas a cada hora;
- **PostgreSQL:** pedidos e itens registrados continuamente.

O objetivo é publicar uma tabela analítica de vendas com valores convertidos para reais, pronta para dashboards e análises.

### Começando pelo contrato de saída

Antes de escolher ferramentas, defino a granularidade: **uma linha por item de pedido**. A tabela final deve conter:

| Campo | Tipo | Regra |
| --- | --- | --- |
| `order_id` | string | obrigatório |
| `order_item_id` | string | único dentro do pedido |
| `order_timestamp` | timestamp UTC | obrigatório |
| `product_id` | string | deve existir no cadastro de produtos |
| `quantity` | inteiro | maior que zero |
| `currency` | string | código ISO em maiúsculas |
| `unit_price` | decimal(18,2) | maior ou igual a zero |
| `exchange_rate_brl` | decimal(18,6) | cotação válida para a data |
| `gross_amount_brl` | decimal(18,2) | quantidade × preço × cotação |
| `updated_at` | timestamp UTC | versão mais recente recebida da origem |
| `processed_at` | timestamp UTC | preenchido pelo pipeline |

Definir esse contrato primeiro evita que a implementação seja guiada apenas pelo formato das fontes. A tabela de consumo representa uma regra de negócio, não uma cópia do sistema de origem.

### Arquitetura em camadas

Organizo o fluxo em três camadas com responsabilidades distintas:

```text
CSV -----------+
API JSON ------+--> RAW --> TRUSTED --> CURATED --> BI / análises
PostgreSQL ----+      |          |           |
                    original   padronizado  regra de negócio
```

- **Raw:** preserva exatamente o que foi recebido, com metadados de ingestão;
- **Trusted:** aplica tipos, deduplicação e regras de qualidade por domínio;
- **Curated:** combina as fontes e publica métricas de negócio.

Essa separação permite corrigir uma transformação sem consultar novamente a origem. Também facilita auditoria: sempre é possível relacionar um registro publicado ao lote que o produziu.

### Ingestão respeitando cada fonte

#### Arquivo CSV

Arquivos são ingeridos de forma imutável. O caminho inclui a data de referência e o identificador da execução:

```text
raw/products/reference_date=2026-08-08/run_id=8f3a/products.csv
```

Antes de aceitar o lote, valido encoding, delimitador, cabeçalho, tamanho mínimo e checksum. O checksum impede que o mesmo arquivo seja processado duas vezes com nomes diferentes.

#### API JSON

A API exige controle de paginação, *timeout*, tentativas com espera progressiva e respeito ao limite de chamadas. Além do conteúdo, armazeno status HTTP, horário da coleta e versão do endpoint.

{% highlight python %}
def fetch_page(session, url, params, timeout=30):
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    if "rates" not in payload or "base" not in payload:
        raise ValueError("Resposta fora do contrato esperado")

    return payload
{% endhighlight %}

Persistir a resposta antes de transformá-la é importante. Se a regra de conversão mudar, o dado original continua disponível para reprocessamento.

#### PostgreSQL

Para pedidos, uma extração completa a cada execução seria cara e aumentaria a pressão sobre o banco. Uso carga incremental por `updated_at`, com uma pequena janela de sobreposição para capturar atualizações atrasadas.

{% highlight sql %}
SELECT
    order_id,
    order_item_id,
    product_id,
    quantity,
    currency,
    unit_price,
    order_timestamp,
    updated_at
FROM order_items
WHERE updated_at >= :watermark_start
  AND updated_at <  :watermark_end;
{% endhighlight %}

O *watermark* só avança depois que o lote é validado e publicado. Se a execução falhar, o intervalo pode ser reprocessado sem perder registros.

### Padronização na camada Trusted

Na camada intermediária, cada fonte é tratada separadamente. Com PySpark, as regras principais podem ser expressas de forma declarativa:

{% highlight python %}
from pyspark.sql import Window, functions as F
from pyspark.sql.types import DecimalType, IntegerType

latest_version = Window.partitionBy(
    "order_id", "order_item_id"
).orderBy(F.col("updated_at").desc())

orders_normalized = (
    orders_raw
    .withColumn("product_id", F.trim("product_id"))
    .withColumn("currency", F.upper(F.trim("currency")))
    .withColumn("quantity", F.col("quantity").cast(IntegerType()))
    .withColumn("unit_price", F.col("unit_price").cast(DecimalType(18, 2)))
    .withColumn("order_timestamp", F.to_utc_timestamp("order_timestamp", "America/Sao_Paulo"))
)

orders_trusted = (
    orders_normalized
    .withColumn("version_rank", F.row_number().over(latest_version))
    .filter(F.col("version_rank") == 1)
    .drop("version_rank")
)
{% endhighlight %}

Registros que violam o contrato não desaparecem. Eles seguem para uma tabela de quarentena com a regra violada, o lote e o valor recebido. Isso permite corrigir a origem e medir a saúde do pipeline.

### Combinando as fontes

A tabela final nasce de duas junções: pedidos com produtos e pedidos com a cotação válida na data. Como cotações podem variar no tempo, não basta juntar apenas pelo código da moeda; é necessário considerar a data de vigência.

{% highlight python %}
sales_curated = (
    orders_trusted.alias("o")
    .join(
        products_trusted.alias("p"),
        F.col("o.product_id") == F.col("p.product_id"),
        "left",
    )
    .join(
        rates_trusted.alias("r"),
        (F.col("o.currency") == F.col("r.currency"))
        & (F.to_date("o.order_timestamp") == F.col("r.reference_date")),
        "left",
    )
    .withColumn(
        "gross_amount_brl",
        F.round(
            F.col("o.quantity")
            * F.col("o.unit_price")
            * F.col("r.exchange_rate_brl"),
            2,
        ),
    )
    .withColumn("processed_at", F.current_timestamp())
)
{% endhighlight %}

Uma cotação ausente é uma falha de completude, não um valor zero. O lote pode ser bloqueado ou publicado parcialmente conforme o acordo de nível de serviço, mas a decisão deve ser explícita e observável.

### Do dado integrado ao mart de vendas

A tabela `sales_curated` mantém a granularidade de item do pedido e funciona como base reutilizável. Para consumo de negócio, eu publicaria um mart diário com uma linha por **data, produto e moeda de origem**.

{% highlight sql %}
SELECT
    CAST(order_timestamp AS DATE) AS order_date,
    product_id,
    currency,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(quantity) AS units_sold,
    SUM(gross_amount_brl) AS gross_revenue_brl
FROM curated.sales
GROUP BY 1, 2, 3;
{% endhighlight %}

`gross_revenue_brl` teria uma definição única: soma de quantidade × preço unitário × cotação vigente, antes de descontos, cancelamentos e devoluções. Se o negócio precisar de receita líquida, ela deve ser publicada como outra métrica, com regras próprias — não como uma alteração silenciosa da métrica existente.

Testes de unicidade na chave do item, relacionamento com produtos e presença da cotação protegem o modelo base. No mart, uma reconciliação garante que a soma diária permaneça igual à camada detalhada para o mesmo conjunto de filtros.

### Idempotência e deduplicação

Um pipeline idempotente produz o mesmo estado final quando recebe o mesmo dado mais de uma vez. Para isso:

- o CSV é identificado por checksum;
- a resposta da API recebe uma chave composta por moeda e data de referência;
- os pedidos usam `order_id` + `order_item_id`, mantendo a versão mais recente por `updated_at`;
- a publicação usa `MERGE` ou sobrescrita controlada de partições.

Em uma tabela compatível com `MERGE`, como uma tabela Delta, a publicação pode seguir esta lógica:

{% highlight sql %}
MERGE INTO curated.sales AS target
USING staging.sales_batch AS source
ON  target.order_id = source.order_id
AND target.order_item_id = source.order_item_id
WHEN MATCHED AND source.updated_at > target.updated_at THEN
  UPDATE SET *
WHEN NOT MATCHED THEN
  INSERT *;
{% endhighlight %}

Assim, uma nova tentativa após falha não duplica vendas nem exige apagar todo o histórico.

### Qualidade e observabilidade

Eu acompanharia quatro grupos de métricas:

- **volume:** linhas recebidas, aceitas, atualizadas e rejeitadas;
- **qualidade:** nulos, duplicidades, produtos sem cadastro e moedas sem cotação;
- **tempo:** duração, atraso da fonte e tempo até disponibilização;
- **distribuição:** quantidade, preço e valor bruto comparados ao histórico recente.

Alguns testes bloqueiam a publicação, como ausência de colunas obrigatórias ou duplicidade da chave final. Outros geram alerta, como uma variação de volume acima do comportamento esperado.

### Evolução de esquema

Mudanças aditivas, como uma nova coluna opcional, podem ser aceitas e versionadas. Mudanças incompatíveis — renomear um campo, trocar seu tipo ou alterar sua unidade — devem falhar de forma clara. Aceitar qualquer esquema automaticamente transfere o problema para quem consome a tabela.

O contrato deve registrar proprietário, descrição, tipo, nulabilidade, classificação de dados sensíveis e política de compatibilidade. Quando uma mudança for necessária, produtor e consumidores precisam de uma janela de migração.

### Segurança e governança

Credenciais ficam em um gerenciador de segredos, nunca no código. A conta do pipeline recebe apenas as permissões necessárias: leitura nas origens e escrita nas tabelas sob sua responsabilidade. Logs não devem expor dados pessoais ou conteúdo completo das requisições.

No catálogo, cada tabela publicada informa origem, atualização, responsável, granularidade e regras de qualidade. Essa documentação reduz dependência de conhecimento informal e ajuda novos consumidores a usar o dado corretamente.

### Conclusão

Fontes heterogêneas exigem estratégias de ingestão diferentes, mas devem convergir para os mesmos princípios: contrato explícito, preservação do dado bruto, transformações reproduzíveis, idempotência e observabilidade.

O valor do pipeline não está apenas em mover CSV, JSON e linhas de banco. Está em entregar um conjunto de dados no qual outras pessoas possam confiar — e em conseguir explicar como cada registro chegou até lá.
