"""Static CircleCI contracts for offline and credential-free verification."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".circleci" / "config.yml"


def _config():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_circleci_workflow_references_existing_jobs():
    config = _config()
    assert config["version"] == 2.1
    jobs = config["jobs"]
    workflow = config["workflows"]["verify-offline-source"]["jobs"]
    assert {"dbt-source-preflight", "ml-contract-smoke"} == set(workflow)
    assert set(workflow).issubset(jobs)


def test_offline_dbt_preflight_has_no_live_cloud_command():
    commands = [
        step["run"]["command"]
        for step in _config()["jobs"]["dbt-source-preflight"]["steps"]
        if isinstance(step, dict) and isinstance(step.get("run"), dict)
    ]
    assert any("check_offline_ci.py" in command for command in commands)
    assert not any("dbt run" in command or "dbt build" in command for command in commands)


def test_ml_smoke_is_synthetic_not_authenticated_bigquery():
    config = _config()
    job = config["jobs"]["ml-contract-smoke"]
    assert any(
        "check_ml_pipeline.py" in step["run"].get("command", "")
        for step in job["steps"]
        if isinstance(step, dict) and isinstance(step.get("run"), dict)
    )
    assert "context" not in job
    assert "environment" not in job


def test_referenced_local_scripts_exist():
    assert (ROOT / "scripts" / "check_offline_ci.py").is_file()
    assert (ROOT / "scripts" / "check_ml_pipeline.py").is_file()
    assert (ROOT / "requirements-ml.txt").is_file()
