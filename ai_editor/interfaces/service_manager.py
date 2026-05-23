"""Service manager CLI for ai_editor — start / stop / restart / status / generate-config."""
from __future__ import annotations

import argparse
import json
import os
import re
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


def _server_bind_addr(raw: dict[str, Any]) -> tuple[str, int]:
    server = raw.get("server") or {}
    host = str(server.get("host") or "127.0.0.1")
    port = int(server.get("port", 8080))
    return host, port


def _find_listener_pid(host: str, port: int) -> int | None:
    """Return PID listening on host:port, or None if not found."""
    addr = f"{host}:{port}"
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _find_listener_pid_lsof(host, port)
    for line in result.stdout.splitlines():
        if addr not in line:
            continue
        match = re.search(r"pid=(\d+)", line)
        if match:
            return int(match.group(1))
    return _find_listener_pid_lsof(host, port)


def _find_listener_pid_lsof(host: str, port: int) -> int | None:
    try:
        result = subprocess.run(
            ["lsof", "-i", f"TCP@{host}:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def _read_proc_args(pid: int) -> list[str]:
    cmdline_path = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = cmdline_path.read_bytes()
    except OSError:
        return []
    return [part.decode() for part in raw.split(b"\x00") if part]


def _config_path_matches_cmdline(config_path: str, args: list[str]) -> bool:
    if not args:
        return False
    try:
        module_idx = args.index("-m")
    except ValueError:
        return False
    if module_idx + 1 >= len(args) or args[module_idx + 1] != "ai_editor.main":
        return False
    try:
        config_idx = args.index("--config")
    except ValueError:
        return False
    if config_idx + 1 >= len(args):
        return False
    proc_config = args[config_idx + 1]
    resolved = str(Path(config_path).resolve())
    rel = str(Path(config_path))
    if proc_config in {resolved, rel}:
        return True
    if not Path(config_path).is_absolute() and proc_config == Path(config_path).name:
        return True
    return False


def _find_pids_for_config(config_path: str) -> list[int]:
    """PIDs for ai_editor.main using the same config (Linux /proc scan)."""
    pids: list[int] = []
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return pids
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        args = _read_proc_args(int(entry.name))
        if _config_path_matches_cmdline(config_path, args):
            pids.append(int(entry.name))
    return sorted(set(pids))


def _resolve_stop_pids(args: argparse.Namespace, state: ServiceState) -> list[int]:
    """Choose PIDs to terminate: PID file, then listener port, then config scan."""
    if state.pid_alive and state.pid is not None:
        return [state.pid]

    config_path = _config_path(args)
    raw = _load_raw_config(config_path)
    host, port = _server_bind_addr(raw)
    discovered: list[int] = []

    if state.running:
        listener = _find_listener_pid(host, port)
        if listener is not None:
            discovered.append(listener)
        for pid in _find_pids_for_config(config_path):
            if pid not in discovered:
                discovered.append(pid)

    return discovered


def _terminate_pids(pids: list[int], pid_file: Path) -> None:
    if not pids:
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue

    for _ in range(30):
        alive = [pid for pid in pids if _pid_alive(pid)]
        if not alive:
            pid_file.unlink(missing_ok=True)
            print("stopped")
            return
        time.sleep(1)

    for pid in pids:
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                continue
    pid_file.unlink(missing_ok=True)
    print("killed")


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
    pids = _resolve_stop_pids(args, state)

    if not pids:
        pid_file.unlink(missing_ok=True)
        print("not running")
        return

    if state.running and not state.pid_alive:
        print(
            f"health=ok but pid file missing or stale; "
            f"stopping discovered pid(s): {', '.join(map(str, pids))}",
            file=sys.stderr,
        )

    _terminate_pids(pids, pid_file)


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
