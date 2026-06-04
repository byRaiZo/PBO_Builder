@echo off
setlocal
cd /d "%~dp0"
python -c "from pbobuilder.ui import PboBuilderByRaiZoApp; app=PboBuilderByRaiZoApp(); app.mainloop()"
endlocal
