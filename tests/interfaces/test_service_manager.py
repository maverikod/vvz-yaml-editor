"""Tests for service_manager PID discovery helpers."""
from __future__ import annotations

from ai_editor.interfaces import service_manager as sm


def test_config_path_matches_cmdline_resolved_and_relative() -> None:
    cmd = ["python", "-m", "ai_editor.main", "--config", "config.json"]
    assert sm._config_path_matches_cmdline("config.json", cmd)
    assert sm._config_path_matches_cmdline("/tmp/config.json", cmd) is False


def test_config_path_matches_cmdline_absolute() -> None:
    cmd = ["python", "-m", "ai_editor.main", "--config", "/tmp/config.json"]
    assert sm._config_path_matches_cmdline("/tmp/config.json", cmd)


def test_config_path_matches_cmdline_rejects_shell_wrapper() -> None:
    cmd = ["bash", "-c", "python -m ai_editor.main --config config.json"]
    assert sm._config_path_matches_cmdline("config.json", cmd) is False


def test_resolve_stop_pids_prefers_alive_pid_file(
    monkeypatch,
) -> None:
    state = sm.ServiceState(
        pid=42,
        pid_alive=True,
        health_ok=True,
        health_url="http://127.0.0.1:8080/health",
        health_body=None,
        health_error=None,
    )
    args = sm.argparse.Namespace(config="config.json", pid_file="ai_editor.pid")
    assert sm._resolve_stop_pids(args, state) == [42]


def test_resolve_stop_pids_discovers_listener_when_health_ok(
    monkeypatch,
) -> None:
    state = sm.ServiceState(
        pid=None,
        pid_alive=False,
        health_ok=True,
        health_url="https://172.18.0.1:8014/health",
        health_body={"version": "1.0.0"},
        health_error=None,
    )
    args = sm.argparse.Namespace(config="config.json", pid_file="ai_editor.pid")

    monkeypatch.setattr(sm, "_load_raw_config", lambda _path: {"server": {"host": "172.18.0.1", "port": 8014}})
    monkeypatch.setattr(sm, "_find_listener_pid", lambda _host, _port: 1176815)
    monkeypatch.setattr(sm, "_find_pids_for_config", lambda _path: [1176815, 1176819])

    assert sm._resolve_stop_pids(args, state) == [1176815, 1176819]
