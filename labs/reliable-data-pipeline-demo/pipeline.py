from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SOURCE_NAME = "orders_csv"
REQUIRED_COLUMNS = {
    "order_id",
    "order_item_id",
    "product_id",
    "quantity",
    "unit_price",
    "currency",
    "order_timestamp",
    "updated_at",
}


@dataclass(frozen=True)
class LoadResult:
    checksum: str
    skipped: bool
    accepted_rows: int
    rejected_rows: int
    rows_written: int
    watermark: str | None


def connect(database: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database), isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS pipeline_batches (
            batch_checksum TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('processing', 'succeeded', 'failed')),
            accepted_rows INTEGER NOT NULL DEFAULT 0,
            rejected_rows INTEGER NOT NULL DEFAULT 0,
            processed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pipeline_state (
            source_name TEXT PRIMARY KEY,
            watermark TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT NOT NULL,
            order_item_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
            currency TEXT NOT NULL,
            order_timestamp TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            batch_checksum TEXT NOT NULL,
            PRIMARY KEY (order_id, order_item_id)
        );

        CREATE TABLE IF NOT EXISTS rejected_records (
            rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_checksum TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            reason TEXT NOT NULL,
            payload TEXT NOT NULL,
            rejected_at TEXT NOT NULL
        );
        """
    )


def file_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp sem timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def parse_row(row: dict[str, str]) -> dict[str, Any]:
    missing_values = sorted(column for column in REQUIRED_COLUMNS if not row.get(column, "").strip())
    if missing_values:
        raise ValueError(f"campos obrigatórios vazios: {', '.join(missing_values)}")

    quantity = int(row["quantity"])
    if quantity <= 0:
        raise ValueError("quantity deve ser maior que zero")

    try:
        unit_price = Decimal(row["unit_price"]).quantize(Decimal("0.01"))
    except InvalidOperation as error:
        raise ValueError("unit_price inválido") from error
    if unit_price < 0:
        raise ValueError("unit_price não pode ser negativo")

    currency = row["currency"].strip().upper()
    if len(currency) != 3:
        raise ValueError("currency deve usar um código de três letras")

    return {
        "order_id": row["order_id"].strip(),
        "order_item_id": row["order_item_id"].strip(),
        "product_id": row["product_id"].strip(),
        "quantity": quantity,
        "unit_price_cents": int(unit_price * 100),
        "currency": currency,
        "order_timestamp": normalize_timestamp(row["order_timestamp"]),
        "updated_at": normalize_timestamp(row["updated_at"]),
    }


def current_watermark(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT watermark FROM pipeline_state WHERE source_name = ?",
        (SOURCE_NAME,),
    ).fetchone()
    return row["watermark"] if row else None


def load_csv(connection: sqlite3.Connection, path: str | Path) -> LoadResult:
    path = Path(path)
    checksum = file_checksum(path)
    previous = connection.execute(
        "SELECT status, accepted_rows, rejected_rows FROM pipeline_batches WHERE batch_checksum = ?",
        (checksum,),
    ).fetchone()

    if previous and previous["status"] == "succeeded":
        return LoadResult(
            checksum=checksum,
            skipped=True,
            accepted_rows=previous["accepted_rows"],
            rejected_rows=previous["rejected_rows"],
            rows_written=0,
            watermark=current_watermark(connection),
        )

    now = datetime.now(timezone.utc).isoformat()
    accepted_rows = 0
    rejected_rows = 0
    rows_written = 0
    maximum_updated_at: str | None = None

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO pipeline_batches (
                batch_checksum, source_name, status, processed_at
            ) VALUES (?, ?, 'processing', ?)
            ON CONFLICT(batch_checksum) DO UPDATE SET
                status = 'processing',
                processed_at = excluded.processed_at
            """,
            (checksum, SOURCE_NAME, now),
        )

        with path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            columns = set(reader.fieldnames or [])
            missing_columns = sorted(REQUIRED_COLUMNS - columns)
            if missing_columns:
                raise ValueError(f"colunas obrigatórias ausentes: {', '.join(missing_columns)}")

            for row_number, raw_row in enumerate(reader, start=2):
                try:
                    row = parse_row(raw_row)
                except (ValueError, TypeError) as error:
                    rejected_rows += 1
                    connection.execute(
                        """
                        INSERT INTO rejected_records (
                            batch_checksum, row_number, reason, payload, rejected_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (checksum, row_number, str(error), json.dumps(raw_row, ensure_ascii=False), now),
                    )
                    continue

                accepted_rows += 1
                cursor = connection.execute(
                    """
                    INSERT INTO orders (
                        order_id, order_item_id, product_id, quantity,
                        unit_price_cents, currency, order_timestamp,
                        updated_at, batch_checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(order_id, order_item_id) DO UPDATE SET
                        product_id = excluded.product_id,
                        quantity = excluded.quantity,
                        unit_price_cents = excluded.unit_price_cents,
                        currency = excluded.currency,
                        order_timestamp = excluded.order_timestamp,
                        updated_at = excluded.updated_at,
                        batch_checksum = excluded.batch_checksum
                    WHERE excluded.updated_at > orders.updated_at
                    """,
                    (
                        row["order_id"],
                        row["order_item_id"],
                        row["product_id"],
                        row["quantity"],
                        row["unit_price_cents"],
                        row["currency"],
                        row["order_timestamp"],
                        row["updated_at"],
                        checksum,
                    ),
                )
                rows_written += max(cursor.rowcount, 0)
                maximum_updated_at = max(maximum_updated_at or row["updated_at"], row["updated_at"])

        if maximum_updated_at:
            connection.execute(
                """
                INSERT INTO pipeline_state (source_name, watermark)
                VALUES (?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    watermark = CASE
                        WHEN excluded.watermark > pipeline_state.watermark
                        THEN excluded.watermark
                        ELSE pipeline_state.watermark
                    END
                """,
                (SOURCE_NAME, maximum_updated_at),
            )

        connection.execute(
            """
            UPDATE pipeline_batches
            SET status = 'succeeded', accepted_rows = ?, rejected_rows = ?, processed_at = ?
            WHERE batch_checksum = ?
            """,
            (accepted_rows, rejected_rows, now, checksum),
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        connection.execute(
            """
            INSERT INTO pipeline_batches (
                batch_checksum, source_name, status, processed_at
            ) VALUES (?, ?, 'failed', ?)
            ON CONFLICT(batch_checksum) DO UPDATE SET
                status = 'failed',
                processed_at = excluded.processed_at
            """,
            (checksum, SOURCE_NAME, now),
        )
        raise

    return LoadResult(
        checksum=checksum,
        skipped=False,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        rows_written=rows_written,
        watermark=current_watermark(connection),
    )


def database_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    orders = connection.execute(
        """
        SELECT
            COUNT(*) AS order_items,
            COALESCE(SUM(quantity * unit_price_cents), 0) AS revenue_cents
        FROM orders
        """
    ).fetchone()
    batches = connection.execute(
        "SELECT COUNT(*) AS total FROM pipeline_batches WHERE status = 'succeeded'"
    ).fetchone()
    rejections = connection.execute(
        "SELECT COUNT(*) AS total FROM rejected_records"
    ).fetchone()
    return {
        "order_items": orders["order_items"],
        "revenue_cents": orders["revenue_cents"],
        "successful_batches": batches["total"],
        "rejected_records": rejections["total"],
        "watermark": current_watermark(connection),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga CSV idempotente de itens de pedido")
    parser.add_argument("--input", required=True, help="Caminho do arquivo CSV")
    parser.add_argument("--database", default="demo.db", help="Arquivo SQLite de destino")
    args = parser.parse_args()

    connection = connect(args.database)
    try:
        create_schema(connection)
        result = load_csv(connection, args.input)
        print(json.dumps({"load": asdict(result), "database": database_summary(connection)}, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
