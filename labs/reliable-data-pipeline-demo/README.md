# Reliable Data Pipeline Demo

Demonstração executável dos princípios apresentados nos artigos da série **Reliable Data Pipelines**.

O exemplo usa apenas a biblioteca padrão do Python e SQLite para manter a execução simples. Em produção, os mesmos invariantes podem ser implementados com PostgreSQL, Delta Lake ou outro destino que ofereça unicidade e transações.

## O que o projeto demonstra

- identificação do lote por SHA-256;
- chave de negócio `order_id + order_item_id`;
- atualização apenas quando `updated_at` é mais recente;
- watermark atualizado na mesma transação da publicação;
- registros inválidos enviados para quarentena;
- nova execução do mesmo arquivo sem duplicação;
- testes de reconciliação e reprocessamento.

```text
CSV -> contrato e validação -> staging lógico
                              |-> orders confiável
                              |-> rejected_records
                              |-> pipeline_state
```

## Estrutura

```text
reliable-data-pipeline-demo/
├── pipeline.py
├── sample_data/
│   └── orders.csv
├── sql/
│   ├── mart_daily_sales.sql
│   └── quality_checks.sql
└── tests/
    └── test_pipeline.py
```

## Executar

Requer Python 3.10 ou superior.

```bash
python pipeline.py --input sample_data/orders.csv --database demo.db
python pipeline.py --input sample_data/orders.csv --database demo.db
```

Na segunda execução, `skipped` será `true` porque o checksum já foi concluído.

## Testar

```bash
python -m unittest discover -s tests -v
```

Os testes comprovam que:

1. executar o mesmo lote duas vezes mantém duas linhas no destino;
2. uma versão mais recente atualiza apenas a chave correspondente;
3. uma versão antiga não sobrescreve o registro atual;
4. uma linha inválida é preservada na quarentena;
5. o watermark representa a maior versão publicada.

## Decisões de projeto

Valores monetários são armazenados em centavos para evitar erros de ponto flutuante. Datas são normalizadas para UTC antes da comparação. A restrição `PRIMARY KEY` protege a unicidade no próprio destino, não apenas no código.

O exemplo é intencionalmente pequeno, mas trata falhas e reprocessamento como requisitos do desenho.
