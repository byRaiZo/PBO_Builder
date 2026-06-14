# PBO Builder(byRaiZo)

DayZ PBO build helper for packing addon folders into release-ready PBO files.

## What It Does

- Builds one addon folder or multiple selected addon subfolders.
- Binarizes all P3D models with DayZ Tools `binarize.exe`.
- Refuses to pack source/non-ODOL P3D files into release PBOs.
- Converts `config.cpp` to `config.bin` with `CfgConvert.exe`.
- Converts text `.rvmat` files to binary `raP`.
- Preserves config-referenced `_damage.rvmat` and `_destruct.rvmat` files.
- Generates `texHeaders.bin` with `binarize.exe -texheaders`.
- Packs PBO files with `product=dayz ugc` and addon `prefix`.
- Optionally signs PBOs with `DSSignFile.exe` and copies the matching `.bikey`.
- Uses a build cache and content-safe file hashing to skip unchanged addons.

## Run

Default modern Qt UI:

```bat
run_pbo_builder_byraizo.bat
```

or:

```powershell
python main.py
```

Legacy Tkinter UI fallback:

```bat
run_pbo_builder_byraizo_legacy_tk.bat
```

## Source Layout

```text
main.py                         App entry point
pbo_builder_byraizo.py          Compatibility launcher
pbobuilder/qt_ui.py             Modern PySide6/Qt UI
pbobuilder/constants.py         App metadata, defaults, colors, shared constants
pbobuilder/errors.py            BuildError
pbobuilder/system.py            AppData, settings/cache/log files, subprocess helpers
pbobuilder/filters.py           Exclude rules, protected files, P3D/PAA detection
pbobuilder/files.py             Hashing, staging, temp cleanup, safety checks
pbobuilder/tools.py             DayZ Tools calls: Binarize, texHeaders, CfgConvert
pbobuilder/pbo.py               PBO packing, signing, output publish/rollback
pbobuilder/targets.py           Addon detection, prefix/name resolution, build hash
pbobuilder/preflight.py         Config/reference/path preflight checks
pbobuilder/build.py             End-to-end build pipeline
pbobuilder/ui.py                Legacy Tkinter UI
```

## Python Dependency

The modern UI uses PySide6:

```powershell
pip install -r requirements.txt
```

## Required Tools

Install DayZ Tools and point the app to:

- `Binarize.exe`
- `CfgConvert.exe`
- `DSSignFile.exe`, only when signing is enabled
- `.biprivatekey`, only when signing is enabled

The default project root is `P:`.

## Output Layout

The selected output root receives:

```text
Addons\<addon>.pbo
Addons\<addon>.*.bisign
Keys\<key>.bikey
```

## Auto Update Releases

Auto update checks GitHub Releases for `byRaiZo/PBO_Builder`.

Create a SemVer tag and push it:

```powershell
git tag v1.0.1
git push origin main --tags
```

GitHub Actions will build the PyInstaller one-folder app, create both assets,
and publish a GitHub Release:

```text
PBO_Builder_byRaiZo-v1.0.1-win64.zip
PBO_Builder_byRaiZo-v1.0.1-win64.zip.sha256
```

The zip must contain the full PyInstaller one-folder build:

```text
PBO Builder(byRaiZo)\
```

## Notes

Settings, cache, logs, and temporary signing data are stored separately from the
old prototype under:

```text
%LOCALAPPDATA%\PBO_Builder_byRaiZo
```

Build temp folders use a dedicated marker file named:

```text
.pbo_builder_byraizo_temp
```
