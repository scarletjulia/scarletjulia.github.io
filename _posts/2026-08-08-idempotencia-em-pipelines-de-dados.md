---
layout: post
title: "Idempotência em pipelines: como reprocessar sem duplicar dados"
featured-img: python
summary: "Estratégias práticas para repetir uma carga após falhas sem perder registros, duplicar fatos ou avançar o watermark cedo demais."
description: "Guia prático de idempotência em pipelines com checksum, chaves de negócio, upsert, watermark transacional, quarentena e testes."
series: "Reliable Data Pipelines"
date: 2026-08-08 12:00:00 -0300
last_modified_at: 2026-08-08
categories: [Reliable Data Engineering, Data Pipelines, SQL, Qualidade de Dados, Python]
---

Uma execução falhou depois de gravar metade dos registros. O orquestrador iniciou uma nova tentativa. O que acontece agora?

Se a resposta for “depende de onde parou”, o pipeline ainda não possui uma estratégia clara de idempotência. Em sistemas de dados, falhas e novas tentativas são normais. A solução precisa produzir o mesmo estado final mesmo quando o mesmo lote é processado mais de uma vez.

<div class="evidence-callout">
  <p><strong>Execute o exemplo:</strong> o repositório contém uma <a href="https://github.com/scarletjulia/scarletjulia.github.io/tree/main/labs/reliable-data-pipeline-demo">demonstração em Python e SQLite</a> que carrega o mesmo arquivo duas vezes, atualiza registros por versão, isola linhas inválidas e só avança o watermark depois do commit.</p>
</div>

### O que idempotência significa

Uma operação idempotente pode ser repetida sem alterar o resultado depois da primeira aplicação bem-sucedida. Para um pipeline, isso não significa apenas “não inserir duas linhas iguais”. O estado inteiro precisa permanecer correto:

- fatos não podem ser duplicados;
- atualizações mais antigas não podem sobrescrever versões novas;
- registros rejeitados precisam continuar rastreáveis;
- o watermark não pode avançar antes da publicação;
- métricas agregadas devem reconciliar com a camada detalhada.

Podemos representar a propriedade assim:

```text
processar(lote, estado) = novo_estado
processar(lote, novo_estado) = novo_estado
```

O segundo processamento pode registrar que o lote já foi visto, mas não deve mudar o resultado de negócio.

### Cenário de falha

Considere uma carga incremental de pedidos:

```text
1. extrair registros desde o último watermark
2. validar o lote
3. gravar pedidos
4. atualizar agregações
5. avançar o watermark
```

Se o processo falhar entre os passos 3 e 5, uma nova tentativa extrairá parte dos mesmos pedidos. Um `INSERT` simples criará duplicidades. Se o watermark avançar antes do passo 3, a falha pode causar algo pior: perda silenciosa de dados.

O desenho precisa tratar gravação e progresso como uma única unidade lógica.

### Primeira defesa: identificar o lote

Para arquivos, uso um checksum do conteúdo em vez de confiar apenas no nome. Dois arquivos com nomes diferentes e conteúdo igual representam o mesmo lote; um arquivo substituído com o mesmo nome representa outro conteúdo.

{% highlight python %}
from hashlib import sha256

def file_checksum(path):
    digest = sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
{% endhighlight %}

Uma tabela de controle registra checksum, origem, status, quantidade de linhas e horário. O lote só recebe status `succeeded` depois que todas as alterações necessárias foram confirmadas.

| `batch_checksum` | `status` | `accepted_rows` | `rejected_rows` |
| --- | --- | ---: | ---: |
| `a41f...` | `succeeded` | 2.481 | 7 |

Ao receber novamente um checksum já concluído, o pipeline pode encerrar sem regravar os dados.

### Segunda defesa: escolher a chave correta

O checksum protege o lote, mas não resolve registros repetidos entre lotes diferentes. Para isso, precisamos da chave de negócio.

Em itens de pedido, uma chave possível é:

```text
order_id + order_item_id
```

Essa combinação precisa de uma restrição de unicidade no destino. Sem a restrição, a deduplicação existe apenas como intenção no código e pode ser violada por outra rotina.

{% highlight sql %}
CREATE TABLE orders (
    order_id       TEXT NOT NULL,
    order_item_id  TEXT NOT NULL,
    product_id     TEXT NOT NULL,
    quantity       INTEGER NOT NULL,
    unit_price     DECIMAL(18, 2) NOT NULL,
    updated_at     TIMESTAMP NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);
{% endhighlight %}

### Upsert com controle de versão

Quando a origem permite alterações, ignorar todas as chaves existentes também está errado. O destino deve aceitar apenas uma versão mais recente.

{% highlight sql %}
MERGE INTO curated.orders AS target
USING staging.orders_batch AS source
ON  target.order_id = source.order_id
AND target.order_item_id = source.order_item_id

WHEN MATCHED AND source.updated_at > target.updated_at THEN
  UPDATE SET
    product_id = source.product_id,
    quantity = source.quantity,
    unit_price = source.unit_price,
    updated_at = source.updated_at

WHEN NOT MATCHED THEN
  INSERT (
    order_id,
    order_item_id,
    product_id,
    quantity,
    unit_price,
    updated_at
  )
  VALUES (
    source.order_id,
    source.order_item_id,
    source.product_id,
    source.quantity,
    source.unit_price,
    source.updated_at
  );
{% endhighlight %}

Essa condição impede que uma entrega atrasada com versão antiga desfaça uma correção já publicada.

### O watermark faz parte da transação

O watermark representa até onde a origem foi processada com sucesso. Ele não deve significar “até onde consegui extrair”. Deve significar “até onde publiquei e validei”.

```text
BEGIN
  carregar staging
  validar contrato
  aplicar MERGE
  reconciliar contagens
  atualizar watermark
COMMIT
```

Se qualquer etapa falhar, o `ROLLBACK` preserva o watermark anterior. A nova tentativa pode reler a mesma janela com segurança porque a chave e o `MERGE` protegem o destino.

Quando origem e destino não compartilham a mesma transação, uso publicação em duas fases: o pipeline grava em uma área temporária, valida o resultado e troca o ponteiro ou partição visível apenas no final.

### Janela de sobreposição

Eventos atrasados podem chegar com `updated_at` anterior ao último watermark. Uma prática comum é reler uma pequena janela:

```text
watermark_start = last_successful_watermark - overlap
watermark_end   = início_da_execução
```

A sobreposição aumenta registros repetidos por desenho. Por isso, ela só é segura quando o destino é idempotente. O tamanho da janela deve ser definido a partir do atraso observado, não por um número arbitrário.

### Dados inválidos não desaparecem

Uma linha com quantidade zero ou preço inválido não deve ser inserida na tabela confiável, mas também não deveria ser descartada silenciosamente. Envio o registro para uma tabela de quarentena contendo:

- identificador e checksum do lote;
- número da linha ou chave da origem;
- regra violada;
- conteúdo recebido;
- horário do processamento.

Isso separa duas perguntas diferentes: “o dado pode ser publicado?” e “o dado pode ser investigado?”.

### Testes que provam idempotência

Um teste útil precisa executar o fluxo, e não apenas testar uma função isolada:

1. carregar o lote pela primeira vez;
2. registrar contagem e soma das métricas;
3. carregar exatamente o mesmo lote outra vez;
4. confirmar que contagem, soma e watermark não mudaram;
5. carregar uma versão mais recente de uma chave existente;
6. confirmar que apenas essa chave foi atualizada;
7. carregar uma versão antiga e confirmar que ela foi ignorada.

{% highlight python %}
first = load_csv(connection, "orders.csv")
second = load_csv(connection, "orders.csv")

assert first.skipped is False
assert second.skipped is True
assert count_orders(connection) == 2
assert total_revenue_cents(connection) == 17_980
{% endhighlight %}

Além do estado final, valido a tabela de controle: um único lote concluído, nenhuma execução presa em `processing` e watermark coerente com a maior versão publicada.

### Métricas operacionais

Em produção, eu acompanharia:

- lotes repetidos identificados por checksum;
- registros inseridos, atualizados, ignorados e rejeitados;
- diferença entre linhas extraídas e linhas publicadas;
- idade do watermark;
- duração e número de tentativas por lote;
- divergência entre camada detalhada e agregações.

Uma mudança súbita na quantidade de registros ignorados pode indicar reenvio da origem, chave mal definida ou atualização fora de ordem.

### Antipadrões comuns

**Apagar tudo e recarregar.** Pode funcionar para tabelas pequenas, mas aumenta custo, tempo sem disponibilidade e risco operacional.

**Usar `SELECT DISTINCT` no final.** Remove linhas idênticas, mas não decide qual versão deve permanecer quando os valores são diferentes.

**Confiar apenas no nome do arquivo.** O nome pode mudar sem mudança de conteúdo — ou permanecer igual depois de uma correção.

**Avançar o watermark após a extração.** Uma falha durante a escrita deixa uma faixa de dados marcada como concluída sem ter sido publicada.

**Tratar rejeitado como perdido.** Sem quarentena, não existe reconciliação nem caminho de correção.

### Checklist de projeto

Antes de considerar uma carga reprocessável, respondo:

- qual é a identidade do lote?
- qual é a chave de negócio de cada registro?
- como escolho a versão vencedora?
- a unicidade é garantida no destino?
- quando o watermark avança?
- o que acontece com registros inválidos?
- como reconcilio origem e destino?
- quais métricas provam que a nova tentativa não mudou o resultado?

### Conclusão

Idempotência não é um `dropDuplicates` adicionado no fim do pipeline. Ela nasce da combinação entre identidade do lote, chave de negócio, controle de versão, publicação atômica, watermark e testes de reconciliação.

Quando essas decisões estão explícitas, uma nova tentativa deixa de ser um risco e passa a ser parte normal da operação.
