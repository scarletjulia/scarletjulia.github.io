# Reliable Data Engineering — Scarlet Júlia

[![Reliable data pipeline demo](https://github.com/scarletjulia/scarletjulia.github.io/actions/workflows/reliable-data-pipeline-demo.yml/badge.svg)](https://github.com/scarletjulia/scarletjulia.github.io/actions/workflows/reliable-data-pipeline-demo.yml)

Código-fonte da biblioteca técnica publicada em [scarletjulia.github.io](https://scarletjulia.github.io/).

O site reúne artigos e estudos de caso sobre sistemas de dados que podem ser auditados, reprocessados e usados com confiança.

## Pilares editoriais

- **Reliable Data Engineering:** contratos, idempotência, lineage, observabilidade e reconciliação;
- **Data Pipelines at Scale:** PySpark, SQL, batch, incremental, APIs e CDC;
- **Analytics Engineering:** modelagem dimensional, marts, métricas e camadas RAW, Trusted e Curated.

## Conteúdo em destaque

- [Fontes heterogêneas: projetando um pipeline de dados confiável](_posts/2026-08-08-integrando-fontes-heterogeneas-em-um-pipeline-de-dados.md)
- [Idempotência em pipelines: como reprocessar sem duplicar dados](_posts/2026-08-08-idempotencia-em-pipelines-de-dados.md)
- [Pipeline de dados para previsão de preços de carros usados](_posts/2023-07-23-Projetando-Preços-de-Carros-Usados.md)

## Artigo + evidência

O diretório [reliable-data-pipeline-demo](labs/reliable-data-pipeline-demo/) transforma os conceitos dos artigos em uma implementação executável.

Ele demonstra:

- identificação de lote por checksum;
- carga idempotente por chave de negócio;
- atualização somente da versão mais recente;
- avanço transacional do watermark;
- quarentena de registros inválidos;
- testes de reprocessamento e reconciliação.

Os testes usam somente a biblioteca padrão do Python e são executados automaticamente pelo GitHub Actions.

## Estrutura do repositório

```text
├── _posts/                         # artigos técnicos
├── _layouts/ e _includes/          # apresentação Jekyll
├── assets/                         # estilos e imagens locais
├── labs/
│   └── reliable-data-pipeline-demo # implementação de referência
├── biblioteca.md                   # clusters temáticos
└── _config.yml                     # configuração e SEO
```

## Executar o site localmente

Pré-requisitos: Ruby, Bundler e Jekyll.

```bash
bundle install
bundle exec jekyll serve
```

O GitHub Pages compila e publica a branch `main` automaticamente.

## Autoria

Conteúdo e implementações por [Scarlet Júlia](https://github.com/scarletjulia).

O site utiliza uma versão personalizada do tema Jekyll Sleek, originalmente criado por Jan Czizikow e distribuído sob licença MIT.
