---
layout: page
title: Biblioteca técnica
permalink: /biblioteca/
description: "Artigos de Scarlet Júlia organizados por Reliable Data Engineering, PySpark, SQL, qualidade e Analytics Engineering."
---

Esta biblioteca organiza os conteúdos por problema técnico, não apenas por data de publicação. Se você está chegando agora, comece pela série **Reliable Data Pipelines**.

<section class="knowledge-cluster" id="reliable-data-pipelines">
  <h2>Reliable Data Pipelines</h2>
  <p>Arquitetura e decisões para pipelines que podem falhar, ser reprocessados e ainda assim entregar dados corretos.</p>
  <ul class="knowledge-list">
  {% for post in site.posts %}
    {% if post.series == "Reliable Data Pipelines" %}
    <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> — {{ post.summary }}</li>
    {% endif %}
  {% endfor %}
  </ul>
</section>

<section class="knowledge-cluster" id="pyspark-sql">
  <h2>PySpark &amp; SQL</h2>
  <p>Processamento distribuído, transformação e estratégias para trabalhar com volume e fontes diversas.</p>
  <ul class="knowledge-list">
  {% for post in site.posts %}
    {% if post.series == "Data Pipelines at Scale" or post.categories contains "PySpark" or post.categories contains "SQL" %}
    <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> — {{ post.summary }}</li>
    {% endif %}
  {% endfor %}
  </ul>
</section>

<section class="knowledge-cluster" id="data-quality">
  <h2>Data Quality</h2>
  <p>Contratos, validações, reconciliação, quarentena e critérios para decidir quando um pipeline deve bloquear a publicação.</p>
  <ul class="knowledge-list">
  {% for post in site.posts %}
    {% if post.categories contains "Qualidade de Dados" %}
    <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> — {{ post.summary }}</li>
    {% endif %}
  {% endfor %}
  </ul>
</section>

<section class="knowledge-cluster" id="analytics-engineering">
  <h2>Analytics Engineering</h2>
  <p>Granularidade, fatos, dimensões, marts e métricas preparadas para análises e dashboards.</p>
  <ul class="knowledge-list">
  {% for post in site.posts %}
    {% if post.series == "Analytics Engineering na Prática" %}
    <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> — {{ post.summary }}</li>
    {% endif %}
  {% endfor %}
  </ul>
</section>

### Próximos temas da série

- Watermarks em pipelines incrementais;
- Data Contracts e evolução de schema;
- deduplicação com PySpark;
- tabelas de quarentena;
- testes que devem bloquear uma publicação;
- batch, CDC ou streaming;
- observabilidade e reconciliação;
- reprocessamento seguro.
