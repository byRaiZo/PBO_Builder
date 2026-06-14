import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .constants import APP_TITLE, APP_VERSION
from .system import get_app_data_dir, get_subprocess_creationflags

GITHUB_OWNER = "byRaiZo"
GITHUB_REPO = "PBO_Builder"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
ASSET_PREFIX = "PBO_Builder_byRaiZo"
WINDOWS_ASSET_SUFFIX = "win64.zip"
HTTP_TIMEOUT_SECONDS = 15
SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag_name: str
    zip_name: str
    zip_url: str
    sha256_name: str
    sha256_url: str
    release_url: str


def parse_version(value):
    if not isinstance(value, str):
        return None
    match = VERSION_RE.match(value.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def normalize_version(value):
    parsed = parse_version(value)
    if not parsed:
        return ""
    return ".".join(str(part) for part in parsed)


def is_newer_version(current_version, candidate_version):
    current = parse_version(current_version)
    candidate = parse_version(candidate_version)
    if not current or not candidate:
        return False
    return candidate > current


def can_self_update(frozen=None):
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return os.name == "nt" and bool(frozen)


def http_get_bytes(url, timeout=HTTP_TIMEOUT_SECONDS):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{APP_TITLE}/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_latest_release():
    data = http_get_bytes(LATEST_RELEASE_URL)
    return json.loads(data.decode("utf-8"))


def _asset_by_name(assets, expected_name):
    expected_lower = expected_name.lower()
    for asset in assets:
        if asset.get("name", "").lower() == expected_lower:
            return asset
    return None


def _fallback_asset(assets, version, suffix):
    version_marker = "v" + version
    suffix = suffix.lower()
    for asset in assets:
        name = asset.get("name", "")
        lower_name = name.lower()
        if version_marker in lower_name and lower_name.endswith(suffix):
            return asset
    return None


def find_release_assets(release, version):
    assets = release.get("assets", [])
    zip_name = f"{ASSET_PREFIX}-v{version}-{WINDOWS_ASSET_SUFFIX}"
    sha256_name = zip_name + ".sha256"
    zip_asset = _asset_by_name(assets, zip_name) or _fallback_asset(assets, version, WINDOWS_ASSET_SUFFIX)
    sha256_asset = _asset_by_name(assets, sha256_name) or _fallback_asset(assets, version, ".zip.sha256")
    if not zip_asset or not sha256_asset:
        return None, None
    if not zip_asset.get("browser_download_url") or not sha256_asset.get("browser_download_url"):
        return None, None
    return zip_asset, sha256_asset


def release_to_update_info(release, current_version=APP_VERSION):
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag_name = release.get("tag_name", "")
    version = normalize_version(tag_name)
    if not version or not is_newer_version(current_version, version):
        return None
    zip_asset, sha256_asset = find_release_assets(release, version)
    if not zip_asset or not sha256_asset:
        return None
    return UpdateInfo(
        version=version,
        tag_name=tag_name,
        zip_name=zip_asset["name"],
        zip_url=zip_asset["browser_download_url"],
        sha256_name=sha256_asset["name"],
        sha256_url=sha256_asset["browser_download_url"],
        release_url=release.get("html_url", ""),
    )


def check_for_update(current_version=APP_VERSION, frozen=None):
    if not can_self_update(frozen):
        return None
    return release_to_update_info(fetch_latest_release(), current_version)


def updates_dir():
    path = get_app_data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_file(url, destination):
    data = http_get_bytes(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def parse_sha256_text(text):
    match = SHA256_RE.search(text or "")
    return match.group(0).lower() if match else ""


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path, expected_sha256):
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        raise UpdateError("SHA256 checksum is empty.")
    actual = file_sha256(path)
    if actual != expected:
        raise UpdateError(f"SHA256 mismatch. Expected {expected}, got {actual}.")
    return True


def download_update_package(update_info):
    package_dir = updates_dir() / f"v{update_info.version}_{int(time.time())}"
    zip_path = package_dir / update_info.zip_name
    sha_path = package_dir / update_info.sha256_name
    download_file(update_info.zip_url, zip_path)
    download_file(update_info.sha256_url, sha_path)
    expected_sha = parse_sha256_text(sha_path.read_text(encoding="utf-8", errors="ignore"))
    verify_sha256(zip_path, expected_sha)
    return zip_path


def create_updater_script(script_path):
    script = r'''
param(
    [Parameter(Mandatory=$true)][string]$ZipPath,
    [Parameter(Mandatory=$true)][string]$AppDir,
    [Parameter(Mandatory=$true)][string]$ExePath,
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [Parameter(Mandatory=$true)][string]$LogPath
)
$ErrorActionPreference = "Stop"
function Write-UpdateLog($Message) {
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -LiteralPath $LogPath -Value $line
}
try {
    Write-UpdateLog "Updater started."
    try {
        Wait-Process -Id $TargetPid -Timeout 60 -ErrorAction SilentlyContinue
    } catch {
        Write-UpdateLog "Wait-Process warning: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds 1

    $appParent = Split-Path -Parent $AppDir
    $appName = Split-Path -Leaf $AppDir
    $exeName = Split-Path -Leaf $ExePath
    $stamp = [DateTime]::UtcNow.Ticks
    $extractRoot = Join-Path (Split-Path -Parent $ZipPath) "extract_$stamp"
    $backupDir = Join-Path $appParent "$appName.backup_$stamp"

    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractRoot -Force

    $children = @(Get-ChildItem -LiteralPath $extractRoot -Force)
    if ($children.Count -eq 1 -and $children[0].PSIsContainer) {
        $newAppDir = $children[0].FullName
    } else {
        $newAppDir = $extractRoot
    }

    $newExe = Join-Path $newAppDir $exeName
    if (-not (Test-Path -LiteralPath $newExe -PathType Leaf)) {
        throw "Updated executable was not found in archive: $newExe"
    }

    Rename-Item -LiteralPath $AppDir -NewName (Split-Path -Leaf $backupDir)
    Move-Item -LiteralPath $newAppDir -Destination $AppDir
    Write-UpdateLog "Application folder replaced."

    $finalExe = Join-Path $AppDir $exeName
    Start-Process -FilePath $finalExe -WorkingDirectory $AppDir
    Write-UpdateLog "Updated application started: $finalExe"

    Remove-Item -LiteralPath $backupDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
} catch {
    Write-UpdateLog "ERROR: $($_.Exception.Message)"
    try {
        if ((-not (Test-Path -LiteralPath $AppDir)) -and (Test-Path -LiteralPath $backupDir)) {
            Rename-Item -LiteralPath $backupDir -NewName (Split-Path -Leaf $AppDir)
            Write-UpdateLog "Rollback completed."
        }
        if (Test-Path -LiteralPath $ExePath -PathType Leaf) {
            Start-Process -FilePath $ExePath -WorkingDirectory $AppDir
        }
    } catch {
        Write-UpdateLog "Rollback/start warning: $($_.Exception.Message)"
    }
    exit 1
}
'''
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script.strip() + "\n", encoding="utf-8")
    return script_path


def launch_update_installer(zip_path, app_dir=None, exe_path=None, pid=None):
    if not can_self_update(True):
        raise UpdateError("Self-update is supported only on Windows frozen builds.")
    exe = Path(exe_path or sys.executable).resolve()
    app = Path(app_dir or exe.parent).resolve()
    target_pid = int(pid or os.getpid())
    work_dir = updates_dir() / f"installer_{int(time.time())}"
    script_path = create_updater_script(work_dir / "update.ps1")
    log_path = work_dir / "update.log"
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-ZipPath",
        str(Path(zip_path).resolve()),
        "-AppDir",
        str(app),
        "-ExePath",
        str(exe),
        "-TargetPid",
        str(target_pid),
        "-LogPath",
        str(log_path),
    ]
    subprocess.Popen(
        cmd,
        cwd=str(work_dir),
        creationflags=get_subprocess_creationflags(),
        close_fds=True,
    )
    return script_path


def install_update_and_restart(update_info):
    zip_path = download_update_package(update_info)
    return launch_update_installer(zip_path)
