"""Offline regression tests for safe BigQuery identifier interpolation."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_published_ml_outputs.py"


def import_verifier():
    """Import the verifier without installing Google Cloud SDK dependencies."""
    modules = {}
    for name in (
        "google",
        "google.cloud",
        "google.cloud.bigquery",
        "google.oauth2",
        "google.oauth2.service_account",
    ):
        stub = types.ModuleType(name)
        if name in ("google", "google.cloud", "google.oauth2"):
            stub.__path__ = []
        modules[name] = stub
    modules["google.cloud"].bigquery = modules["google.cloud.bigquery"]
    modules["google.oauth2"].service_account = modules["google.oauth2.service_account"]
    modules["google.cloud.bigquery"].Client = object

    spec = importlib.util.spec_from_file_location("_test_bigquery_identifiers", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load BigQuery output verifier")
    verifier = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, modules):
        spec.loader.exec_module(verifier)
    return verifier


class BigQueryIdentifierValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = import_verifier()

    def test_accepts_standard_project_and_dataset_names(self):
        prefix = self.verifier.qualified_table_prefix(
            "football-prod-2026", "football_ml"
        )
        self.assertEqual(prefix, "`football-prod-2026.football_ml")

    def test_accepts_underscore_and_numeric_dataset(self):
        self.assertEqual(
            self.verifier.qualified_table_prefix("project123", "ml_2026"),
            "`project123.ml_2026",
        )

    def test_rejects_unsafe_project_ids(self):
        for project in ("", "invalid.name", "project`", "a\nselect 1", "a;DROP"):
            with (
                self.subTest(project=project),
                self.assertRaisesRegex(ValueError, "project ID"),
            ):
                self.verifier.qualified_table_prefix(project, "football_ml")

    def test_rejects_unsafe_dataset_ids(self):
        for dataset in ("", "wrong.name", "table`", "my dataset", "x;DROP"):
            with (
                self.subTest(dataset=dataset),
                self.assertRaisesRegex(ValueError, "dataset"),
            ):
                self.verifier.qualified_table_prefix("project123", dataset)

    def test_rejects_invalid_google_cloud_project_ids(self):
        for project in ("PROJECT123", "pro_ject123", "project123-", "-project123", "a", "a" * 31):
            with (
                self.subTest(project=project),
                self.assertRaisesRegex(ValueError, "project ID"),
            ):
                self.verifier.qualified_table_prefix(project, "football_ml")

    def test_rejects_invalid_bigquery_dataset_ids(self):
        for dataset in ("ml-production", "x" * 1025):
            with (
                self.subTest(dataset=dataset),
                self.assertRaisesRegex(ValueError, "dataset"),
            ):
                self.verifier.qualified_table_prefix("project123", dataset)

    def test_accepts_hidden_and_maximum_length_dataset_ids(self):
        self.assertEqual(
            self.verifier.qualified_table_prefix("project123", "_hidden"),
            "`project123._hidden",
        )
        self.assertEqual(
            self.verifier.qualified_table_prefix("project123", "x" * 1024),
            "`project123." + "x" * 1024,
        )

    def test_dataset_validation_precedes_bigquery_client_creation(self):
        args = argparse.Namespace(
            project_id="project123", dataset="invalid-dataset", credentials=None
        )
        with (
            mock.patch.object(self.verifier, "parse_args", return_value=args),
            mock.patch.object(self.verifier, "bigquery_client") as client,
        ):
            with self.assertRaisesRegex(ValueError, "dataset"):
                self.verifier.main()
            client.assert_not_called()

    def test_invalid_identifier_fails_before_client_creation(self):
        args = argparse.Namespace(
            project_id="project123", dataset="bad`dataset", credentials=None
        )
        with (
            mock.patch.object(self.verifier, "parse_args", return_value=args),
            mock.patch.object(self.verifier, "bigquery_client") as client,
        ):
            with self.assertRaisesRegex(ValueError, "dataset"):
                self.verifier.main()
            client.assert_not_called()


    @staticmethod
    def _valid_bigquery_row():
        return {
            "model_version": "release-2026-10",
            "release_status": "approved",
            "current_prediction_rows": 5,
            **dict.fromkeys(
                (
                    "blocking_gate_failures",
                    "invalid_current_predictions",
                    "invalid_evaluation_predictions",
                    "evaluation_version_mismatches",
                    "metric_version_mismatches",
                    "invalid_segment_metrics",
                    "drift_version_mismatches",
                    "importance_version_mismatches",
                    "gate_version_mismatches",
                ),
                0,
            ),
        }

    def _run_with_mock_row(self, row):
        args = argparse.Namespace(
            project_id="project123", dataset="football_ml", credentials=None
        )
        client = mock.Mock()
        client.query.return_value.result.return_value = [row]
        with (
            mock.patch.object(self.verifier, "parse_args", return_value=args),
            mock.patch.object(self.verifier, "bigquery_client", return_value=client),
        ):
            self.verifier.main()
        return client

    def test_null_safe_model_version_and_quality_gate_sql(self):
        client = self._run_with_mock_row(self._valid_bigquery_row())
        query = client.query.call_args.args[0]
        self.assertEqual(
            query.count("model_version IS DISTINCT FROM latest.model_version"), 6
        )
        self.assertNotIn("model_version != latest.model_version", query)
        self.assertIn("severity = 'blocking' and passed IS NOT TRUE", query)
        client.query.assert_called_once()
        self.assertEqual(client.query.call_args.kwargs, {"location": "EU"})

    def test_rejects_missing_release_status_and_model_version(self):
        for field, value, message in (
            ("release_status", None, "invalid release status"),
            ("release_status", "unknown", "invalid release status"),
            ("model_version", None, "model version is missing"),
            ("model_version", "", "model version is missing"),
            ("model_version", "  ", "model version is missing"),
        ):
            with self.subTest(field=field, value=value):
                row = self._valid_bigquery_row()
                row[field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self._run_with_mock_row(row)

    def test_approved_with_monitoring_is_still_accepted(self):
        row = self._valid_bigquery_row()
        row["release_status"] = "approved_with_monitoring"
        self._run_with_mock_row(row)


if __name__ == "__main__":
    unittest.main()
