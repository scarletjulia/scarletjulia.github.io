---
#
# You don't need to edit this file, it's empty on purpose.
# Edit sleeks's default layout instead if you wanna make some changes
# See: https://jekyllrb.com/docs/themes/#overriding-theme-defaults
#
layout: default
title: Reliable Data Engineering - Scarlet Júlia
description: "Artigos e projetos sobre pipelines confiáveis, PySpark, SQL, qualidade de dados, observabilidade e Analytics Engineering."
---

<section class="analytics-intro" aria-labelledby="analytics-intro-title">
  <p class="analytics-kicker">RELIABLE DATA ENGINEERING</p>
  <h2 id="analytics-intro-title">Pipelines de dados confiáveis, do desenho à operação.</h2>
  <p class="analytics-intro__lead">Esta é minha biblioteca pública sobre sistemas de dados que podem ser reprocessados, auditados e usados com confiança. Cada conteúdo conecta arquitetura, código, qualidade e impacto para quem consome o dado.</p>

  <div class="analytics-pillars">
    <article class="analytics-pillar">
      <h3>Reliable Data Engineering</h3>
      <p>Contratos, idempotência, lineage, observabilidade, reconciliação e tratamento explícito de falhas.</p>
    </article>
    <article class="analytics-pillar">
      <h3>Data Pipelines at Scale</h3>
      <p>PySpark, SQL, batch, cargas incrementais, APIs, watermarks e estratégias de deduplicação.</p>
    </article>
    <article class="analytics-pillar">
      <h3>Analytics Engineering</h3>
      <p>Modelagem dimensional, marts, métricas documentadas e camadas RAW, Trusted e Curated.</p>
    </article>
  </div>

  <nav class="topic-links" aria-label="Principais temas da biblioteca">
    <a href="{{ '/biblioteca/#reliable-data-pipelines' | relative_url }}">Reliable Data Pipelines</a>
    <a href="{{ '/biblioteca/#pyspark-sql' | relative_url }}">PySpark &amp; SQL</a>
    <a href="{{ '/biblioteca/#data-quality' | relative_url }}">Data Quality</a>
    <a href="{{ '/biblioteca/#analytics-engineering' | relative_url }}">Analytics Engineering</a>
  </nav>

  <div class="analytics-actions">
    <a class="btn" href="{% post_url 2026-08-08-integrando-fontes-heterogeneas-em-um-pipeline-de-dados %}">Começar pelo artigo principal</a>
    <a class="analytics-actions__link" href="{{ '/biblioteca/' | relative_url }}">Explorar a biblioteca</a>
    <a class="analytics-actions__link" href="https://github.com/scarletjulia/scarletjulia.github.io/tree/main/labs/reliable-data-pipeline-demo">Ver demonstração no GitHub</a>
  </div>
</section>
