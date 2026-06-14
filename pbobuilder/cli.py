import argparse
import ctypes
import os
import sys

from .build import build_all
from .errors import BuildError
from .system import create_build_log_path, get_default_max_processes, load_saved_settings
from .targets import detect_addon_targets
from .tools import find_cfgconvert, find_dayz_binarize, find_dssignfile, find_p3d_obfuscator


CLI_MARKERS = {
    "-h",
    "--help",
    "-pack",
    "--pack-folder",
    "-packfolder",
    "--output-root",
    "--output-server-root",
    "--pbo-name",
    "--project-root",
    "--temp-dir",
    "--exclude-patterns",
    "--binarize-exe",
    "--cfgconvert-exe",
    "--dssignfile-exe",
    "--private-key",
    "--p3d-obfuscator-exe",
    "--max-processes",
    "-signpbo",
    "-singpbo",
    "--sign-pbo",
    "--protect-p3d",
    "--preflight",
    "--no-binarize",
    "--no-convert",
    "--no-force-rebuild",
}


def is_cli_invocation(argv):
    return any(arg.lower() in CLI_MARKERS for arg in argv)


def clean_arg(value):
    return (value or "").strip().strip('"')


def derive_output_from_pack_target(target):
    target = os.path.normpath(clean_arg(target))
    if target.lower().endswith(".pbo"):
        pbo_name = os.path.splitext(os.path.basename(target))[0]
        parent = os.path.dirname(target)
        if os.path.basename(parent).lower() == "addons":
            return os.path.dirname(parent), pbo_name
        return parent, pbo_name
    return target, ""


def first_value(*values):
    for value in values:
        value = clean_arg(str(value)) if value is not None else ""
        if value:
            return value
    return ""


def get_saved_int(settings, key, fallback):
    try:
        return int(settings.get(key) or fallback)
    except (TypeError, ValueError):
        return fallback


def open_cli_console():
    if os.name != "nt":
        return False

    kernel32 = ctypes.windll.kernel32
    if kernel32.GetConsoleWindow():
        return False
    if not kernel32.AllocConsole():
        return False

    kernel32.SetConsoleTitleW("PBO Builder(byRaiZo) - CLI build")
    sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="ignore")
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    return True


def wait_for_enter_on_error(created_console):
    if not created_console:
        return
    try:
        input("\nPress Enter to close...")
    except (EOFError, OSError):
        pass


def build_parser():
    parser = argparse.ArgumentParser(
        prog="PBO Builder(byRaiZo)",
        description="Pack DayZ addon folders from command line.",
    )
    parser.add_argument(
        "-pack",
        nargs=2,
        metavar=("SOURCE", "OUTPUT"),
        help="PBO Manager style: -pack SOURCE OUTPUT_PBO_OR_MOD_ROOT",
    )
    parser.add_argument("--pack-folder", "-packFolder", dest="pack_folder", help="Source addon folder.")
    parser.add_argument("--output-root", help="Client/mod output root. Addons and Keys are created inside it.")
    parser.add_argument("--output-server-root", help="Server output root for *_SERVER addons.")
    parser.add_argument("--pbo-name", help="Override PBO name for a single addon.")
    parser.add_argument("--project-root", help="DayZ project drive/root, default from settings or P:.")
    parser.add_argument("--temp-dir", help="Build temp folder, default from settings or output_root/.pbo_builder_temp.")
    parser.add_argument("--exclude-patterns", help="Extra exclude patterns, same format as UI.")
    parser.add_argument("--binarize-exe", help="Path to DayZ Tools Binarize.exe.")
    parser.add_argument("--cfgconvert-exe", help="Path to DayZ Tools CfgConvert.exe.")
    parser.add_argument("--dssignfile-exe", help="Path to DayZ Tools DSSignFile.exe.")
    parser.add_argument("--private-key", help="Path to .biprivatekey.")
    parser.add_argument("--p3d-obfuscator-exe", help="Path to P3DObfuscator.exe.")
    parser.add_argument("--max-processes", type=int, help="Binarize max processes.")
    parser.add_argument(
        "-signPBO",
        "-signpbo",
        "-singPBO",
        "-singpbo",
        "--sign-pbo",
        dest="sign_pbos",
        action="store_true",
    )
    parser.add_argument("--protect-p3d", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--no-binarize", action="store_true")
    parser.add_argument("--no-convert", action="store_true")
    parser.add_argument("--no-force-rebuild", action="store_true")
    return parser


def build_cli_settings(args, saved_settings=None):
    saved = saved_settings if saved_settings is not None else load_saved_settings()

    pack_source = ""
    pack_output = ""
    if args.pack:
        pack_source, pack_output = args.pack

    source_root = first_value(args.pack_folder, pack_source)
    if not source_root:
        raise BuildError("Source folder is required. Use -pack SOURCE OUTPUT or --pack-folder SOURCE.")

    derived_output_root = ""
    derived_pbo_name = ""
    if pack_output:
        derived_output_root, derived_pbo_name = derive_output_from_pack_target(pack_output)

    explicit_output_root = first_value(args.output_root, derived_output_root)
    output_root = first_value(explicit_output_root, saved.get("output_root"))
    if not output_root:
        raise BuildError("Output root is required. Use -pack SOURCE OUTPUT or --output-root PATH.")

    output_server_root = first_value(args.output_server_root)
    if not output_server_root and not explicit_output_root:
        output_server_root = first_value(saved.get("output_root_server"))
    temp_dir = first_value(args.temp_dir, saved.get("temp_dir"), os.path.join(output_root, ".pbo_builder_temp"))
    project_root = first_value(args.project_root, saved.get("project_root"), "P:")
    pbo_name = first_value(args.pbo_name, derived_pbo_name)
    output_addons_dir = os.path.join(output_root, "Addons")
    targets = detect_addon_targets(source_root, output_addons_dir)
    selected_addons = [name for name, _path in targets]

    return {
        "source_root": source_root,
        "output_root_dir": output_root,
        "output_server_root_dir": output_server_root,
        "temp_dir": temp_dir,
        "use_binarize": not args.no_binarize,
        "convert_config": not args.no_convert,
        "sign_pbos": bool(args.sign_pbos),
        "protect_p3d": bool(args.protect_p3d),
        "binarize_exe": first_value(args.binarize_exe, saved.get("binarize_exe"), find_dayz_binarize()),
        "p3d_obfuscator_exe": first_value(
            args.p3d_obfuscator_exe,
            saved.get("p3d_obfuscator_exe"),
            find_p3d_obfuscator(),
        ),
        "cfgconvert_exe": first_value(args.cfgconvert_exe, saved.get("cfgconvert_exe"), find_cfgconvert()),
        "dssignfile_exe": first_value(args.dssignfile_exe, saved.get("dssignfile_exe"), find_dssignfile()),
        "private_key": first_value(args.private_key, saved.get("private_key")),
        "exclude_patterns": first_value(args.exclude_patterns, saved.get("exclude_patterns")),
        "project_root": project_root,
        "pbo_name": pbo_name,
        "max_processes": args.max_processes or get_saved_int(
            saved,
            "max_processes",
            get_default_max_processes(),
        ),
        "selected_addons": selected_addons,
        "force_rebuild": not args.no_force_rebuild,
        "preflight_before_build": bool(args.preflight),
        "log_file": str(create_build_log_path()),
    }


def run_cli(argv=None):
    created_console = open_cli_console()
    parser = build_parser()
    log_file = None

    try:
        args = parser.parse_args(argv)
        settings = build_cli_settings(args)
        log_path = settings["log_file"]
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_file = open(log_path, "w", encoding="utf-8")

        def log(message):
            print(message)
            log_file.write(str(message) + "\n")
            log_file.flush()

        def progress(current, total):
            log(f"Progress: {current}/{total}")

        log("CLI build started.")
        log(f"Log file: {log_path}")
        build_all(settings, log, progress)
        log("CLI build completed.")
        return 0
    except BuildError as error:
        message = f"ERROR: {error}"
        print(message, file=sys.stderr)
        if log_file is not None:
            log_file.write(message + "\n")
            log_file.flush()
        wait_for_enter_on_error(created_console)
        return 1
    except Exception as error:
        message = f"ERROR: Unexpected CLI failure: {error}"
        print(message, file=sys.stderr)
        if log_file is not None:
            log_file.write(message + "\n")
            log_file.flush()
        wait_for_enter_on_error(created_console)
        return 1
    finally:
        if log_file is not None:
            log_file.close()
