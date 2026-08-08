-- Deve retornar zero linhas: duplicidade na chave de negócio.
SELECT order_id, order_item_id, COUNT(*) AS occurrences
FROM orders
GROUP BY order_id, order_item_id
HAVING COUNT(*) > 1;

-- Deve retornar zero: registros inválidos na camada confiável.
SELECT COUNT(*) AS invalid_rows
FROM orders
WHERE quantity <= 0
   OR unit_price_cents < 0
   OR product_id IS NULL;

-- Reconciliação operacional por lote.
SELECT
    batch_checksum,
    accepted_rows,
    rejected_rows,
    status
FROM pipeline_batches
ORDER BY processed_at DESC;
