import sys

if len(sys.argv) > 1:
    from .cli import main
    raise SystemExit(main())

from .app import run
raise SystemExit(run())
