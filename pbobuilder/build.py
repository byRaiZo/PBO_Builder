import fnmatch
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .constants import *
from .errors import BuildError
from .files import *
from .filters import *
from .pbo import *
from .preflight import run_preflight_for_targets
from .system import load_build_cache, save_build_cache, get_available_logical_threads
from .targets import *
from .tools import *

def build_all(settings, log, progress_callback):
    start_time = time.time()
    source_root = os.path.normpath(settings["source_root"])
    output_client_root_dir = os.path.normpath(settings["output_root_dir"])
    output_server_root_raw = settings.get("output_server_root_dir", "")
    output_server_root_dir = os.path.normpath(output_server_root_raw) if output_server_root_raw else output_client_root_dir
    output_client_addons_dir = os.path.join(output_client_root_dir, "Addons")
    output_client_keys_dir = os.path.join(output_client_root_dir, "Keys")
    output_server_addons_dir = os.path.join(output_server_root_dir, "Addons")
    output_server_keys_dir = os.path.join(output_server_root_dir, "Keys")
    temp_root = os.path.normpath(settings["temp_dir"])
    if not os.path.isdir(source_root):
        raise BuildError(f"Source root is not a directory: {source_root}")
    os.makedirs(output_client_addons_dir, exist_ok=True)
    os.makedirs(output_client_keys_dir, exist_ok=True)
    os.makedirs(output_server_addons_dir, exist_ok=True)
    os.makedirs(output_server_keys_dir, exist_ok=True)
    ensure_builder_temp_root(temp_root, log, source_root, output_client_root_dir)
    if output_server_root_dir != output_client_root_dir:
        ensure_builder_temp_root(temp_root, None, source_root, output_server_root_dir)

    use_binarize = settings["use_binarize"]
    convert_config = settings["convert_config"]
    sign_pbos = settings["sign_pbos"]
    protect_p3d = bool(settings.get("protect_p3d", False))
    binarize_exe = settings["binarize_exe"]
    p3d_obfuscator_exe = settings.get("p3d_obfuscator_exe", "")
    cfgconvert_exe = settings["cfgconvert_exe"]
    dssignfile_exe = settings["dssignfile_exe"]
    private_key = settings["private_key"]
    exclude_patterns = settings["exclude_patterns"]
    exclude_pattern_list = parse_exclude_patterns(exclude_patterns)
    project_root = settings["project_root"]
    pbo_name = settings["pbo_name"]
    max_processes = settings["max_processes"]
    selected_addons = set(settings.get("selected_addons", []))
    needs_signing_tools = sign_pbos and any(not name.upper().endswith("_SERVER") for name in selected_addons)
    force_rebuild = bool(settings.get("force_rebuild", False))
    preflight_before_build = bool(settings.get("preflight_before_build", False))
    content_safe_cache = True
    exclude_file = ""

    log(f"Output root client:   {output_client_root_dir}")
    log(f"Output client Addons: {output_client_addons_dir}")
    log(f"Output client Keys:   {output_client_keys_dir}")
    log(f"Output root server:   {output_server_root_dir}")
    log(f"Output server Addons: {output_server_addons_dir}")
    log(f"Output server Keys:   {output_server_keys_dir}")
    if force_rebuild:
        log(f"Force rebuild enabled. Only selected addon temp folders will be refreshed: {temp_root}")
    else:
        log(f"Force rebuild disabled. Keeping existing temp folder contents: {temp_root}")
    log("Content-safe checks enabled internally. File contents are hashed for cache/staging checks.")
    log("Using per-build SHA1 cache for repeated file fingerprints. Source hashes are not persisted across runs.")
    log(f"Detected total logical CPU threads: {os.cpu_count() or 'unknown'}")
    log(f"Detected available logical threads: {get_available_logical_threads()}")
    log(f"Configured Binarize max processes: {max_processes}")

    if use_binarize:
        if not binarize_exe or not os.path.isfile(binarize_exe):
            raise BuildError("binarize.exe not found. Select the DayZ Tools binarize.exe path.")
        log(f"Using binarize.exe: {binarize_exe}")
        exclude_file = create_temp_exclude_file(temp_root, exclude_patterns, log)
        if exclude_file:
            log(f"Using generated exclude file: {exclude_file}")
        else:
            log("No exclude file will be passed to Binarize. Binarize uses the filtered staging folder instead.")

    if protect_p3d:
        if not use_binarize:
            raise BuildError("P3D protection requires Binarize P3D to be enabled.")
        if not p3d_obfuscator_exe or not os.path.isfile(p3d_obfuscator_exe):
            raise BuildError("P3DObfuscator.exe not found. Select the P3DObfuscator.exe path.")
        log(f"Using P3DObfuscator.exe: {p3d_obfuscator_exe}")

    if convert_config:
        if not cfgconvert_exe or not os.path.isfile(cfgconvert_exe):
            raise BuildError("CfgConvert.exe not found. Select the DayZ Tools CfgConvert.exe path.")
        log(f"Using CfgConvert.exe: {cfgconvert_exe}")

    if needs_signing_tools:
        if not dssignfile_exe or not os.path.isfile(dssignfile_exe):
            raise BuildError("DSSignFile.exe not found. Select the DayZ Tools DSSignFile.exe path.")
        if not private_key or not os.path.isfile(private_key):
            raise BuildError("Private key not found. Select your .biprivatekey file.")
        log(f"Using DSSignFile.exe: {dssignfile_exe}")
        log(f"Using private key: {os.path.basename(private_key)}")
    elif sign_pbos:
        log("Signing enabled, but selected targets are server-only. Server output PBOs will not be signed.")

    all_targets = detect_addon_targets(source_root, output_client_addons_dir)
    targets = [(name, path) for name, path in all_targets if name in selected_addons] if selected_addons else []
    if not targets:
        raise BuildError("No addon targets selected.")
    log(f"Found {len(all_targets)} addon target(s). Selected {len(targets)} for build.")

    if preflight_before_build:
        log("Preflight before build enabled. Running checks before packing.")
        preflight_result = run_preflight_for_targets(settings, targets, log, progress_callback)
        if preflight_result.errors > 0:
            raise BuildError(f"Preflight failed with {preflight_result.errors} error(s). Build aborted.")
        if preflight_result.warnings > 0:
            log(f"Preflight completed with {preflight_result.warnings} warning(s). Continuing build.")
        else:
            log("Preflight completed without errors or warnings. Continuing build.")

    if force_rebuild:
        log("Force rebuild enabled. Cache will be ignored for selected addons.")

    cache = load_build_cache()
    build_hash_cache = {}
    cache_key_root = os.path.abspath(source_root).lower()
    source_cache = cache.setdefault(cache_key_root, {})
    summary = {
        "built": 0,
        "skipped": 0,
        "signed": 0,
        "failed": 0,
        "keys_copied": 0,
        "p3d_recovered": 0,
        "targets": len(targets),
        "log_file": settings.get("log_file", ""),
    }
    build_jobs = []

    for index, (folder_name, folder_path) in enumerate(targets, start=1):
        progress_callback(index - 1, len(targets))
        log("")
        log("=" * 80)
        log(f"Preparing addon {index}/{len(targets)}: {folder_name}")
        log("=" * 80)
        pbo_base_name = get_pbo_base_name(folder_name, pbo_name, len(targets))
        is_server_addon = folder_name.upper().endswith("_SERVER")
        target_addons_dir = output_server_addons_dir if is_server_addon else output_client_addons_dir
        target_keys_dir = output_server_keys_dir if is_server_addon else output_client_keys_dir
        target_kind = "server" if is_server_addon else "client"
        should_sign_output = sign_pbos and not is_server_addon
        output_pbo = os.path.join(target_addons_dir, pbo_base_name + ".pbo")
        prefix = get_pbo_prefix(pbo_base_name, folder_path)
        state_hash = compute_addon_state_hash(folder_path, prefix, settings, exclude_pattern_list, build_hash_cache)
        cache_entry = source_cache.get(folder_name, {})
        signature_exists = bool(find_new_signature_for_pbo(output_pbo))
        can_skip = (
            not force_rebuild
            and cache_entry.get("hash") == state_hash
            and os.path.isfile(output_pbo)
            and (not should_sign_output or signature_exists)
        )
        if can_skip:
            log(f"Skipping {folder_name} - no changes detected.")
            summary["skipped"] += 1
            continue

        addon_temp_root = get_addon_temp_root(temp_root, folder_name)
        if force_rebuild:
            for temp_subfolder in ["staging", "binarized", "textures", "configs"]:
                selected_temp_path = os.path.join(addon_temp_root, temp_subfolder)
                if os.path.isdir(selected_temp_path):
                    shutil.rmtree(selected_temp_path)
                    log(f"Force rebuild: removed selected addon temp folder only: {selected_temp_path}")

        pack_source = folder_path
        folder_has_p3d = use_binarize and has_p3d_files(folder_path, exclude_pattern_list)
        # Binarize also generates texHeaders.bin. Keep that output in staging so
        # source folders are never modified during a build.
        needs_staging = convert_config or use_binarize
        staging_dir = ""
        binarized_dir = ""
        if needs_staging:
            staging_dir = os.path.join(addon_temp_root, "staging")
            log("Copying source to staging folder...")
            copy_source_to_staging(folder_path, staging_dir, exclude_pattern_list, log, content_safe_cache)
            pack_source = staging_dir
        if folder_has_p3d:
            binarized_dir = os.path.join(addon_temp_root, "binarized")
        elif use_binarize:
            log("No P3D files found. Skipping P3D binarize for this addon.")
        output_work_dir = create_output_work_dir(output_pbo, folder_name)
        temp_output_pbo = os.path.join(output_work_dir, os.path.basename(output_pbo))

        binarize_source = staging_dir if folder_has_p3d and staging_dir else folder_path

        build_jobs.append({
            "folder_name": folder_name,
            "folder_path": folder_path,
            "output_pbo": output_pbo,
            "output_kind": target_kind,
            "output_keys_dir": target_keys_dir,
            "sign_output": should_sign_output,
            "temp_output_pbo": temp_output_pbo,
            "output_work_dir": output_work_dir,
            "prefix": prefix,
            "pack_source": pack_source,
            "folder_has_p3d": folder_has_p3d,
            "staging_dir": staging_dir,
            "binarized_dir": binarized_dir,
            "binarize_source": binarize_source,
            "state_hash": state_hash,
        })

    for build_index, job in enumerate(build_jobs, start=1):
        progress_callback(build_index - 1, len(build_jobs))
        folder_name = job["folder_name"]
        log("")
        log("=" * 80)
        log(f"Packing addon {build_index}/{len(build_jobs)}: {folder_name}")
        log("=" * 80)
        log(f"Output target: {job['output_kind']}")
        try:
            if use_binarize and job["folder_has_p3d"]:
                non_binarized_p3ds = collect_non_binarized_p3ds(job["staging_dir"], exclude_pattern_list)
                if non_binarized_p3ds:
                    binarize_input_dir, skipped_odol = create_binarize_source_without_odol(
                        job["binarize_source"],
                        temp_root,
                        folder_name,
                        log,
                        exclude_pattern_list,
                    )
                    if skipped_odol:
                        log(f"Binarize will skip {skipped_odol} already-ODOL P3D file(s).")

                    log("Running Binarize against dependency-isolated staging workspace...")
                    run_dayz_binarize(
                        source_dir=binarize_input_dir,
                        binarized_output_dir=job["binarized_dir"],
                        binarize_exe=binarize_exe,
                        project_root=project_root,
                        temp_dir=temp_root,
                        max_processes=max_processes,
                        exclude_file=exclude_file,
                        log=log,
                        addon_name=folder_name,
                    )
                    log("Overlaying binarized files onto staging folder...")
                    overlay_tree(job["binarized_dir"], job["staging_dir"])
                    p3d_recovered_count = ensure_p3d_files_in_staging(
                        job["folder_path"],
                        job["staging_dir"],
                        log,
                        exclude_pattern_list,
                    )

                    if p3d_recovered_count > 0:
                        summary["p3d_recovered"] += p3d_recovered_count

                    ensure_all_p3ds_binarized_in_staging(
                        staging_dir=job["staging_dir"],
                        binarize_exe=binarize_exe,
                        project_root=project_root,
                        temp_dir=temp_root,
                        max_processes=max_processes,
                        exclude_file=exclude_file,
                        log=log,
                        addon_name=folder_name,
                        extra_patterns=exclude_pattern_list,
                    )
                else:
                    log("All included P3D files are already ODOL. Skipping P3D Binarize for this addon.")

                if protect_p3d:
                    run_p3d_obfuscator_for_staging(
                        job["staging_dir"],
                        p3d_obfuscator_exe,
                        log,
                        exclude_pattern_list,
                    )

            if convert_config:
                ensure_config_cpp_files_in_staging(job["folder_path"], job["pack_source"], log, exclude_pattern_list)
                run_cfgconvert_rvmats_to_bin(job["pack_source"], cfgconvert_exe, log, exclude_pattern_list)
                run_cfgconvert_to_bin(job["pack_source"], cfgconvert_exe, log, exclude_pattern_list)

            if use_binarize:
                run_dayz_texheaders(
                    source_dir=job["pack_source"],
                    binarize_exe=binarize_exe,
                    project_root=project_root,
                    temp_dir=temp_root,
                    max_processes=max_processes,
                    exclude_file=exclude_file,
                    log=log,
                    addon_name=folder_name,
                )
            else:
                log("Binarize disabled. Skipping texture headers generation.")

            log(f"PBO name:   {os.path.basename(job['output_pbo'])}")
            log(f"PBO prefix: {job['prefix']}")
            pack_pbo(job["pack_source"], job["temp_output_pbo"], job["prefix"], log, exclude_pattern_list)
            verify_packed_pbo(job["temp_output_pbo"], job["prefix"], log)
            if job["sign_output"]:
                wait_for_file_ready(job["temp_output_pbo"], log)
                run_dssignfile(dssignfile_exe, private_key, job["temp_output_pbo"], log)
                summary["signed"] += 1
            elif sign_pbos and job["output_kind"] == "server":
                log("Signing skipped for server output target.")

            replace_output_artifacts(job["temp_output_pbo"], job["output_pbo"], job["sign_output"], log)
            verify_published_output(job["output_pbo"], job["sign_output"], log)
            summary["built"] += 1

            if job["sign_output"]:
                copied_key = copy_bikey_to_keys(private_key, job["output_keys_dir"], log)
                if copied_key:
                    summary["keys_copied"] += 1
            source_cache[folder_name] = {
                "hash": job["state_hash"],
                "pbo": job["output_pbo"],
                "updated": datetime.now().isoformat(timespec="seconds"),
            }
            save_build_cache(cache)
        except Exception:
            summary["failed"] += 1
            raise
        finally:
            cleanup_output_work_dir(job["output_work_dir"], log)

    progress_callback(len(targets), len(targets))
    save_build_cache(cache)
    elapsed = time.time() - start_time
    summary["elapsed"] = elapsed
    log("")
    log("=" * 80)
    log("Build summary")
    log("=" * 80)
    log(f"Targets:       {summary['targets']}")
    log(f"Built:         {summary['built']}")
    log(f"Skipped:       {summary['skipped']}")
    log(f"Signed:        {summary['signed']}")
    log(f"Keys copied:   {summary['keys_copied']}")
    log(f"P3D recovered: {summary['p3d_recovered']}")
    log(f"Failed:        {summary['failed']}")
    log(f"Time:          {format_duration(elapsed)}")
    if summary.get("log_file"):
        log(f"Log:         {summary['log_file']}")
    log("=" * 80)
    log("")
    log("Build finished.")
    return summary
