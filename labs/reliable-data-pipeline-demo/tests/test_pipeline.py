import csv
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from pipeline import connect, create_schema, database_summary, load_csv  # noqa: E402


class IdempotentPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.db"
        self.connection = connect(self.database_path)
        create_schema(self.connection)

    def tearDown(self):
        self.connection.close()
        self.temp_directory.cleanup()

    def write_csv(self, name, rows):
        path = Path(self.temp_directory.name) / name
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=[
                    "order_id",
                    "order_item_id",
                    "product_id",
                    "quantity",
                    "unit_price",
                    "currency",
                    "order_timestamp",
                    "updated_at",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_same_batch_is_loaded_once(self):
        sample = PROJECT_DIR / "sample_data" / "orders.csv"

        first = load_csv(self.connection, sample)
        second = load_csv(self.connection, sample)
        summary = database_summary(self.connection)

        self.assertFalse(first.skipped)
        self.assertTrue(second.skipped)
        self.assertEqual(summary["order_items"], 2)
        self.assertEqual(summary["revenue_cents"], 17_980)
        self.assertEqual(summary["successful_batches"], 1)

    def test_newer_version_wins_and_invalid_row_is_quarantined(self):
        load_csv(self.connection, PROJECT_DIR / "sample_data" / "orders.csv")
        update = self.write_csv(
            "update.csv",
            [
                {
                    "order_id": "O100",
                    "order_item_id": "1",
                    "product_id": "P100",
                    "quantity": "2",
                    "unit_price": "34.90",
                    "currency": "brl",
                    "order_timestamp": "2026-08-08T09:15:00-03:00",
                    "updated_at": "2026-08-08T13:00:00-03:00",
                },
                {
                    "order_id": "O102",
                    "order_item_id": "1",
                    "product_id": "P300",
                    "quantity": "0",
                    "unit_price": "50.00",
                    "currency": "BRL",
                    "order_timestamp": "2026-08-08T11:00:00-03:00",
                    "updated_at": "2026-08-08T13:05:00-03:00",
                },
            ],
        )

        result = load_csv(self.connection, update)
        summary = database_summary(self.connection)

        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.rejected_rows, 1)
        self.assertEqual(summary["order_items"], 2)
        self.assertEqual(summary["revenue_cents"], 18_980)
        self.assertEqual(summary["rejected_records"], 1)
        self.assertEqual(summary["watermark"], "2026-08-08T16:00:00+00:00")

        older = self.write_csv(
            "older.csv",
            [
                {
                    "order_id": "O100",
                    "order_item_id": "1",
                    "product_id": "P100",
                    "quantity": "2",
                    "unit_price": "1.00",
                    "currency": "BRL",
                    "order_timestamp": "2026-08-08T09:15:00-03:00",
                    "updated_at": "2026-08-08T12:50:00-03:00",
                }
            ],
        )
        load_csv(self.connection, older)

        self.assertEqual(database_summary(self.connection)["revenue_cents"], 18_980)


if __name__ == "__main__":
    unittest.main()
