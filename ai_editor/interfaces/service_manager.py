"""Service manager CLI for ai_editor — start / stop / restart / status / generate-config."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ai_editor.config.config_generator import AiEditorConfigGenerator, ConfigGenerationError
from ai_editor.config.config_validator import AiEditorConfigValidator

DEFAULT_PID = "ai_editor.pid"
DEFAULT_LOG = "logs/ai_editor.log"
STARTUP_WAIT_S = 15
STARTUP_POLL_INTERVAL_S = 0.5


@dataclass
class ServiceState:
    """Combined view from PID file, process liveness, and HTTP health probe."""

    pid: int | None
    pid_alive: bool
    health_ok: bool
    health_url: str
    health_body: dict[str, Any] | None
    health_error: str | None

    @property
    def running(self) -> bool:
        """True when the server responds on /health."""
        return self.health_ok

    @property
    def pid_stale(self) -> bool:
        return self.pid is not None and not self.pid_alive and not self.health_ok


def _config_path(args: argparse.Namespace) -> str:
    return args.config or os.environ.get("AI_EDITOR_CONFIG", "config.json")


def _read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _load_raw_config(config_path: str) -> dict[str, Any]:
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


def _health_url(raw: dict[str, Any]) -> str:
    server = raw.get("server") or {}
    protocol = str(server.get("protocol", "http"))
    scheme = "https" if protocol in ("https", "mtls") else "http"
    host = server.get("advertised_host") or server.get("host") or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    port = int(server.get("port", 8080))
    return f"{scheme}://{host}:{port}/health"


def _probe_health(url: str, timeout: float = 5.0) -> tuple[bool, dict[str, Any] | None, str | None]:
    try:
        with httpx.Client(verify=False, timeout=timeout) as client:
            response = client.get(url)
        if response.status_code != 200:
            return False, None, f"HTTP {response.status_code}"
        try:
            body = response.json()
        except json.JSONDecodeError:
            return False, None, "invalid JSON in health response"
        return True, body, None
    except httpx.RequestError as exc:
        return False, None, str(exc)


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _inspect_service(args: argparse.Namespace) -> ServiceState:
    config_path = _config_path(args)
    raw = _load_raw_config(config_path)
    url = _health_url(raw)
    pid = _read_pid(Path(args.pid_file))
    alive = _pid_alive(pid)
    ok, body, err = _probe_health(url)
    return ServiceState(
        pid=pid,
        pid_alive=alive,
        health_ok=ok,
        health_url=url,
        health_body=body,
        health_error=err,
    )


def _format_status(state: ServiceState) -> str:
    if state.running:
        body = state.health_body or {}
        reg = body.get("proxy_registration") or (body.get("components") or {}).get(
            "proxy_registration"
        ) or {}
        registered = reg.get("registered")
        version = body.get("version", "?")
        pid_part = f"pid={state.pid}" if state.pid else "pid=unknown"
        reg_part = (
            f"registered={registered}"
            if registered is not None
            else "registered=unknown"
        )
        return (
            f"running {pid_part} health=ok url={state.health_url} "
            f"version={version} {reg_part}"
        )
    if state.pid_stale:
        return f"stopped (stale pid file: {state.pid}) health=fail url={state.health_url}"
    if state.pid_alive and not state.health_ok:
        return (
            f"unhealthy pid={state.pid} health=fail url={state.health_url} "
            f"error={state.health_error}"
        )
    return f"stopped health=fail url={state.health_url} error={state.health_error or 'no process'}"


def _wait_for_health(args: argparse.Namespace) -> ServiceState:
    deadline = time.monotonic() + STARTUP_WAIT_S
    last: ServiceState | None = None
    while time.monotonic() < deadline:
        last = _inspect_service(args)
        if last.health_ok:
            return last
        time.sleep(STARTUP_POLL_INTERVAL_S)
    return last or _inspect_service(args)


def cmd_start(args: argparse.Namespace) -> None:
    config_path = _config_path(args)
    state = _inspect_service(args)
    if state.running:
        print(_format_status(state))
        print("already running", file=sys.stderr)
        return

    raw = _load_raw_config(config_path)
    errors = AiEditorConfigValidator(config_path=config_path).validate(raw)
    if errors:
        for err in errors:
            print(getattr(err, "message", err), file=sys.stderr)
        sys.exit(1)

    pid_file = Path(args.pid_file)
    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "ai_editor.main", "--config", config_path],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            cwd=str(Path(config_path).resolve().parent),
        )
    pid_file.write_text(str(proc.pid), encoding="utf-8")

    if proc.poll() is not None:
        print("ai_editor failed to start; see log", file=sys.stderr)
        pid_file.unlink(missing_ok=True)
        sys.exit(1)

    state = _wait_for_health(args)
    if not state.health_ok:
        print(_format_status(state), file=sys.stderr)
        print("ai_editor started but health check failed; see log", file=sys.stderr)
        sys.exit(1)

    print(_format_status(state))


def cmd_stop(args: argparse.Namespace) -> None:
    pid_file = Path(args.pid_file)
    state = _inspect_service(args)

    if not state.pid_alive:
        if state.running:
            print(
                "health=ok but pid file missing or stale; "
                "stop the process manually",
                file=sys.stderr,
            )
            sys.exit(1)
        pid_file.unlink(missing_ok=True)
        print("not running")
        return

    pid = state.pid
    assert pid is not None
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        if not _pid_alive(pid):
            pid_file.unlink(missing_ok=True)
            print("stopped")
            return
        time.sleep(1)

    os.kill(pid, signal.SIGKILL)
    pid_file.unlink(missing_ok=True)
    print("killed")


def cmd_status(args: argparse.Namespace) -> None:
    state = _inspect_service(args)
    print(_format_status(state))
    if state.pid_stale:
        Path(args.pid_file).unlink(missing_ok=True)
    if not state.running:
        sys.exit(1)


def cmd_restart(args: argparse.Namespace) -> None:
    state = _inspect_service(args)
    if state.running or state.pid_alive:
        cmd_stop(args)
    cmd_start(args)


def cmd_generate_config(args: argparse.Namespace) -> None:
    gen = AiEditorConfigGenerator()
    try:
        gen.generate(args.protocol, args.out_path)
    except ConfigGenerationError as exc:
        for err in exc.errors:
            print(err, file=sys.stderr)
        sys.exit(1)
    print(f"wrote {args.out_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="aiedmgr",
        description="Manage ai_editor MCP server process and check /health.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.json (default: AI_EDITOR_CONFIG or ./config.json)",
    )
    parser.add_argument(
        "--pid-file",
        default=DEFAULT_PID,
        help=f"PID file path (default: {DEFAULT_PID})",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG,
        help=f"Log file path (default: {DEFAULT_LOG})",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start", help="Validate config, start server, wait for /health")
    sub.add_parser("stop", help="SIGTERM then SIGKILL; remove PID file")
    sub.add_parser("status", help="Report PID liveness and /health probe (exit 1 if down)")
    sub.add_parser("restart", help="stop then start")
    gen = sub.add_parser("generate-config", help="Write config.json via AiEditorConfigGenerator")
    gen.add_argument("protocol", choices=["https", "mtls"])
    gen.add_argument("out_path", help="Output config path")

    args = parser.parse_args(argv)
    handlers = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "restart": cmd_restart,
        "generate-config": cmd_generate_config,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
