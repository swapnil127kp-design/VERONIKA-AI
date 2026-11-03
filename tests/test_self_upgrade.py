"""
Tests for self-upgrade engine.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app import self_upgrade
from app.self_upgrade import SelfUpgrader, UpgradeResult


def test_upgrade_result_to_dict():
    r = UpgradeResult(True, "ok", {"x": 1})
    d = r.to_dict()
    assert d["success"] is True
    assert d["message"] == "ok"
    assert d["data"] == {"x": 1}


def test_self_upgrader_non_git_repo_status():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        su = SelfUpgrader(repo_root=repo)
        assert su.is_git_repo() is False
        st = su.status()
        assert st["git_repo"] is False
        assert st["commit"] == "unknown"
        assert st["branch"] == "unknown"


def test_backup_creates_manifest(tmp_path, monkeypatch):
    # Create a minimal repo structure
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app").mkdir()
    (repo / "app" / "config.py").write_text("# config", encoding="utf-8")
    (repo / "README.md").write_text("hello", encoding="utf-8")
    (repo / "logs").mkdir()
    (repo / "logs" / "test.log").write_text("log", encoding="utf-8")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "pyvenv.cfg").write_text("venv", encoding="utf-8")

    # Fake git state
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "is_git_repo", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_commit", lambda self: "abc123")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_branch", lambda self: "main")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "has_uncommitted_changes", lambda self: False)

    # Redirect backup dir
    bu_dir = tmp_path / "backups"
    monkeypatch.setattr(self_upgrade, "BACKUP_DIR", bu_dir)
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")

    su = SelfUpgrader(repo_root=repo)
    res = su.backup(include_logs=False)
    assert res.success
    bpath = Path(res.data["path"])
    assert bpath.exists()
    manifest = json.loads((bpath / "BACKUP_MANIFEST.json").read_text())
    assert manifest["commit_before"] == "abc123"
    # logs should be excluded
    assert not (bpath / "logs").exists()
    # .venv should be excluded
    assert not (bpath / ".venv").exists()
    # important files included
    assert (bpath / "app" / "config.py").exists()


def test_backup_includes_logs_when_requested(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "x.txt").write_text("x", encoding="utf-8")
    (repo / "logs").mkdir()
    (repo / "logs" / "a.log").write_text("a", encoding="utf-8")

    monkeypatch.setattr(self_upgrade.SelfUpgrader, "is_git_repo", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_commit", lambda self: "deadbeef")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_branch", lambda self: "dev")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "has_uncommitted_changes", lambda self: False)

    bu_dir = tmp_path / "backups"
    monkeypatch.setattr(self_upgrade, "BACKUP_DIR", bu_dir)
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")

    su = SelfUpgrader(repo_root=repo)
    res = su.backup(include_logs=True)
    assert res.success
    bpath = Path(res.data["path"])
    assert (bpath / "logs" / "a.log").exists()


def test_fetch_requires_git_repo(tmp_path):
    su = SelfUpgrader(repo_root=tmp_path)
    res = su.fetch()
    assert not res.success
    assert "Not a git repository" in res.message


def test_pull_rejects_uncommitted_changes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(self_upgrade.SelfUpgrader, "is_git_repo", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "has_uncommitted_changes", lambda self: True)

    su = SelfUpgrader(repo_root=repo)
    res = su.pull()
    assert not res.success
    assert "uncommitted changes" in res.message.lower()


def test_validate_quick_passes_on_imports(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")
    su = SelfUpgrader(repo_root=repo)
    res = su.validate(quick=True)
    assert res.success


def test_rollback_no_backup_state(tmp_path, monkeypatch):
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")
    su = SelfUpgrader(repo_root=tmp_path)
    res = su.rollback()
    assert not res.success
    assert "No backup path" in res.message


def test_upgrade_blocks_on_uncommitted_in_safe_mode(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "is_git_repo", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "has_uncommitted_changes", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_commit", lambda self: "c1")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_branch", lambda self: "main")
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")

    su = SelfUpgrader(repo_root=repo)
    res = su.upgrade(safe_mode=True)
    assert not res.success
    assert "uncommitted changes" in res.message.lower()


def test_upgrade_allows_uncommitted_with_safe_mode_false(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "is_git_repo", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "has_uncommitted_changes", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_commit", lambda self: "c1")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_branch", lambda self: "main")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "fetch", lambda self: UpgradeResult(True, "fetch ok"))
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "backup", lambda self: UpgradeResult(True, "backup ok", {"path": str(tmp_path / "b")}))
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "pull", lambda self, branch=None: UpgradeResult(True, "pulled", {"commit": "c2"}))
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "validate", lambda self, quick=True: UpgradeResult(True, "ok"))
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")

    su = SelfUpgrader(repo_root=repo)
    res = su.upgrade(safe_mode=False)
    assert res.success


def test_upgrade_with_validation_failure_rolls_back(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "is_git_repo", lambda self: True)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "has_uncommitted_changes", lambda self: False)
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_commit", lambda self: "c1")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "current_branch", lambda self: "main")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "fetch", lambda self: UpgradeResult(True, "fetch ok"))
    backup_called = []

    def fake_backup():
        backup_called.append(True)
        return UpgradeResult(True, "backup ok", {"path": str(tmp_path / "b")})

    rb_called = []
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "backup", lambda self: fake_backup())
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "pull", lambda self, branch=None: UpgradeResult(True, "pulled", {"commit": "c2"}))
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "validate", lambda self, quick=True: UpgradeResult(False, "bad", {"errors": ["e1"]}))
    def fake_rb():
        rb_called.append(True)
        return UpgradeResult(True, "rolled back")
    monkeypatch.setattr(self_upgrade.SelfUpgrader, "rollback", lambda self: fake_rb())
    monkeypatch.setattr(self_upgrade, "STATE_FILE", tmp_path / "state.json")

    su = SelfUpgrader(repo_root=repo)
    res = su.upgrade(safe_mode=True)
    assert not res.success
    assert backup_called
    assert rb_called
    assert "rolled back" in res.message.lower()
