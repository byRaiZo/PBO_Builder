"""Compatibility entry point for PBO Builder(byRaiZo)."""

import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    from pbobuilder.cli import is_cli_invocation, run_cli

    if is_cli_invocation(argv):
        return run_cli(argv)

    try:
        from pbobuilder.qt_ui import run_qt_app
    except Exception:
        run_qt_app = None
    from pbobuilder.ui import PboBuilderByRaiZoApp

    if run_qt_app is not None:
        return run_qt_app()
    app = PboBuilderByRaiZoApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
