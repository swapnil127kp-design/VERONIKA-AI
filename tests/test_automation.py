"""
Tests for automation modules.
"""
import math
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from automation.permissions import PermissionManager
from automation.action_registry import ActionRegistry, ActionResult


class TestPermissionManager:
    """Tests for PermissionManager."""

    def setup_method(self):
        self.pm = PermissionManager()

    def test_allow_normal_path(self):
        assert self.pm.is_path_allowed(r"C:\Users\Test\Documents\file.txt")

    def test_deny_ssh_path(self):
        assert not self.pm.is_path_allowed(r"C:\Users\Test\.ssh\id_rsa")

    def test_deny_env_file(self):
        assert not self.pm.is_path_allowed(r"C:\project\.env")

    def test_deny_password_file(self):
        assert not self.pm.is_path_allowed(r"C:\Users\Test\passwords.txt")

    def test_validate_url_http(self):
        assert self.pm.validate_url("https://www.google.com")
        assert self.pm.validate_url("http://localhost:8080")

    def test_validate_url_reject_bad(self):
        assert not self.pm.validate_url("")
        assert not self.pm.validate_url("ftp://files.example.com")
        assert not self.pm.validate_url("javascript:alert(1)")

    def test_validate_url_ms_settings(self):
        assert self.pm.validate_url("ms-settings:display")

    def test_validate_app_name_safe(self):
        assert self.pm.validate_app_name("notepad")
        assert self.pm.validate_app_name("Visual Studio Code")

    def test_validate_app_name_dangerous(self):
        assert not self.pm.validate_app_name("notepad; rm -rf /")
        assert not self.pm.validate_app_name("app & calc")
        assert not self.pm.validate_app_name("app | dir")

    def test_requires_confirmation(self):
        assert self.pm.requires_confirmation("delete_file")
        assert not self.pm.requires_confirmation("launch_app")


class TestActionResult:
    """Tests for ActionResult."""

    def test_success(self):
        r = ActionResult(True, "ok")
        assert r.success is True
        assert r.message == "ok"

    def test_to_dict(self):
        r = ActionResult(False, "fail", {"key": "val"})
        d = r.to_dict()
        assert d["success"] is False
        assert d["data"]["key"] == "val"


class TestActionRegistry:
    """Tests for ActionRegistry."""

    def setup_method(self):
        self.registry = ActionRegistry(memory_manager=None)

    def test_get_available_actions(self):
        actions = self.registry.get_available_actions()
        assert "launch_app" in actions
        assert "calculate" in actions
        assert "open_website" in actions

    def test_execute_unknown_action(self):
        result = self.registry.execute("nonexistent_action")
        assert not result.success
        assert "Unknown action" in result.message

    def test_calculate_basic(self):
        result = self.registry.execute("calculate", {"expression": "2 + 3 * 4"})
        assert result.success
        assert result.data["result"] == 14

    def test_calculate_math_functions(self):
        result = self.registry.execute("calculate", {"expression": "sqrt(144)"})
        assert result.success
        assert result.data["result"] == 12.0

    def test_calculate_invalid_chars(self):
        result = self.registry.execute("calculate", {"expression": "__import__('os')"})
        assert not result.success

    def test_calculate_empty(self):
        result = self.registry.execute("calculate", {"expression": ""})
        assert not result.success

    def test_launch_app_empty(self):
        result = self.registry.execute("launch_app", {"name": ""})
        assert not result.success

    def test_open_folder_nonexistent(self):
        result = self.registry.execute("open_folder", {"path": r"C:\this\does\not\exist\ever"})
        assert not result.success

    def test_browser_search_empty(self):
        result = self.registry.execute("browser_search", {"query": ""})
        assert not result.success

    def test_save_note_no_memory(self):
        # No memory manager, should fail
        result = self.registry.execute("save_note", {"title": "Test", "content": "Hello"})
        assert not result.success

    def test_create_reminder_no_memory(self):
        result = self.registry.execute("create_reminder", {"title": "Test", "due_at": "2025-01-01"})
        assert not result.success

    def test_delete_file_action_requires_confirmation(self):
        # delete_file is a destructive action requiring confirmation
        result = self.registry.execute("delete_file", {"path": r"C:\test\sample.txt"})
        assert not result.success
        assert "requires user confirmation" in result.message


class TestFileActions:
    """Tests for FileActions module."""

    def setup_method(self):
        from automation.file_actions import FileActions
        self.fa = FileActions()

    def test_create_and_read_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        res = self.fa.create_file(str(f), "Hello VERONIKA")
        assert res["success"] is True

        read_res = self.fa.read_file(str(f))
        assert read_res["success"] is True
        assert read_res["content"] == "Hello VERONIKA"

    def test_create_file_no_overwrite(self, tmp_path):
        f = tmp_path / "exist.txt"
        self.fa.create_file(str(f), "Initial")
        res2 = self.fa.create_file(str(f), "New", overwrite=False)
        assert res2["success"] is False
        assert "already exists" in res2["message"]

    def test_create_file_with_overwrite(self, tmp_path):
        f = tmp_path / "exist.txt"
        self.fa.create_file(str(f), "Initial")
        res2 = self.fa.create_file(str(f), "Updated", overwrite=True)
        assert res2["success"] is True
        assert self.fa.read_file(str(f))["content"] == "Updated"

    def test_delete_file(self, tmp_path):
        f = tmp_path / "to_delete.txt"
        self.fa.create_file(str(f), "bye")
        del_res = self.fa.delete_file(str(f))
        assert del_res["success"] is True
        assert not f.exists()

    def test_delete_nonexistent_file(self, tmp_path):
        f = tmp_path / "ghost.txt"
        res = self.fa.delete_file(str(f))
        assert res["success"] is False
        assert "does not exist" in res["message"]

    def test_list_directory(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        (tmp_path / "sub").mkdir()

        res = self.fa.list_directory(str(tmp_path))
        assert res["success"] is True
        assert len(res["files"]) == 3

    def test_search_files(self, tmp_path):
        (tmp_path / "target1.py").write_text("code", encoding="utf-8")
        (tmp_path / "target2.py").write_text("code", encoding="utf-8")
        (tmp_path / "other.txt").write_text("text", encoding="utf-8")

        res = self.fa.search_files(str(tmp_path), "*.py")
        assert res["success"] is True
        assert len(res["files"]) == 2

    def test_get_file_info(self, tmp_path):
        f = tmp_path / "info.txt"
        f.write_text("12345", encoding="utf-8")

        res = self.fa.get_file_info(str(f))
        assert res["success"] is True
        assert res["info"]["name"] == "info.txt"
        assert res["info"]["is_file"] is True
        assert res["info"]["size_bytes"] == 5

    def test_forbidden_path_blocked(self):
        res = self.fa.read_file(r"C:\Users\Test\.ssh\id_rsa")
        assert res["success"] is False
        assert "not permitted" in res["message"]


class TestBrowserActions:
    """Tests for BrowserActions module."""

    def setup_method(self):
        from automation.browser_actions import BrowserActions
        self.ba = BrowserActions()

    def test_get_available_settings(self):
        pages = self.ba.get_available_settings()
        assert "display" in pages
        assert "sound" in pages
        assert "bluetooth" in pages

    def test_open_url_invalid(self):
        res = self.ba.open_url("javascript:void(0)")
        assert res["success"] is False
        assert "Invalid or unsafe URL" in res["message"]

    def test_browser_search_empty(self):
        res = self.ba.browser_search("   ")
        assert res["success"] is False

    def test_open_settings_unknown(self):
        res = self.ba.open_settings("nonexistent_settings_page_xyz")
        assert res["success"] is False
        assert "Unknown settings page" in res["message"]


class TestWorkflowEngine:
    """Tests for WorkflowEngine."""

    def test_templates_exist(self):
        from automation.workflow_engine import WORKFLOW_TEMPLATES
        assert "coding_session" in WORKFLOW_TEMPLATES
        assert "morning_routine" in WORKFLOW_TEMPLATES

    def test_start_workflow_unknown(self):
        from automation.action_registry import ActionRegistry
        from automation.workflow_engine import WorkflowEngine
        reg = ActionRegistry()
        we = WorkflowEngine(reg)
        assert we.start_workflow("nonexistent_workflow") is False


class TestCodingActions:
    """Tests for the coding/shell actions wired into ActionRegistry."""

    def setup_method(self):
        self.registry = ActionRegistry(memory_manager=None)

    def test_coding_actions_registered(self):
        actions = self.registry.get_available_actions()
        for name in ("run_shell", "run_python", "edit_file", "git_operation"):
            assert name in actions

    def test_run_python_success(self):
        result = self.registry.execute("run_python", {"code": "print(6 * 7)"})
        assert result.success
        assert "42" in result.message

    def test_run_python_failure(self):
        result = self.registry.execute("run_python", {"code": "raise ValueError('boom')"})
        assert not result.success
        assert "ValueError" in result.message

    def test_run_python_empty(self):
        result = self.registry.execute("run_python", {"code": ""})
        assert not result.success

    def test_run_shell_success(self):
        result = self.registry.execute("run_shell", {"command": "Write-Output veronika"})
        assert result.success
        assert "veronika" in result.message

    def test_run_shell_blocks_dangerous(self):
        result = self.registry.execute("run_shell", {"command": "format C: /y"})
        assert not result.success

    def test_edit_file_roundtrip(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("alpha beta alpha", encoding="utf-8")
        result = self.registry.execute(
            "edit_file", {"path": str(f), "old": "alpha", "new": "gamma"}
        )
        assert result.success
        assert f.read_text(encoding="utf-8") == "gamma beta gamma"

    def test_edit_file_missing_target(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("hello", encoding="utf-8")
        result = self.registry.execute(
            "edit_file", {"path": str(f), "old": "absent", "new": "x"}
        )
        assert not result.success

    def test_git_operation_non_repo(self, tmp_path):
        result = self.registry.execute(
            "git_operation", {"operation": "status", "directory": str(tmp_path)}
        )
        assert not result.success

    def test_git_operation_unsupported(self, tmp_path):
        result = self.registry.execute(
            "git_operation", {"operation": "rebase", "directory": str(tmp_path)}
        )
        assert not result.success
        assert "Unsupported git operation" in result.message


class TestReaAndMcpActions:
    """REA reasoning + MCP tool actions wired into ActionRegistry (Phase 2)."""

    def test_reason_and_decompose_registered(self):
        reg = ActionRegistry()
        actions = reg.get_available_actions()
        assert "reason" in actions
        assert "decompose_goal" in actions

    def test_reason_requires_goal(self):
        reg = ActionRegistry()
        assert not reg.execute("reason", {}).success

    def test_reason_runs_loops_with_fake_provider(self):
        from ai.provider_base import AIResponse

        class FakeProvider:
            def send_message(self, user_message, **kwargs):
                return AIResponse(content='{"thought": "t", "final_answer": "done"}')

        reg = ActionRegistry(provider_manager=FakeProvider())
        res = reg.execute("reason", {"goal": "do x"})
        assert res.success
        assert res.message == "done"
        assert res.data["final_answer"] == "done"

    def test_decompose_goal_with_fake_provider(self):
        from ai.provider_base import AIResponse

        class FakeProvider:
            def send_message(self, user_message, **kwargs):
                return AIResponse(content='{"sub_goals": ["alpha", "beta"]}')

        reg = ActionRegistry(provider_manager=FakeProvider())
        res = reg.execute("decompose_goal", {"goal": "big"})
        assert res.success
        assert "alpha" in res.message
        assert res.data["sub_goals"] == ["alpha", "beta"]

    def test_mcp_tools_registered_as_actions(self):
        class FakeMCP:
            def as_actions(self, wrap=None):
                def act(**kwargs):
                    return wrap("mcp__x__y", True, "ok", {})
                return {"mcp__x__y": act}

        reg = ActionRegistry(mcp_manager=FakeMCP())
        assert "mcp__x__y" in reg.get_available_actions()
        res = reg.execute("mcp__x__y", {})
        assert res.success
        assert res.message == "ok"

    def test_register_mcp_tools_returns_names(self):
        class FakeMCP:
            def as_actions(self, wrap=None):
                return {"mcp__a__b": lambda **k: wrap("mcp__a__b", True, "x", {})}

        reg = ActionRegistry()
        names = reg.register_mcp_tools(FakeMCP())
        assert names == ["mcp__a__b"]
