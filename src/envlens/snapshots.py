"""Private, bounded environment captures with comparison-only secret storage."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time
import uuid


def data_dir() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "envlens" / "captures"


def state_dir() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return root / "envlens"


_SECRET_KEY = re.compile(
    r"(^|_)(secret|token|password|passwd|credential|private.?key|api.?key|auth|cookie)(_|$)|"
    r"^(AWS_SECRET|AWS_SESSION|GITHUB_TOKEN|GH_TOKEN|GPG_AGENT_INFO)$",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/-]+=*|gh[pousr]_[a-z0-9]{20,}|"
    r"github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
MAX_CAPTURE_BYTES = 1024 * 1024
MAX_ENV_ITEMS = 4096
MAX_VALUE_BYTES = 64 * 1024
MAX_SNAPSHOTS = 100


class CaptureError(ValueError):
    pass


def _key() -> bytes:
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / "fingerprint.key"
    try:
        value = path.read_bytes()
        if len(value) == 32:
            return value
    except FileNotFoundError:
        pass
    value = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    return value


def _secret_fingerprint(key: bytes, name: str, value: str) -> str:
    return hmac.new(key, (name + "\0" + value).encode("utf-8", "surrogateescape"), hashlib.sha256).hexdigest()


def parse_environment(raw: bytes) -> dict[str, str]:
    if len(raw) > MAX_CAPTURE_BYTES:
        raise CaptureError("Capture exceeds 1 MiB; refusing to save it")
    result: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        if b"=" not in item:
            continue
        key_bytes, value_bytes = item.split(b"=", 1)
        try:
            name = key_bytes.decode("utf-8", "replace")
            value = value_bytes.decode("utf-8", "replace")
        except UnicodeDecodeError:
            continue
        if not name or len(name) > 256 or len(value_bytes) > MAX_VALUE_BYTES:
            continue
        if any(ord(char) < 32 and char not in "\t" for char in name):
            continue
        result[name] = value
        if len(result) > MAX_ENV_ITEMS:
            raise CaptureError("Capture contains more than 4,096 variables")
    return result


def capture(raw: bytes, label: str, *, cwd: str | None = None, shell: str | None = None) -> dict:
    label = " ".join(label.strip().split())
    if not label or len(label) > 80:
        raise CaptureError("Give this capture a name of 1–80 characters")
    env = parse_environment(raw)
    key = _key()
    entries: dict[str, dict[str, str | bool]] = {}
    home = str(Path.home())
    for name, value in sorted(env.items(), key=lambda entry: entry[0].casefold()):
        sensitive = bool(_SECRET_KEY.search(name) or _SECRET_VALUE.search(value))
        if sensitive:
            entries[name] = {"secret": True, "fingerprint": _secret_fingerprint(key, name, value)}
        else:
            # A home directory in a path is useful to compare locally and should
            # not unnecessarily reveal the account name in a shared report.
            if home and value.startswith(home):
                value = "~" + value[len(home):]
            entries[name] = {"secret": False, "value": value}
    record = {
        "schema": 1,
        "id": uuid.uuid4().hex,
        "label": label,
        "captured_at": time.time(),
        "cwd": _redact_path(cwd or env.get("PWD") or os.getcwd()),
        "shell": Path(shell or env.get("SHELL", "unknown")).name,
        "count": len(entries),
        "redacted_count": sum(bool(value["secret"]) for value in entries.values()),
        "variables": entries,
    }
    return record


def _redact_path(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home):] if home and path.startswith(home) else path


def save(record: dict) -> Path:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / f"{record['captured_at']:.6f}-{record['id']}.json"
    payload = json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    prune(directory)
    return path


def prune(directory: Path | None = None) -> None:
    files = sorted((directory or data_dir()).glob("*.json"), reverse=True)
    for old in files[MAX_SNAPSHOTS:]:
        try:
            old.unlink()
        except OSError:
            pass


def load_all() -> list[dict]:
    directory = data_dir()
    if not directory.exists():
        return []
    result = []
    for path in sorted(directory.glob("*.json"), reverse=True)[:MAX_SNAPSHOTS]:
        try:
            if path.stat().st_size > 2 * MAX_CAPTURE_BYTES:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema") == 1 and isinstance(data.get("variables"), dict):
                data["_path"] = str(path)
                result.append(data)
        except (OSError, ValueError, TypeError):
            continue
    return result


def remove(record: dict) -> None:
    path = Path(record.get("_path", ""))
    if path.parent == data_dir() and path.suffix == ".json":
        path.unlink(missing_ok=True)


def compare(left: dict, right: dict) -> list[tuple[str, str, str, str]]:
    """Return rows: variable, status, left value, right value."""
    a, b = left["variables"], right["variables"]
    rows = []
    for name in sorted(a.keys() | b.keys(), key=str.casefold):
        if name not in a:
            rows.append((name, "added", "—", _display(b[name])))
        elif name not in b:
            rows.append((name, "missing", _display(a[name]), "—"))
        else:
            av, bv = a[name], b[name]
            if av.get("secret") or bv.get("secret"):
                same = av.get("secret") and bv.get("secret") and hmac.compare_digest(
                    str(av.get("fingerprint", "")), str(bv.get("fingerprint", ""))
                )
                rows.append((name, "same secret" if same else "secret differs", "••••••", "••••••"))
            elif av.get("value") == bv.get("value"):
                rows.append((name, "same", str(av.get("value", "")), str(bv.get("value", ""))))
            else:
                rows.append((name, "changed", str(av.get("value", "")), str(bv.get("value", ""))))
    return rows


def _display(value: dict) -> str:
    return "••••••" if value.get("secret") else str(value.get("value", ""))
