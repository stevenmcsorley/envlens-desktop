"""Capture a shell environment through a tiny shell-agnostic stdin helper."""
import argparse
import sys

from .snapshots import CaptureError, capture, save


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="envlens",
        description="Capture the environment of the current shell for visual comparison.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    command = sub.add_parser("capture", help="save a NUL-delimited environment from stdin")
    command.add_argument("--label", required=True, help="context name shown in EnvLens")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        record = capture(raw, args.label)
        path = save(record)
    except (CaptureError, OSError) as exc:
        print(f"envlens: {exc}", file=sys.stderr)
        return 1
    print(
        f"Saved {record['label']}: {record['count']} variables "
        f"({record['redacted_count']} secret values fingerprinted, never stored)"
    )
    print(f"Open EnvLens to compare this capture. Private file: {path}")
    return 0
