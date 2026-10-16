"""Offline integrity-order tests for model artifact verification.

The training module is replaced with a small stub so these tests do not need
BigQuery credentials, a trained model, or network access.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_ml_artifact.py"
FEATURE_HASH = "test-feature-contract"


def load_verifier():
    """Import the real verifier without loading the training-time dependencies."""
    training_stub = types.ModuleType("train_player_market_value")
    training_stub.file_sha256 = lambda path: hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()
    training_stub.feature_contract_hash = lambda: FEATURE_HASH

    spec = importlib.util.spec_from_file_location("_test_ml_artifact_verifier", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import ML artifact verifier")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"train_player_market_value": training_stub}):
        spec.loader.exec_module(module)
    return module


def prepare_artifacts(directory: Path, *, hash_matches=True, contract_matches=True):
    model_path = directory / "model.joblib"
    model_path.write_bytes(b"synthetic-model-content")
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    manifest = {
        "model_artifact_sha256": actual_hash if hash_matches else "0" * 64,
        "feature_contract_hash": FEATURE_HASH if contract_matches else "wrong-contract",
        "model_version": "test-v1",
        "release_status": "approved",
    }
    metrics = {
        "model_version": "test-v1",
        "release_status": "approved",
        "blocking_quality_gates_passed": True,
    }
    (directory / "artifact_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (directory / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return model_path


def valid_bundle():
    return {
        "feature_contract_hash": FEATURE_HASH,
        "model_version": "test-v1",
        "pipeline": object(),
        "selected_ml_blend_weight": 0.8,
        "selected_ml_blend_weights_by_quality_status": {
            "high": 0.8,
            "medium": 1.0,
            "limited": 0.0,
        },
        "baseline_fill_value_eur": 0.0,
        "numeric_features": [],
        "categorical_features": [],
        "feature_contract": {},
        "runtime_versions": {},
    }


class ArtifactIntegrityOrderTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_dir = Path(self.tmp.name)

    def run_verifier(self, mocked_bundle):
        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(
                self.verifier.joblib, "load", return_value=mocked_bundle
            ) as deserializer,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.verifier.main()
        return deserializer

    def test_missing_model_never_reaches_joblib(self):
        model_path = prepare_artifacts(self.output_dir)
        model_path.unlink()

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaises(FileNotFoundError):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_malformed_metrics_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        (self.output_dir / "metrics.json").write_text(
            "{not valid json", encoding="utf-8"
        )

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaises(json.JSONDecodeError):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_tampered_artifact_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir, hash_matches=False)
        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "checksum"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_incompatible_feature_contract_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir, contract_matches=False)
        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "feature contract"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_valid_manifest_proceeds_to_deserialization(self):
        model_path = prepare_artifacts(self.output_dir)
        deserializer = self.run_verifier(valid_bundle())
        deserializer.assert_called_once_with(model_path)


    def test_rejected_release_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        manifest_path = self.output_dir / "artifact_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["release_status"] = "rejected"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "Rejected model artifact"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_failed_quality_gate_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        metrics_path = self.output_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["blocking_quality_gates_passed"] = False
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "blocking quality gates"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_metrics_version_mismatch_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        metrics_path = self.output_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["model_version"] = "incompatible"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "Metrics version"):
                self.verifier.main()
            deserializer.assert_not_called()


    def test_unknown_release_status_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        manifest_path = self.output_dir / "artifact_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["release_status"] = "pending"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "invalid release status"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_truthy_string_quality_gate_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        metrics_path = self.output_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["blocking_quality_gates_passed"] = "false"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "blocking quality gates"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_release_status_mismatch_never_reaches_joblib(self):
        prepare_artifacts(self.output_dir)
        metrics_path = self.output_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["release_status"] = "approved_with_monitoring"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

        with (
            mock.patch.object(
                self.verifier, "parse_args",
                return_value=argparse.Namespace(output_dir=str(self.output_dir)),
            ),
            mock.patch.object(self.verifier.joblib, "load") as deserializer,
        ):
            with self.assertRaisesRegex(ValueError, "release status does not match"):
                self.verifier.main()
            deserializer.assert_not_called()

    def test_approved_with_monitoring_proceeds_to_deserialization(self):
        model_path = prepare_artifacts(self.output_dir)
        for name in ("artifact_manifest.json", "metrics.json"):
            path = self.output_dir / name
            metadata = json.loads(path.read_text(encoding="utf-8"))
            metadata["release_status"] = "approved_with_monitoring"
            path.write_text(json.dumps(metadata), encoding="utf-8")

        deserializer = self.run_verifier(valid_bundle())
        deserializer.assert_called_once_with(model_path)


if __name__ == "__main__":
    unittest.main()
