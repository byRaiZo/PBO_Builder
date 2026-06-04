try:
    from pbobuilder.qt_ui import run_qt_app
except Exception:
    run_qt_app = None
from pbobuilder.ui import PboBuilderByRaiZoApp


def main():
    if run_qt_app is not None:
        return run_qt_app()
    app = PboBuilderByRaiZoApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
