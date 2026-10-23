"""Write clearly fictitious captures for a screenshot/demo profile.

Example:
  XDG_DATA_HOME=/tmp/envlens-demo/data \
  XDG_STATE_HOME=/tmp/envlens-demo/state \
  PYTHONPATH=src /usr/bin/python3 tools/create_example_captures.py
Then open the app with the same XDG_DATA_HOME and XDG_STATE_HOME.
"""
from envlens.snapshots import capture, save

TERMINAL = {
    "PATH": "/home/demo/project/.venv/bin:/usr/bin:/bin",
    "PWD": "/home/demo/project",
    "HOME": "/home/demo",
    "SHELL": "/bin/bash",
    "VIRTUAL_ENV": "/home/demo/project/.venv",
    "LANG": "en_US.UTF-8",
    "API_TOKEN": "fictional-terminal-token",
}
IDE = {
    "PATH": "/usr/bin:/bin",
    "PWD": "/home/demo/project",
    "HOME": "/home/demo",
    "SHELL": "/bin/bash",
    "PYTHONPATH": "/workspace/source",
    "NODE_OPTIONS": "--trace-warnings",
    "LANG": "en_US.UTF-8",
    "API_TOKEN": "fictional-ide-token",
}


for label, variables in (("Terminal (example)", TERMINAL), ("IDE task (example)", IDE)):
    raw = b"\0".join(f"{name}={value}".encode() for name, value in variables.items()) + b"\0"
    saved = save(capture(raw, label, cwd=variables["PWD"], shell=variables["SHELL"]))
    print(f"Saved fictional {label} capture: {saved}")
