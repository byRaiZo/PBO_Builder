import copy
import html
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .build import build_all
from .constants import *
from .errors import BuildError
from .files import clear_full_temp_folder, clear_temp_folder
from .pbo import find_new_signature_for_pbo
from .preflight import PREFLIGHT_CHECK_DEFAULTS, run_preflight_for_targets
from .system import (
    create_build_log_path,
    get_cache_file_path,
    get_default_max_processes,
    get_initial_dir_from_value,
    get_logs_dir,
    is_safe_window_geometry,
    load_build_cache,
    load_saved_settings,
    save_build_cache,
    save_saved_settings,
)
from .targets import detect_addon_targets
from .tools import find_cfgconvert, find_dayz_binarize, find_dssignfile, find_p3d_obfuscator
from .updater import check_for_update, install_update_and_restart


ASSETS_DIR = Path(__file__).parent / "assets"
DEFAULT_LANGUAGE = "ru"

TRANSLATIONS = {
    "en": {
        "settings": "Settings",
        "tools": "Tools",
        "language": "Language",
        "english": "English",
        "russian": "Russian",
        "private_key": "Private key",
        "project_root": "Project root",
        "temp_dir": "Temp dir",
        "max_processes": "Max processes",
        "exclude_patterns": "Exclude patterns",
        "logs": "Logs",
        "preflight_checks": "Preflight checks",
        "check_cfgpatches": "CfgPatches",
        "check_required_addons": "requiredAddons[]",
        "check_cfgmods": "CfgMods scripts",
        "check_references": "Text references",
        "check_p3d_internal": "P3D internal refs",
        "check_case_conflicts": "Case conflicts",
        "check_risky_paths": "Risky paths",
        "check_prefix": "PBO prefix",
        "check_terrain_wrp": "Terrain / WRP",
        "check_navmesh": "Navmesh",
        "check_road_shapes": "Road shapes",
        "check_terrain_layers": "Terrain layers",
        "check_source_exports": "Source/export warnings",
        "check_terrain_size": "Terrain size",
        "clear_logs": "Clear logs",
        "logs_folder": "Logs folder",
        "cancel": "Cancel",
        "save": "Save",
        "paths": "Paths",
        "ready": "Ready",
        "about": "About",
        "source_root": "Source root",
        "output_root_client": "Output root client",
        "output_root_server": "Output root server",
        "pbo_name": "PBO name",
        "pbo_name_placeholder": "Optional for single addon",
        "pipeline": "Pipeline",
        "binarize_p3d": "Binarize P3D",
        "protect_p3d": "Protect P3D",
        "cpp_rvmat_to_bin": "CPP/RVMAT to BIN",
        "sign_pbos": "Sign PBOs",
        "force_rebuild": "Force rebuild",
        "preflight_before_build": "Preflight before build",
        "actions": "Actions",
        "build_pbos": "Build PBOs",
        "preflight": "Preflight",
        "clear_all_temp": "Clear all temp",
        "clear_cache": "Clear cache",
        "latest_log": "Latest log",
        "addons": "Addons",
        "refresh": "Refresh",
        "all": "All",
        "none": "None",
        "open": "Open",
        "browse": "Browse",
        "add_path": "Add {label}",
        "remove_path": "Remove selected {label}",
        "add_path_title": "Add {label}",
        "language_restart": "Language will be applied after restart.",
        "cannot_clear_logs": "Cannot clear logs while a build is running.",
        "logs_empty": "Logs folder is already empty.",
        "logs_cleared": "Logs folder cleared. Deleted {count} file(s).",
        "logs_clear_partial": "Deleted {count} log file(s), but some files could not be removed:\n\n{details}",
        "no_build_logs": "No build logs found yet.",
        "path_empty": "Path is empty.",
        "path_missing": "Path does not exist: {path}",
        "field_empty": "{label} is empty.",
        "field_missing": "{label} does not exist: {path}",
        "select_source_root": "Select a source root folder.",
        "source_root_missing": "Source root does not exist: {path}",
        "select_addon_check": "Select at least one addon to check.",
        "select_addon_build": "Select at least one addon to build.",
        "no_selected_targets": "No selected addon targets found.",
        "select_output_client": "Select an output root client folder.",
        "select_output_server": "Select an output root server folder for _SERVER addons.",
        "pbo_override_single": "PBO name override can only be used when exactly one addon is selected.",
        "select_required": "Select {label}.",
        "file_missing": "{label} does not exist: {path}",
        "preflight_errors": "Preflight finished with {errors} error(s) and {warnings} warning(s).",
        "preflight_warnings": "Preflight finished with {warnings} warning(s).",
        "preflight_ok": "Preflight finished without errors or warnings.",
        "build_finished_message": "Build finished.",
        "build_running_status": "Build running...",
        "build_progress_title": "PBO build",
        "build_progress_message": "Build in progress...",
        "build_finished_status": "Build OK",
        "preflight_running_status": "Preflight running...",
        "preflight_finished_status": "Preflight OK",
        "working_status": "Working {current}/{maximum}",
        "error_status": "Error",
        "preflight_log": "Preflight log",
        "build_log": "Build log",
        "update_available_title": "Update available",
        "update_available_message": "Version {version} is available.\n\nCurrent version: {current}\n\nInstall now?",
        "update_button_install": "Update",
        "update_button_later": "Later",
        "update_progress_title": "Installing update",
        "update_progress_message": "Downloading update...",
        "update_replacing_message": "Download complete. Replacing files...",
        "update_installing_status": "Installing update...",
        "update_started_message": "The update installer has started. The app will close now.",
        "update_failed_message": "Update failed: {error}",
        "open_file": "Open file",
        "close": "Close",
        "cannot_clear_temp": "Cannot clear temp folder while a build is running.",
        "clear_temp_confirm": "Safely clear builder temp data?\n\n{path}",
        "temp_cleared": "Builder temp data cleared.",
        "cannot_clear_all_temp": "Cannot clear all temp while a build is running.",
        "clear_all_temp_confirm": "Clear ALL selected temp folder contents?\n\n{path}",
        "all_temp_cleared": "All temp folder contents cleared.",
        "cannot_clear_cache": "Cannot clear build cache while a build is running.",
        "select_addon": "Select at least one addon.",
        "clear_cache_confirm": "Clear build cache for selected addons?",
        "cache_cleared": "Cleared {count} cache entrie(s).",
        "and_more": "...and {count} more",
        "about_message": "{title}\nVersion: {version}\nAuthor: {author}\n\n{license}",
        "footer_license": "Freeware - Proprietary / All Rights Reserved",
        },
    "ru": {
        "settings": "Настройки",
        "tools": "Инструменты",
        "language": "Язык",
        "english": "Английский",
        "russian": "Русский",
        "private_key": "Приватный ключ",
        "project_root": "Корень проекта",
        "temp_dir": "Папка temp",
        "max_processes": "Макс. процессов",
        "exclude_patterns": "Исключения",
        "logs": "Логи",
        "preflight_checks": "Проверки Preflight",
        "check_cfgpatches": "CfgPatches",
        "check_required_addons": "requiredAddons[]",
        "check_cfgmods": "CfgMods скрипты",
        "check_references": "Ссылки в текстах",
        "check_p3d_internal": "Ссылки внутри P3D",
        "check_case_conflicts": "Конфликты регистра",
        "check_risky_paths": "Опасные пути",
        "check_prefix": "PBO prefix",
        "check_terrain_wrp": "Terrain / WRP",
        "check_navmesh": "Navmesh",
        "check_road_shapes": "Road shapes",
        "check_terrain_layers": "Terrain layers",
        "check_source_exports": "Source/export warnings",
        "check_terrain_size": "Размер terrain",
        "clear_logs": "Очистить логи",
        "logs_folder": "Папка логов",
        "cancel": "Отмена",
        "save": "Сохранить",
        "paths": "Пути",
        "ready": "Готов",
        "about": "О программе",
        "source_root": "Исходная папка",
        "output_root_client": "Вывод client",
        "output_root_server": "Вывод server",
        "pbo_name": "Имя PBO",
        "pbo_name_placeholder": "Опционально для одного аддона",
        "pipeline": "Пайплайн",
        "binarize_p3d": "Бинаризовать P3D",
        "protect_p3d": "Защитить P3D",
        "cpp_rvmat_to_bin": "CPP/RVMAT в BIN",
        "sign_pbos": "Подписывать PBO",
        "force_rebuild": "Полная пересборка",
        "preflight_before_build": "Проверка перед сборкой",
        "actions": "Действия",
        "build_pbos": "Собрать PBO",
        "preflight": "Проверка",
        "clear_all_temp": "Очистить temp",
        "clear_cache": "Очистить кэш",
        "latest_log": "Последний лог",
        "addons": "Аддоны",
        "refresh": "Обновить",
        "all": "Все",
        "none": "Снять",
        "open": "Открыть",
        "browse": "Выбрать",
        "add_path": "Добавить: {label}",
        "remove_path": "Удалить выбранный путь: {label}",
        "add_path_title": "Добавить: {label}",
        "language_restart": "Язык применится после перезапуска программы.",
        "cannot_clear_logs": "Нельзя очищать логи во время сборки.",
        "logs_empty": "Папка логов уже пустая.",
        "logs_cleared": "Папка логов очищена. Удалено файлов: {count}.",
        "logs_clear_partial": "Удалено файлов логов: {count}, но часть файлов удалить не удалось:\n\n{details}",
        "no_build_logs": "Логи сборки пока не найдены.",
        "path_empty": "Путь пустой.",
        "path_missing": "Путь не существует: {path}",
        "field_empty": "{label}: путь пустой.",
        "field_missing": "{label}: путь не существует: {path}",
        "select_source_root": "Выбери исходную папку.",
        "source_root_missing": "Исходная папка не существует: {path}",
        "select_addon_check": "Выбери хотя бы один аддон для проверки.",
        "select_addon_build": "Выбери хотя бы один аддон для сборки.",
        "no_selected_targets": "Выбранные аддоны не найдены.",
        "select_output_client": "Выбери папку вывода client.",
        "select_output_server": "Выбери папку вывода server для _SERVER аддонов.",
        "pbo_override_single": "Переопределение имени PBO можно использовать только при выборе одного аддона.",
        "select_required": "Выбери {label}.",
        "file_missing": "{label} не найден: {path}",
        "preflight_errors": "Проверка завершилась с ошибками: {errors}, предупреждений: {warnings}.",
        "preflight_warnings": "Проверка завершилась с предупреждениями: {warnings}.",
        "preflight_ok": "Проверка завершилась без ошибок и предупреждений.",
        "build_finished_message": "Сборка завершена.",
        "build_running_status": "Сборка...",
        "build_progress_title": "Сборка PBO",
        "build_progress_message": "Сборка в процессе...",
        "build_finished_status": "Сборка OK",
        "preflight_running_status": "Проверка...",
        "preflight_finished_status": "Проверка OK",
        "working_status": "Работа {current}/{maximum}",
        "error_status": "Ошибка",
        "preflight_log": "Лог проверки",
        "build_log": "Лог сборки",
        "update_available_title": "Доступно обновление",
        "update_available_message": "Доступна версия {version}.\n\nТекущая версия: {current}\n\nУстановить сейчас?",
        "update_button_install": "Обновить",
        "update_button_later": "Позже",
        "update_progress_title": "Установка обновления",
        "update_progress_message": "Скачивание обновления...",
        "update_replacing_message": "Скачивание завершено. Замена файлов...",
        "update_installing_status": "Установка обновления...",
        "update_started_message": "Установщик обновления запущен. Программа сейчас закроется.",
        "update_failed_message": "Не удалось обновить программу: {error}",
        "open_file": "Открыть файл",
        "close": "Закрыть",
        "cannot_clear_temp": "Нельзя очищать temp во время сборки.",
        "clear_temp_confirm": "Безопасно очистить временные данные билдера?\n\n{path}",
        "temp_cleared": "Временные данные билдера очищены.",
        "cannot_clear_all_temp": "Нельзя очищать весь temp во время сборки.",
        "clear_all_temp_confirm": "Очистить ВСЁ содержимое выбранной temp-папки?\n\n{path}",
        "all_temp_cleared": "Содержимое temp-папки очищено.",
        "cannot_clear_cache": "Нельзя очищать кэш сборки во время сборки.",
        "select_addon": "Выбери хотя бы один аддон.",
        "clear_cache_confirm": "Очистить кэш сборки для выбранных аддонов?",
        "cache_cleared": "Очищено записей кэша: {count}.",
        "and_more": "...и ещё {count}",
        "about_message": "{title}\nВерсия: {version}\nАвтор: {author}\n\n{license}",
        "footer_license": "Бесплатно - проприетарно / Все права защищены",
    },
}


def normalize_language(language):
    return language if language in TRANSLATIONS else DEFAULT_LANGUAGE


def tr_text(key, language=DEFAULT_LANGUAGE, **kwargs):
    language = normalize_language(language)
    text = TRANSLATIONS.get(language, {}).get(key, TRANSLATIONS["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


def get_asset_icon(name):
    path = ASSETS_DIR / name
    if path.is_file():
        return QIcon(str(path))
    return QIcon()


def set_button_icon(button, asset_name, fallback_icon=None, size=16):
    icon = get_asset_icon(asset_name)
    if icon.isNull() and fallback_icon is not None:
        icon = fallback_icon
    if not icon.isNull():
        button.setIcon(icon)
        button.setIconSize(QSize(size, size))


class BuildWorker(QThread):
    log_message = Signal(str)
    progress_changed = Signal(int, int)
    build_done = Signal()
    preflight_done = Signal(int, int)
    failed = Signal(str)

    def __init__(self, mode, settings, targets=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.settings = settings
        self.targets = targets or []

    def run(self):
        try:
            if self.mode == "build":
                build_all(self.settings, self.log_message.emit, self.progress_changed.emit)
                self.build_done.emit()
                return

            result = run_preflight_for_targets(
                self.settings,
                self.targets,
                self.log_message.emit,
                self.progress_changed.emit,
            )
            self.preflight_done.emit(result.errors, result.warnings)
        except Exception as error:
            self.failed.emit(str(error))


class UpdateCheckWorker(QThread):
    update_found = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            update_info = check_for_update()
            if update_info:
                self.update_found.emit(update_info)
        except Exception as error:
            self.failed.emit(str(error))


class UpdateInstallWorker(QThread):
    progress_changed = Signal(int, int, str)
    started = Signal()
    failed = Signal(str)

    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info

    def run(self):
        try:
            install_update_and_restart(self.update_info, self.progress_changed.emit)
            self.started.emit()
        except Exception as error:
            self.failed.emit(str(error))


class BuildProgressDialog(QDialog):
    def __init__(self, parent=None, language=DEFAULT_LANGUAGE):
        super().__init__(parent)
        self._allow_close = False
        self.setWindowTitle(tr_text("build_progress_title", language))
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet(QT_STYLE)
        self.setFixedSize(320, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        label = QLabel(tr_text("build_progress_message", language))
        label.setObjectName("DialogTitle")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        layout.addWidget(progress)

    def closeEvent(self, event):
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()

    def finish(self):
        self._allow_close = True
        self.accept()


class UpdateProgressDialog(QDialog):
    def __init__(self, parent=None, language=DEFAULT_LANGUAGE):
        super().__init__(parent)
        self._allow_close = False
        self.setWindowTitle(tr_text("update_progress_title", language))
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet(QT_STYLE)
        self.setFixedSize(420, 140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self.label = QLabel(tr_text("update_progress_message", language))
        self.label.setObjectName("DialogTitle")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

    def set_progress(self, current, total, label=""):
        if total > 0:
            percent = min(100, int((current / total) * 100))
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
        else:
            self.progress.setRange(0, 0)
        if label:
            self.label.setText(label)

    def set_message(self, message):
        self.label.setText(message)
        self.progress.setRange(0, 0)

    def closeEvent(self, event):
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()

    def finish(self):
        self._allow_close = True
        self.accept()


class PathRow(QWidget):
    changed = Signal()

    def __init__(self, label, value="", browse_kind="folder", file_filter="All files (*.*)", parent=None, language=DEFAULT_LANGUAGE):
        super().__init__(parent)
        self.browse_kind = browse_kind
        self.file_filter = file_filter
        self.language = normalize_language(language)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(3)

        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.edit = QLineEdit(value)
        self.edit.setMinimumHeight(25)
        self.edit.setMaximumHeight(25)
        self.edit.textChanged.connect(self.changed.emit)

        self.open_button = QToolButton()
        self.open_button.setObjectName("PathIconButton")
        set_button_icon(
            self.open_button,
            "folder.png",
            self.style().standardIcon(QStyle.SP_DirOpenIcon),
            17,
        )
        self.open_button.setToolTip(tr_text("open", self.language))
        self.open_button.clicked.connect(self.open_path)

        self.browse_button = QToolButton()
        self.browse_button.setObjectName("PathIconButton")
        self.browse_button.setText("...")
        self.browse_button.setToolTip(tr_text("browse", self.language))
        self.browse_button.clicked.connect(self.browse)

        layout.addWidget(self.label, 0, 0, 1, 3)
        layout.addWidget(self.edit, 1, 0)
        layout.addWidget(self.open_button, 1, 1)
        layout.addWidget(self.browse_button, 1, 2)
        layout.setColumnStretch(0, 1)

    def text(self):
        return self.edit.text().strip()

    def set_text(self, value):
        self.edit.setText(value or "")

    def browse(self):
        current = self.text()
        initial = get_initial_dir_from_value(current)
        if self.browse_kind == "file":
            path, _ = QFileDialog.getOpenFileName(self, self.label.text(), initial, self.file_filter)
        else:
            path = QFileDialog.getExistingDirectory(self, self.label.text(), initial)
        if path:
            if len(path) == 3 and path[1] == ":" and path.endswith(WIN_SEP):
                path = path[:2]
            self.set_text(path)

    def open_path(self):
        value = self.text()
        if not value:
            QMessageBox.warning(self, APP_TITLE, tr_text("path_empty", self.language))
            return
        target = value if os.path.isdir(value) else os.path.dirname(value)
        if not target or not os.path.isdir(target):
            QMessageBox.warning(self, APP_TITLE, tr_text("path_missing", self.language, path=value))
            return
        try:
            if os.name == "nt":
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target])
        except Exception as error:
            QMessageBox.warning(self, APP_TITLE, str(error))


class SourceRootRow(QWidget):
    changed = Signal()

    def __init__(self, label, current="", sources=None, parent=None, language=DEFAULT_LANGUAGE):
        super().__init__(parent)
        self._updating = False
        self.path_label = label
        self.language = normalize_language(language)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(1)

        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")

        self.combo = QComboBox()
        self.combo.setEditable(False)
        self.combo.setMinimumHeight(28)
        self.combo.setMaximumHeight(28)
        self.combo.setMinimumWidth(0)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setToolTip(current or "")

        self.add_button = QToolButton()
        self.add_button.setObjectName("PathIconButton")
        set_button_icon(self.add_button, "plus.png", size=15)
        self.add_button.setToolTip(tr_text("add_path", self.language, label=label))
        self.add_button.clicked.connect(self.add_source_root)

        self.remove_button = QToolButton()
        self.remove_button.setObjectName("PathIconButton")
        set_button_icon(self.remove_button, "minus.png", size=15)
        self.remove_button.setToolTip(tr_text("remove_path", self.language, label=label))
        self.remove_button.clicked.connect(self.remove_source_root)

        self.open_button = QToolButton()
        self.open_button.setObjectName("PathIconButton")
        set_button_icon(
            self.open_button,
            "folder.png",
            self.style().standardIcon(QStyle.SP_DirOpenIcon),
            17,
        )
        self.open_button.setToolTip(tr_text("open", self.language))
        self.open_button.clicked.connect(self.open_path)

        layout.addWidget(self.label, 0, 0, 1, 4)
        layout.addWidget(self.combo, 1, 0)
        layout.addWidget(self.add_button, 1, 1)
        layout.addWidget(self.remove_button, 1, 2)
        layout.addWidget(self.open_button, 1, 3)
        layout.setColumnMinimumWidth(0, 0)
        layout.setColumnStretch(0, 1)

        for source in self._normalized_sources(current, sources or []):
            self._add_source_item(source)
        if current:
            self.set_text(current)

        self.combo.currentIndexChanged.connect(self._on_current_index_changed)

    def _normalized_sources(self, current, sources):
        result = []
        seen = set()
        for source in [current, *(sources or [])]:
            value = (source or "").strip()
            if not value:
                continue
            key = os.path.normcase(os.path.normpath(value))
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _display_name(self, path):
        value = (path or "").strip().rstrip("\\/")
        if not value:
            return ""
        name = os.path.basename(os.path.normpath(value))
        return name or value

    def _add_source_item(self, path):
        value = (path or "").strip()
        if not value:
            return
        if self.find_source_index(value) >= 0:
            return
        self.combo.addItem(self._display_name(value), value)

    def _current_stored_path(self):
        index = self.combo.currentIndex()
        if index >= 0:
            stored = self.combo.itemData(index)
            if stored:
                return str(stored).strip()
        return self.combo.currentText().strip()

    def find_source_index(self, value):
        key = os.path.normcase(os.path.normpath((value or "").strip()))
        if not key:
            return -1
        for index in range(self.combo.count()):
            stored = self.combo.itemData(index) or self.combo.itemText(index)
            stored_key = os.path.normcase(os.path.normpath(str(stored).strip()))
            if stored_key == key:
                return index
        return -1

    def _emit_changed(self):
        if not self._updating:
            self.combo.setToolTip(self.text())
            self.changed.emit()

    def text(self):
        return self._current_stored_path()

    def set_text(self, value):
        value = (value or "").strip()
        if not value:
            self.combo.setCurrentText("")
            return
        self._updating = True
        try:
            index = self.find_source_index(value)
            if index < 0:
                self._add_source_item(value)
                index = self.find_source_index(value)
            if index >= 0:
                self.combo.setCurrentIndex(index)
            elif self.combo.lineEdit():
                self.combo.lineEdit().setText(value)
            self.combo.setToolTip(value)
        finally:
            self._updating = False
        self.changed.emit()

    def source_roots(self):
        result = []
        seen = set()
        current = self.text()
        values = [current]
        values.extend(str(self.combo.itemData(index) or self.combo.itemText(index)).strip() for index in range(self.combo.count()))
        for value in values:
            if not value:
                continue
            key = os.path.normcase(os.path.normpath(value))
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _on_current_index_changed(self):
        if self._updating:
            return
        if self.combo.lineEdit():
            self._updating = True
            try:
                self.combo.lineEdit().setText(self._display_name(self.text()))
            finally:
                self._updating = False
        self.combo.setToolTip(self.text())
        self.changed.emit()

    def add_source_root(self):
        initial = get_initial_dir_from_value(self.text())
        path = QFileDialog.getExistingDirectory(
            self,
            tr_text("add_path_title", self.language, label=self.path_label),
            initial,
        )
        if not path:
            return
        if len(path) == 3 and path[1] == ":" and path.endswith(WIN_SEP):
            path = path[:2]
        self.set_text(path)

    def remove_source_root(self):
        index = self.combo.currentIndex()
        if index < 0:
            return
        self._updating = True
        try:
            self.combo.removeItem(index)
            if self.combo.count() > 0:
                self.combo.setCurrentIndex(min(index, self.combo.count() - 1))
                if self.combo.lineEdit():
                    self.combo.lineEdit().setText(self._display_name(self.text()))
            elif self.combo.lineEdit():
                self.combo.lineEdit().clear()
            self.combo.setToolTip(self.text())
        finally:
            self._updating = False
        self.changed.emit()

    def open_path(self):
        value = self.text()
        if not value:
            QMessageBox.warning(self, APP_TITLE, tr_text("field_empty", self.language, label=self.path_label))
            return
        if not os.path.isdir(value):
            QMessageBox.warning(self, APP_TITLE, tr_text("field_missing", self.language, label=self.path_label, path=value))
            return
        try:
            if os.name == "nt":
                os.startfile(value)
            else:
                subprocess.Popen(["xdg-open", value])
        except Exception as error:
            QMessageBox.warning(self, APP_TITLE, str(error))


class SettingsDialog(QDialog):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.language = normalize_language(values.get("language", DEFAULT_LANGUAGE))
        self.setWindowTitle(tr_text("settings", self.language))
        self.setStyleSheet(QT_STYLE)
        self.setModal(True)
        self.resize(860, 640)
        self.setMinimumSize(760, 520)
        self.values = copy.deepcopy(values)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        title = QLabel(tr_text("settings", self.language))
        title.setObjectName("DialogTitle")
        layout.addWidget(title)

        tools_card = QFrame()
        tools_card.setObjectName("Card")
        tools_layout = QVBoxLayout(tools_card)
        tools_layout.setContentsMargins(12, 12, 12, 12)
        tools_layout.setSpacing(8)

        self.binarize_row = PathRow(
            "binarize.exe",
            self.values.get("binarize_exe", ""),
            "file",
            "binarize.exe (binarize.exe);;Executable (*.exe);;All files (*.*)",
            language=self.language,
        )
        self.cfgconvert_row = PathRow(
            "CfgConvert.exe",
            self.values.get("cfgconvert_exe", ""),
            "file",
            "CfgConvert.exe (CfgConvert.exe);;Executable (*.exe);;All files (*.*)",
            language=self.language,
        )
        self.p3d_obfuscator_row = PathRow(
            "P3DObfuscator.exe",
            self.values.get("p3d_obfuscator_exe", ""),
            "file",
            "P3DObfuscator (*.exe);;Executable (*.exe);;All files (*.*)",
            language=self.language,
        )
        self.dssignfile_row = PathRow(
            "DSSignFile.exe",
            self.values.get("dssignfile_exe", ""),
            "file",
            "DSSignFile.exe (DSSignFile.exe);;Executable (*.exe);;All files (*.*)",
            language=self.language,
        )
        self.private_key_row = PathRow(
            tr_text("private_key", self.language),
            self.values.get("private_key", ""),
            "file",
            "BI private key (*.biprivatekey);;All files (*.*)",
            language=self.language,
        )
        self.project_root_row = PathRow(tr_text("project_root", self.language), self.values.get("project_root", DEFAULT_PROJECT_ROOT), language=self.language)
        self.temp_dir_row = PathRow(tr_text("temp_dir", self.language), self.values.get("temp_dir", DEFAULT_TEMP_DIR), language=self.language)

        for row in (
            self.binarize_row,
            self.cfgconvert_row,
            self.p3d_obfuscator_row,
            self.dssignfile_row,
            self.private_key_row,
            self.project_root_row,
            self.temp_dir_row,
        ):
            tools_layout.addWidget(row)
        layout.addWidget(tools_card)

        perf_card = QFrame()
        perf_card.setObjectName("Card")
        perf_layout = QGridLayout(perf_card)
        perf_layout.setContentsMargins(12, 12, 12, 12)
        perf_layout.setHorizontalSpacing(10)
        perf_layout.setVerticalSpacing(8)

        lang_label = QLabel(tr_text("language", self.language))
        lang_label.setObjectName("FieldLabel")
        self.language_combo = QComboBox()
        self.language_combo.addItem(tr_text("russian", self.language), "ru")
        self.language_combo.addItem(tr_text("english", self.language), "en")
        language_index = self.language_combo.findData(self.language)
        if language_index >= 0:
            self.language_combo.setCurrentIndex(language_index)
        perf_layout.addWidget(lang_label, 0, 0)
        perf_layout.addWidget(self.language_combo, 1, 0)

        max_label = QLabel(tr_text("max_processes", self.language))
        max_label.setObjectName("FieldLabel")
        self.max_processes_spin = QSpinBox()
        self.max_processes_spin.setRange(1, 64)
        self.max_processes_spin.setValue(int(self.values.get("max_processes", get_default_max_processes())))
        self.max_processes_spin.setMinimumHeight(30)
        perf_layout.addWidget(max_label, 0, 1)
        perf_layout.addWidget(self.max_processes_spin, 1, 1)
        layout.addWidget(perf_card)

        filters_card = QFrame()
        filters_card.setObjectName("Card")
        filters_layout = QVBoxLayout(filters_card)
        filters_layout.setContentsMargins(12, 12, 12, 12)
        filters_layout.setSpacing(8)
        exclude_label = QLabel(tr_text("exclude_patterns", self.language))
        exclude_label.setObjectName("FieldLabel")
        self.exclude_edit = QPlainTextEdit()
        self.exclude_edit.setPlainText(self.values.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS))
        self.exclude_edit.setMinimumHeight(90)
        filters_layout.addWidget(exclude_label)
        filters_layout.addWidget(self.exclude_edit)
        layout.addWidget(filters_card, 1)

        preflight_card = QFrame()
        preflight_card.setObjectName("Card")
        preflight_layout = QGridLayout(preflight_card)
        preflight_layout.setContentsMargins(12, 12, 12, 12)
        preflight_layout.setHorizontalSpacing(10)
        preflight_layout.setVerticalSpacing(6)
        preflight_title = QLabel(tr_text("preflight_checks", self.language))
        preflight_title.setObjectName("FieldLabel")
        preflight_layout.addWidget(preflight_title, 0, 0, 1, 2)
        self.preflight_checkboxes = {}
        preflight_items = [
            ("preflight_check_cfgpatches", "check_cfgpatches"),
            ("preflight_check_required_addons", "check_required_addons"),
            ("preflight_check_cfgmods", "check_cfgmods"),
            ("preflight_check_references", "check_references"),
            ("preflight_check_p3d_internal", "check_p3d_internal"),
            ("preflight_check_case_conflicts", "check_case_conflicts"),
            ("preflight_check_risky_paths", "check_risky_paths"),
            ("preflight_check_prefix", "check_prefix"),
            ("preflight_check_terrain_wrp", "check_terrain_wrp"),
            ("preflight_check_terrain_navmesh", "check_navmesh"),
            ("preflight_check_terrain_road_shapes", "check_road_shapes"),
            ("preflight_check_terrain_layers", "check_terrain_layers"),
            ("preflight_check_terrain_source_exports", "check_source_exports"),
            ("preflight_check_terrain_size", "check_terrain_size"),
        ]
        for item_index, (setting_key, label_key) in enumerate(preflight_items, start=1):
            checkbox = QCheckBox(tr_text(label_key, self.language))
            checkbox.setChecked(bool(self.values.get(setting_key, PREFLIGHT_CHECK_DEFAULTS[setting_key])))
            row = 1 + (item_index - 1) // 2
            column = (item_index - 1) % 2
            preflight_layout.addWidget(checkbox, row, column)
            self.preflight_checkboxes[setting_key] = checkbox
        layout.addWidget(preflight_card)

        actions_card = QFrame()
        actions_card.setObjectName("Card")
        actions_layout = QGridLayout(actions_card)
        actions_layout.setContentsMargins(12, 12, 12, 12)
        actions_layout.setHorizontalSpacing(8)
        actions_layout.setVerticalSpacing(8)
        actions_title = QLabel(tr_text("logs", self.language))
        actions_title.setObjectName("FieldLabel")
        self.clear_log_button = QPushButton(tr_text("clear_logs", self.language))
        self.open_logs_button = QPushButton(tr_text("logs_folder", self.language))
        if parent is not None:
            self.clear_log_button.clicked.connect(lambda: parent.clear_log_from_settings())
            self.open_logs_button.clicked.connect(lambda: parent.open_logs_folder())
        actions_layout.addWidget(actions_title, 0, 0, 1, 2)
        actions_layout.addWidget(self.clear_log_button, 1, 0)
        actions_layout.addWidget(self.open_logs_button, 1, 1)
        layout.addWidget(actions_card)
        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton(tr_text("cancel", self.language))
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton(tr_text("save", self.language))
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        root_layout.addLayout(buttons)

    def get_values(self):
        values = {
            "binarize_exe": self.binarize_row.text(),
            "cfgconvert_exe": self.cfgconvert_row.text(),
            "p3d_obfuscator_exe": self.p3d_obfuscator_row.text(),
            "dssignfile_exe": self.dssignfile_row.text(),
            "private_key": self.private_key_row.text(),
            "project_root": self.project_root_row.text(),
            "temp_dir": self.temp_dir_row.text(),
            "max_processes": self.max_processes_spin.value(),
            "exclude_patterns": self.exclude_edit.toPlainText().strip(),
            "language": normalize_language(self.language_combo.currentData()),
        }
        for key, checkbox in self.preflight_checkboxes.items():
            values[key] = checkbox.isChecked()
        return values


class ModernPboBuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.saved_settings = load_saved_settings()
        self.worker = None
        self.update_check_worker = None
        self.update_install_worker = None
        self.current_log_file = None
        self.current_log_path = ""
        self.log_lines = []
        self.current_addon_targets = []
        self.is_building = False
        self.build_progress_dialog = None
        self.update_progress_dialog = None
        self.current_language = normalize_language(self.saved_settings.get("language", DEFAULT_LANGUAGE))

        self.setWindowTitle(APP_TITLE)
        self.resize(820, 600)
        self.setFixedSize(820, 600)
        self._set_icon()
        self.advanced_settings = self._load_advanced_settings()

        self._build_ui()
        self._wire_events()
        self.refresh_addon_list()
        self.set_status(tr_text("ready", self.current_language), "ready")
        QTimer.singleShot(0, self.sync_addons_height)
        QTimer.singleShot(1000, self.start_update_check)

    def _set_icon(self):
        icon_path = self._app_icon_path()
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _app_icon_path(self):
        asset_icon = Path(__file__).parent / "assets" / "icon.png"
        if asset_icon.is_file():
            return asset_icon
        return Path(__file__).parent / APP_ICON_FILE

    def _build_ui(self):
        self.setStyleSheet(QT_STYLE)
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 6, 8, 6)
        root_layout.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_addons_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([435, 375])
        splitter.handle(1).setDisabled(True)
        root_layout.addWidget(splitter, 1)

        root_layout.addWidget(self._create_footer())

    def _create_left_panel(self):
        panel = QWidget()
        panel.setObjectName("LeftPanel")
        panel.setMinimumWidth(420)
        panel.setMaximumWidth(440)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        paths_card = self._card(tr_text("paths", self.current_language))
        paths_layout = QVBoxLayout(paths_card)
        paths_layout.setContentsMargins(10, 8, 10, 8)
        paths_layout.setSpacing(3)
        self._add_card_title(paths_layout, tr_text("paths", self.current_language))

        top = QHBoxLayout()
        top.setSpacing(6)
        self.status_dot = QLabel()
        self.status_dot.setObjectName("StatusDot")
        self.status_text = QLabel(tr_text("ready", self.current_language))
        self.status_text.setObjectName("StatusText")
        status_wrap = QFrame()
        status_wrap.setObjectName("StatusBadge")
        status_layout = QHBoxLayout(status_wrap)
        status_layout.setContentsMargins(6, 2, 6, 2)
        status_layout.setSpacing(5)
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_wrap.setFixedWidth(116)
        top.addWidget(status_wrap)
        top.addStretch(1)

        self.about_button = QPushButton(tr_text("about", self.current_language))
        self.about_button.setObjectName("AboutButton")
        self.about_button.setMinimumSize(92, 26)
        self.about_button.setMaximumHeight(26)
        self.about_button.clicked.connect(self.show_about)
        top.addWidget(self.about_button)
        paths_layout.addLayout(top)

        saved_output_root = self.saved_settings.get("output_root", self.saved_settings.get("output_addons", ""))
        saved_output_server_root = self.saved_settings.get("output_root_server", "")
        saved_pbo_name = self.saved_settings.get("pbo_name", self.saved_settings.get("prefix_root", ""))

        self.source_root_row = SourceRootRow(
            tr_text("source_root", self.current_language),
            self.saved_settings.get("source_root", ""),
            self.saved_settings.get("source_roots", []),
            language=self.current_language,
        )
        self.output_root_row = SourceRootRow(
            tr_text("output_root_client", self.current_language),
            saved_output_root,
            self.saved_settings.get("output_roots", []),
            language=self.current_language,
        )
        self.output_root_server_row = SourceRootRow(
            tr_text("output_root_server", self.current_language),
            saved_output_server_root,
            self.saved_settings.get("output_server_roots", []),
            language=self.current_language,
        )
        self.pbo_name_edit = QLineEdit(saved_pbo_name)
        self.pbo_name_edit.setPlaceholderText(tr_text("pbo_name_placeholder", self.current_language))
        self.pbo_name_edit.setMinimumHeight(28)
        self.pbo_name_edit.setMaximumHeight(28)
        self.pbo_name_edit.setMinimumWidth(0)

        pbo_label = QLabel(tr_text("pbo_name", self.current_language))
        pbo_label.setObjectName("FieldLabel")
        paths_layout.addWidget(self.source_root_row)
        paths_layout.addWidget(self.output_root_row)
        paths_layout.addWidget(self.output_root_server_row)
        paths_layout.addWidget(pbo_label)
        paths_layout.addWidget(self.pbo_name_edit)
        layout.addWidget(paths_card)

        options_card = self._card(tr_text("pipeline", self.current_language))
        options_layout = QGridLayout(options_card)
        options_layout.setContentsMargins(10, 8, 10, 10)
        options_layout.setHorizontalSpacing(8)
        options_layout.setVerticalSpacing(5)
        self._add_card_title(options_layout, tr_text("pipeline", self.current_language), 0, 0, 1, 2)

        self.use_binarize_check = QCheckBox(tr_text("binarize_p3d", self.current_language))
        self.protect_p3d_check = QCheckBox(tr_text("protect_p3d", self.current_language))
        self.convert_config_check = QCheckBox(tr_text("cpp_rvmat_to_bin", self.current_language))
        self.sign_pbos_check = QCheckBox(tr_text("sign_pbos", self.current_language))
        self.force_rebuild_check = QCheckBox(tr_text("force_rebuild", self.current_language))
        self.preflight_before_build_check = QCheckBox(tr_text("preflight_before_build", self.current_language))
        self.use_binarize_check.setChecked(self.saved_settings.get("use_binarize", True))
        self.protect_p3d_check.setChecked(self.saved_settings.get("protect_p3d", False))
        self.convert_config_check.setChecked(self.saved_settings.get("convert_config", True))
        self.sign_pbos_check.setChecked(self.saved_settings.get("sign_pbos", True))
        self.force_rebuild_check.setChecked(self.saved_settings.get("force_rebuild", False))
        self.preflight_before_build_check.setChecked(self.saved_settings.get("preflight_before_build", False))

        options_layout.addWidget(self.use_binarize_check, 1, 0)
        options_layout.addWidget(self.convert_config_check, 1, 1)
        options_layout.addWidget(self.protect_p3d_check, 2, 0)
        options_layout.addWidget(self.force_rebuild_check, 2, 1)
        options_layout.addWidget(self.sign_pbos_check, 3, 0)
        options_layout.addWidget(self.preflight_before_build_check, 4, 0)
        layout.addWidget(options_card)

        action_card = self._card(tr_text("actions", self.current_language))
        self.action_card = action_card
        action_layout = QGridLayout(action_card)
        action_layout.setContentsMargins(10, 8, 10, 10)
        action_layout.setSpacing(6)
        self._add_card_title(action_layout, tr_text("actions", self.current_language), 0, 0, 1, 3)
        self.build_button = QPushButton(tr_text("build_pbos", self.current_language))
        self.build_button.setObjectName("PrimaryButton")
        self.preflight_button = QPushButton(tr_text("preflight", self.current_language))
        self.clear_all_temp_button = QPushButton(tr_text("clear_all_temp", self.current_language))
        self.clear_cache_button = QPushButton(tr_text("clear_cache", self.current_language))
        self.latest_log_button = QPushButton(tr_text("latest_log", self.current_language))
        action_layout.addWidget(self.build_button, 1, 0, 1, 2)
        action_layout.addWidget(self.preflight_button, 1, 2)
        action_layout.addWidget(self.clear_all_temp_button, 2, 0)
        action_layout.addWidget(self.clear_cache_button, 2, 1)
        action_layout.addWidget(self.latest_log_button, 2, 2)
        layout.addWidget(action_card)
        layout.addStretch(1)

        return panel

    def _create_addons_panel(self):
        wrapper = QWidget()
        wrapper.setObjectName("AddonsWrapper")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(8, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        addons_card = self._card(tr_text("addons", self.current_language))
        self.addons_card = addons_card
        addons_card.setMinimumWidth(350)
        addons_card.setMaximumWidth(380)
        addons_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        addons_layout = QVBoxLayout(addons_card)
        addons_layout.setContentsMargins(10, 8, 10, 10)
        addons_layout.setSpacing(6)
        self._add_card_title(addons_layout, tr_text("addons", self.current_language))

        self.addon_list = QListWidget()
        self.addon_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        addons_layout.addWidget(self.addon_list, 1)

        addon_buttons = QHBoxLayout()
        addon_buttons.setSpacing(6)
        self.refresh_button = QPushButton(tr_text("refresh", self.current_language))
        self.select_all_button = QPushButton(tr_text("all", self.current_language))
        self.select_none_button = QPushButton(tr_text("none", self.current_language))
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("AddonIconButton")
        self.settings_button.setFixedSize(36, 36)
        set_button_icon(
            self.settings_button,
            "options.png",
            self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
            17,
        )
        self.settings_button.setToolTip(tr_text("settings", self.current_language))
        addon_buttons.addWidget(self.refresh_button)
        addon_buttons.addWidget(self.select_all_button)
        addon_buttons.addWidget(self.select_none_button)
        addon_buttons.addWidget(self.settings_button)
        addons_layout.addLayout(addon_buttons)
        wrapper_layout.addWidget(addons_card)
        wrapper_layout.addStretch(1)
        return wrapper

    def sync_addons_height(self):
        if not hasattr(self, "addons_card") or not hasattr(self, "action_card"):
            return
        action_bottom = self.action_card.mapTo(self, self.action_card.rect().bottomLeft()).y()
        addons_top = self.addons_card.mapTo(self, self.addons_card.rect().topLeft()).y()
        target_height = max(260, action_bottom - addons_top + 1)
        self.addons_card.setMinimumHeight(target_height)
        self.addons_card.setMaximumHeight(target_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.sync_addons_height)

    def _create_footer(self):
        footer = QFrame()
        footer.setObjectName("Footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(2, 0, 2, 0)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress, 1)
        version = QLabel(f"{APP_VERSION}  |  {tr_text('footer_license', self.current_language)}")
        version.setObjectName("Muted")
        layout.addWidget(version)
        return footer

    def _card(self, title):
        card = QFrame()
        card.setObjectName("Card")
        card.setProperty("title", title)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return card

    def _add_card_title(self, layout, title, *grid_args):
        label = QLabel(title)
        label.setObjectName("CardTitle")
        if isinstance(layout, QGridLayout):
            layout.addWidget(label, *grid_args)
        else:
            layout.addWidget(label)

    def _wire_events(self):
        self.source_root_row.changed.connect(lambda: self.refresh_addon_list())
        self.output_root_row.changed.connect(lambda: self.refresh_addon_list())
        self.output_root_server_row.changed.connect(self.save_path_settings)
        self.refresh_button.clicked.connect(lambda: self.refresh_addon_list())
        self.select_all_button.clicked.connect(self.select_all_addons)
        self.select_none_button.clicked.connect(self.select_no_addons)
        self.addon_list.itemChanged.connect(self.save_path_settings)
        self.build_button.clicked.connect(self.start_build)
        self.preflight_button.clicked.connect(self.start_preflight)
        self.clear_all_temp_button.clicked.connect(self.clear_full_temp_from_ui)
        self.clear_cache_button.clicked.connect(self.clear_build_cache_from_ui)
        self.latest_log_button.clicked.connect(self.open_latest_log)
        self.settings_button.clicked.connect(self.open_settings_dialog)

        for widget in (
            self.pbo_name_edit,
            self.use_binarize_check,
            self.protect_p3d_check,
            self.convert_config_check,
            self.sign_pbos_check,
            self.force_rebuild_check,
            self.preflight_before_build_check,
        ):
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.save_path_settings)
            else:
                widget.toggled.connect(self.save_path_settings)

    def _load_advanced_settings(self):
        settings = {
            "language": self.current_language,
            "binarize_exe": self.saved_settings.get("binarize_exe", find_dayz_binarize()),
            "cfgconvert_exe": self.saved_settings.get("cfgconvert_exe", find_cfgconvert()),
            "p3d_obfuscator_exe": self.saved_settings.get("p3d_obfuscator_exe", find_p3d_obfuscator()),
            "dssignfile_exe": self.saved_settings.get("dssignfile_exe", find_dssignfile()),
            "private_key": self.saved_settings.get("private_key", ""),
            "project_root": self.saved_settings.get("project_root", DEFAULT_PROJECT_ROOT),
            "temp_dir": self.saved_settings.get("temp_dir", DEFAULT_TEMP_DIR),
            "max_processes": int(self.saved_settings.get("max_processes", get_default_max_processes())),
            "exclude_patterns": self.saved_settings.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS),
        }
        for key, default in PREFLIGHT_CHECK_DEFAULTS.items():
            settings[key] = bool(self.saved_settings.get(key, default))
        return settings

    def collect_preflight_check_settings(self):
        return {
            key: bool(self.advanced_settings.get(key, default))
            for key, default in PREFLIGHT_CHECK_DEFAULTS.items()
        }

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.advanced_settings, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.get_values()
        old_language = self.current_language
        self.advanced_settings.update(values)
        self.current_language = normalize_language(values.get("language", old_language))
        self.save_path_settings()
        if self.current_language != old_language:
            QMessageBox.information(self, APP_TITLE, tr_text("language_restart", self.current_language))

    def set_status(self, text, kind):
        colors = {
            "ready": "#7fb087",
            "building": "#d6aa5f",
            "preflight": "#7aa2d6",
            "success": "#7fb087",
            "error": "#ff7070",
        }
        color = colors.get(kind, colors["ready"])
        self.status_text.setText(text)
        self.status_dot.setStyleSheet(f"background:{color}; border-radius:4px; min-width:8px; max-width:8px; min-height:16px; max-height:16px;")

    def get_selected_addon_names(self):
        selected = []
        for index in range(self.addon_list.count()):
            item = self.addon_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def refresh_addon_list(self):
        source_root = self.source_root_row.text()
        output_root = self.output_root_row.text()
        output_addons_dir = os.path.join(output_root, "Addons") if output_root else ""
        previous_selection = set(self.get_selected_addon_names())
        self.addon_list.blockSignals(True)
        self.addon_list.clear()
        self.current_addon_targets = []
        if not source_root or not os.path.isdir(source_root):
            self.addon_list.blockSignals(False)
            self.save_path_settings()
            return
        self.current_addon_targets = detect_addon_targets(source_root, output_addons_dir)
        names = [name for name, _ in self.current_addon_targets]
        selection = previous_selection
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in selection else Qt.CheckState.Unchecked)
            self.addon_list.addItem(item)
        self.addon_list.blockSignals(False)
        self.save_path_settings()

    def select_all_addons(self):
        for index in range(self.addon_list.count()):
            self.addon_list.item(index).setCheckState(Qt.CheckState.Checked)
        self.save_path_settings()

    def select_no_addons(self):
        for index in range(self.addon_list.count()):
            self.addon_list.item(index).setCheckState(Qt.CheckState.Unchecked)
        self.save_path_settings()

    def save_path_settings(self):
        data = self.collect_saved_settings()
        width = max(self.width(), 820)
        height = max(self.height(), 575)
        data["window_geometry"] = f"{width}x{height}"
        self.saved_settings = data
        try:
            save_saved_settings(data)
        except Exception:
            pass

    def collect_saved_settings(self):
        data = {
            "source_root": self.source_root_row.text(),
            "source_roots": self.source_root_row.source_roots(),
            "output_root": self.output_root_row.text(),
            "output_roots": self.output_root_row.source_roots(),
            "output_root_server": self.output_root_server_row.text(),
            "output_server_roots": self.output_root_server_row.source_roots(),
            "pbo_name": self.pbo_name_edit.text().strip(),
            "use_binarize": self.use_binarize_check.isChecked(),
            "protect_p3d": self.protect_p3d_check.isChecked(),
            "convert_config": self.convert_config_check.isChecked(),
            "sign_pbos": self.sign_pbos_check.isChecked(),
            "force_rebuild": self.force_rebuild_check.isChecked(),
            "preflight_before_build": self.preflight_before_build_check.isChecked(),
            "max_processes": int(self.advanced_settings.get("max_processes", get_default_max_processes())),
            "binarize_exe": self.advanced_settings.get("binarize_exe", ""),
            "cfgconvert_exe": self.advanced_settings.get("cfgconvert_exe", ""),
            "p3d_obfuscator_exe": self.advanced_settings.get("p3d_obfuscator_exe", ""),
            "dssignfile_exe": self.advanced_settings.get("dssignfile_exe", ""),
            "private_key": self.advanced_settings.get("private_key", ""),
            "project_root": self.advanced_settings.get("project_root", ""),
            "temp_dir": self.advanced_settings.get("temp_dir", ""),
            "exclude_patterns": self.advanced_settings.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS),
            "language": normalize_language(self.advanced_settings.get("language", self.current_language)),
            "selected_addons": self.get_selected_addon_names() if hasattr(self, "addon_list") else [],
        }
        data.update(self.collect_preflight_check_settings())
        return data

    def validate_preflight_settings(self):
        self.refresh_addon_list()
        source_root = self.source_root_row.text()
        if not source_root:
            raise BuildError(tr_text("select_source_root", self.current_language))
        if not os.path.isdir(source_root):
            raise BuildError(tr_text("source_root_missing", self.current_language, path=source_root))
        selected_addons = self.get_selected_addon_names()
        if not selected_addons:
            raise BuildError(tr_text("select_addon_check", self.current_language))
        selected_set = set(selected_addons)
        targets = [(name, path) for name, path in self.current_addon_targets if name in selected_set]
        if not targets:
            raise BuildError(tr_text("no_selected_targets", self.current_language))
        settings = {
            "cfgconvert_exe": self.advanced_settings.get("cfgconvert_exe", ""),
            "project_root": self.advanced_settings.get("project_root", "") or DEFAULT_PROJECT_ROOT,
            "temp_dir": self.advanced_settings.get("temp_dir", "") or DEFAULT_TEMP_DIR,
            "exclude_patterns": self.advanced_settings.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS),
        }
        settings.update(self.collect_preflight_check_settings())
        self.save_path_settings()
        return settings, targets

    def validate_settings(self):
        self.refresh_addon_list()
        source_root = self.source_root_row.text()
        output_root = self.output_root_row.text()
        output_root_server = self.output_root_server_row.text()
        if not source_root:
            raise BuildError(tr_text("select_source_root", self.current_language))
        if not os.path.isdir(source_root):
            raise BuildError(tr_text("source_root_missing", self.current_language, path=source_root))
        if not output_root:
            raise BuildError(tr_text("select_output_client", self.current_language))
        selected_addons = self.get_selected_addon_names()
        if not selected_addons:
            raise BuildError(tr_text("select_addon_build", self.current_language))
        has_server_addon = any(addon_name.upper().endswith("_SERVER") for addon_name in selected_addons)
        if has_server_addon and not output_root_server:
            raise BuildError(tr_text("select_output_server", self.current_language))
        if self.pbo_name_edit.text().strip() and len(selected_addons) > 1:
            raise BuildError(tr_text("pbo_override_single", self.current_language))

        if self.use_binarize_check.isChecked():
            self._require_file(self.advanced_settings.get("binarize_exe", ""), "binarize.exe")
        if self.protect_p3d_check.isChecked():
            if not self.use_binarize_check.isChecked():
                raise BuildError("Защита P3D требует включенной бинаризации P3D.")
            self._require_file(self.advanced_settings.get("p3d_obfuscator_exe", ""), "P3DObfuscator.exe")
        if self.convert_config_check.isChecked():
            self._require_file(self.advanced_settings.get("cfgconvert_exe", ""), "CfgConvert.exe")
        needs_signing_tools = self.sign_pbos_check.isChecked() and any(
            not addon_name.upper().endswith("_SERVER") for addon_name in selected_addons
        )
        if needs_signing_tools:
            self._require_file(self.advanced_settings.get("dssignfile_exe", ""), "DSSignFile.exe")
            self._require_file(self.advanced_settings.get("private_key", ""), "Private key")

        log_path = str(create_build_log_path())
        settings = {
            "source_root": source_root,
            "output_root_dir": output_root,
            "output_server_root_dir": output_root_server,
            "pbo_name": self.pbo_name_edit.text().strip(),
            "use_binarize": self.use_binarize_check.isChecked(),
            "protect_p3d": self.protect_p3d_check.isChecked(),
            "convert_config": self.convert_config_check.isChecked(),
            "sign_pbos": self.sign_pbos_check.isChecked(),
            "force_rebuild": self.force_rebuild_check.isChecked(),
            "preflight_before_build": self.preflight_before_build_check.isChecked(),
            "binarize_exe": self.advanced_settings.get("binarize_exe", ""),
            "cfgconvert_exe": self.advanced_settings.get("cfgconvert_exe", ""),
            "p3d_obfuscator_exe": self.advanced_settings.get("p3d_obfuscator_exe", ""),
            "dssignfile_exe": self.advanced_settings.get("dssignfile_exe", ""),
            "private_key": self.advanced_settings.get("private_key", ""),
            "project_root": self.advanced_settings.get("project_root", "") or DEFAULT_PROJECT_ROOT,
            "temp_dir": self.advanced_settings.get("temp_dir", "") or DEFAULT_TEMP_DIR,
            "exclude_patterns": self.advanced_settings.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS),
            "max_processes": int(self.advanced_settings.get("max_processes", get_default_max_processes())),
            "selected_addons": selected_addons,
            "log_file": log_path,
        }
        settings.update(self.collect_preflight_check_settings())
        self.save_path_settings()
        return settings

    def _require_file(self, path, label):
        if not path:
            raise BuildError(tr_text("select_required", self.current_language, label=label))
        if not os.path.isfile(path):
            raise BuildError(tr_text("file_missing", self.current_language, label=label, path=path))

    def start_build(self):
        if self.is_building:
            return
        try:
            settings = self.validate_settings()
        except Exception as error:
            QMessageBox.critical(self, APP_TITLE, str(error))
            return
        self._open_log(settings.get("log_file", ""))
        self._set_running(True, tr_text("build_running_status", self.current_language), "building")
        self.log("Starting build...")
        if self.current_log_path:
            self.log(f"Log file: {self.current_log_path}")
        self.worker = BuildWorker("build", settings, parent=self)
        self._connect_worker()
        self.worker.start()
        self._show_build_progress_dialog()

    def start_preflight(self):
        if self.is_building:
            return
        try:
            settings, targets = self.validate_preflight_settings()
        except Exception as error:
            QMessageBox.critical(self, APP_TITLE, str(error))
            return
        self._open_log(str(create_build_log_path()))
        settings["log_file"] = self.current_log_path
        self._set_running(True, tr_text("preflight_running_status", self.current_language), "preflight")
        self.log("Starting preflight check...")
        if self.current_log_path:
            self.log(f"Log file: {self.current_log_path}")
        self.worker = BuildWorker("preflight", settings, targets, parent=self)
        self._connect_worker()
        self.worker.start()

    def _connect_worker(self):
        self.worker.log_message.connect(self.log)
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.build_done.connect(self.on_build_done)
        self.worker.preflight_done.connect(self.on_preflight_done)
        self.worker.failed.connect(self.on_worker_failed)

    def start_update_check(self):
        if self.update_check_worker is not None and self.update_check_worker.isRunning():
            return
        self.update_check_worker = UpdateCheckWorker(self)
        self.update_check_worker.update_found.connect(self.on_update_found)
        self.update_check_worker.failed.connect(self.on_update_check_failed)
        self.update_check_worker.start()

    def on_update_check_failed(self, message):
        self.log(f"Update check skipped/failed: {message}")

    def on_update_found(self, update_info):
        message = tr_text(
            "update_available_message",
            self.current_language,
            version=update_info.tag_name,
            current=APP_VERSION,
        )
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(tr_text("update_available_title", self.current_language))
        dialog.setText(message)
        install_button = dialog.addButton(
            tr_text("update_button_install", self.current_language),
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(
            tr_text("update_button_later", self.current_language),
            QMessageBox.ButtonRole.RejectRole,
        )
        dialog.setDefaultButton(install_button)
        dialog.exec()
        if dialog.clickedButton() == install_button:
            self.start_update_install(update_info)

    def start_update_install(self, update_info):
        self._set_running(True, tr_text("update_installing_status", self.current_language), "building")
        self._show_update_progress_dialog()
        self.update_install_worker = UpdateInstallWorker(update_info, self)
        self.update_install_worker.progress_changed.connect(self.on_update_download_progress)
        self.update_install_worker.started.connect(self.on_update_install_started)
        self.update_install_worker.failed.connect(self.on_update_install_failed)
        self.update_install_worker.start()

    def on_update_download_progress(self, current, total, label):
        if not self.update_progress_dialog:
            return
        display_label = tr_text("update_progress_message", self.current_language)
        if total > 0:
            percent = min(100, int((current / total) * 100))
            display_label = f"{display_label} {percent}%"
        self.update_progress_dialog.set_progress(current, total, display_label)

    def on_update_install_started(self):
        if self.update_progress_dialog:
            self.update_progress_dialog.set_message(tr_text("update_replacing_message", self.current_language))
        QTimer.singleShot(250, self._quit_for_update)

    def _quit_for_update(self):
        self._close_update_progress_dialog()
        QApplication.quit()

    def on_update_install_failed(self, message):
        self._close_update_progress_dialog()
        self._set_running(False, tr_text("error_status", self.current_language), "error")
        QMessageBox.critical(
            self,
            APP_TITLE,
            tr_text("update_failed_message", self.current_language, error=message),
        )

    def _set_running(self, running, status_text, status_kind):
        self.is_building = running
        for button in (self.build_button, self.preflight_button):
            button.setEnabled(not running)
        self.progress.setValue(0)
        self.set_status(status_text, status_kind)

    def on_progress(self, current, total):
        maximum = max(total, 1)
        self.progress.setRange(0, maximum)
        self.progress.setValue(current)
        self.set_status(tr_text("working_status", self.current_language, current=current, maximum=maximum), "building")

    def on_build_done(self):
        self._close_build_progress_dialog()
        self._finish_worker(tr_text("build_finished_status", self.current_language), tr_text("build_finished_message", self.current_language), "success")

    def on_preflight_done(self, errors, warnings):
        self._set_running(False, tr_text("preflight_finished_status", self.current_language), "success")
        self.progress.setValue(self.progress.maximum())
        self.close_current_log_file()
        if errors:
            message = tr_text("preflight_errors", self.current_language, errors=errors, warnings=warnings)
            self.show_log_dialog(tr_text("preflight_log", self.current_language), message)
            QMessageBox.critical(self, APP_TITLE, message)
        elif warnings:
            QMessageBox.warning(self, APP_TITLE, tr_text("preflight_warnings", self.current_language, warnings=warnings))
        else:
            QMessageBox.information(self, APP_TITLE, tr_text("preflight_ok", self.current_language))

    def on_worker_failed(self, message):
        self._close_build_progress_dialog()
        self.log("")
        self.log(f"ERROR: {message}")
        self._set_running(False, tr_text("error_status", self.current_language), "error")
        self.close_current_log_file()
        self.show_log_dialog(tr_text("build_log", self.current_language), message)
        QMessageBox.critical(self, APP_TITLE, message)

    def _finish_worker(self, status, message, kind):
        self._set_running(False, status, kind)
        self.progress.setValue(self.progress.maximum())
        self.close_current_log_file()
        QMessageBox.information(self, APP_TITLE, message)

    def _show_build_progress_dialog(self):
        self._close_build_progress_dialog()
        self.build_progress_dialog = BuildProgressDialog(self, self.current_language)
        self.build_progress_dialog.show()

    def _close_build_progress_dialog(self):
        if not self.build_progress_dialog:
            return
        self.build_progress_dialog.finish()
        self.build_progress_dialog.deleteLater()
        self.build_progress_dialog = None

    def _show_update_progress_dialog(self):
        self._close_update_progress_dialog()
        self.update_progress_dialog = UpdateProgressDialog(self, self.current_language)
        self.update_progress_dialog.show()

    def _close_update_progress_dialog(self):
        if not self.update_progress_dialog:
            return
        self.update_progress_dialog.finish()
        self.update_progress_dialog.deleteLater()
        self.update_progress_dialog = None

    def _open_log(self, path):
        self.close_current_log_file()
        self.current_log_path = path
        self.log_lines = []
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.current_log_file = open(path, "w", encoding="utf-8")

    def close_current_log_file(self):
        if self.current_log_file:
            try:
                self.current_log_file.close()
            except Exception:
                pass
            self.current_log_file = None

    def log(self, message):
        line = str(message)
        self.log_lines.append(line)
        try:
            print(line, flush=True)
        except Exception:
            pass
        if self.current_log_file:
            try:
                self.current_log_file.write(line + "\n")
                self.current_log_file.flush()
            except Exception:
                pass

    def _log_color(self, line):
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("ERROR") or " ERROR:" in upper:
            return "#ff7070"
        if upper.startswith("WARNING") or " WARNING:" in upper:
            return "#d6aa5f"
        if "BUILD FINISHED" in upper or "COMPLETED SUCCESSFULLY" in upper or upper.endswith(" OK"):
            return "#7fb087"
        if stripped.startswith("=" * 8):
            return "#8f96a3"
        if any(token in stripped for token in ("Binarize", "CfgConvert", "DSSignFile", "Preflight")):
            return "#8ab4f8"
        return ""

    def clear_log(self):
        self.log_lines.clear()
        if self.current_log_path and os.path.isfile(self.current_log_path):
            try:
                open(self.current_log_path, "w", encoding="utf-8").close()
            except Exception:
                pass

    def clear_log_from_settings(self):
        if self.is_building:
            QMessageBox.warning(self, APP_TITLE, tr_text("cannot_clear_logs", self.current_language))
            return

        self.log_lines.clear()
        self.current_log_path = ""
        logs_dir = get_logs_dir()
        log_files = [path for path in logs_dir.iterdir() if path.is_file()]
        if not log_files:
            QMessageBox.information(self, APP_TITLE, tr_text("logs_empty", self.current_language))
            return

        deleted = 0
        failed = []
        for log_file in log_files:
            try:
                log_file.unlink()
                deleted += 1
            except Exception as error:
                failed.append(f"{log_file}: {error}")

        if failed:
            details = "\n".join(failed[:5])
            if len(failed) > 5:
                details += "\n" + tr_text("and_more", self.current_language, count=len(failed) - 5)
            QMessageBox.warning(self, APP_TITLE, tr_text("logs_clear_partial", self.current_language, count=deleted, details=details))
            return

        QMessageBox.information(self, APP_TITLE, tr_text("logs_cleared", self.current_language, count=deleted))

    def show_log_dialog(self, title="Log", message=""):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setStyleSheet(QT_STYLE)
        dialog.resize(720, 520)
        dialog.setMinimumSize(620, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        heading = QLabel(message or title)
        heading.setObjectName("DialogTitle")
        heading.setWordWrap(True)
        heading.setMaximumHeight(96)
        heading.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout.addWidget(heading)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Consolas", 9))
        text.setLineWrapMode(QTextEdit.NoWrap)
        for line in self.log_lines:
            color = self._log_color(line)
            escaped = html.escape(line)
            if color:
                text.append(f'<span style="color:{color}">{escaped}</span>')
            else:
                text.append(escaped)
        text.moveCursor(QTextCursor.End)
        layout.addWidget(text, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if self.current_log_path:
            open_button = QPushButton(tr_text("open_file", self.current_language))
            open_button.clicked.connect(lambda: self._open_path(self.current_log_path))
            buttons.addWidget(open_button)
        close_button = QPushButton(tr_text("close", self.current_language))
        close_button.setObjectName("PrimaryButton")
        close_button.clicked.connect(dialog.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        dialog.exec()

    def clear_temp_from_ui(self):
        if self.is_building:
            QMessageBox.warning(self, APP_TITLE, tr_text("cannot_clear_temp", self.current_language))
            return
        temp_dir = self.advanced_settings.get("temp_dir", "") or DEFAULT_TEMP_DIR
        if QMessageBox.question(self, APP_TITLE, tr_text("clear_temp_confirm", self.current_language, path=temp_dir)) != QMessageBox.Yes:
            return
        try:
            clear_temp_folder(temp_dir, self.log, self.source_root_row.text(), self.output_root_row.text())
            QMessageBox.information(self, APP_TITLE, tr_text("temp_cleared", self.current_language))
        except Exception as error:
            self.log(f"ERROR: {error}")
            QMessageBox.critical(self, APP_TITLE, str(error))

    def clear_full_temp_from_ui(self):
        if self.is_building:
            QMessageBox.warning(self, APP_TITLE, tr_text("cannot_clear_all_temp", self.current_language))
            return
        temp_dir = self.advanced_settings.get("temp_dir", "") or DEFAULT_TEMP_DIR
        if QMessageBox.question(self, APP_TITLE, tr_text("clear_all_temp_confirm", self.current_language, path=temp_dir)) != QMessageBox.Yes:
            return
        try:
            clear_full_temp_folder(temp_dir, self.log, self.source_root_row.text(), self.output_root_row.text())
            QMessageBox.information(self, APP_TITLE, tr_text("all_temp_cleared", self.current_language))
        except Exception as error:
            self.log(f"ERROR: {error}")
            QMessageBox.critical(self, APP_TITLE, str(error))

    def clear_build_cache_from_ui(self):
        if self.is_building:
            QMessageBox.warning(self, APP_TITLE, tr_text("cannot_clear_cache", self.current_language))
            return
        source_root = self.source_root_row.text()
        selected_addons = self.get_selected_addon_names()
        if not source_root or not os.path.isdir(source_root):
            QMessageBox.warning(self, APP_TITLE, tr_text("source_root_missing", self.current_language, path=source_root))
            return
        if not selected_addons:
            QMessageBox.warning(self, APP_TITLE, tr_text("select_addon", self.current_language))
            return
        if QMessageBox.question(self, APP_TITLE, tr_text("clear_cache_confirm", self.current_language)) != QMessageBox.Yes:
            return
        cache = load_build_cache()
        cache_key_root = os.path.abspath(source_root).lower()
        source_cache = cache.get(cache_key_root, {})
        cleared = 0
        for addon_name in selected_addons:
            if addon_name in source_cache:
                del source_cache[addon_name]
                cleared += 1
                self.log(f"Cleared build cache for addon: {addon_name}")
        if source_cache:
            cache[cache_key_root] = source_cache
        elif cache_key_root in cache:
            del cache[cache_key_root]
        save_build_cache(cache)
        QMessageBox.information(self, APP_TITLE, tr_text("cache_cleared", self.current_language, count=cleared))

    def open_logs_folder(self):
        self._open_path(str(get_logs_dir()))

    def open_latest_log(self):
        logs_dir = get_logs_dir()
        log_files = list(logs_dir.glob("build_*.log"))
        if not log_files:
            QMessageBox.information(self, APP_TITLE, tr_text("no_build_logs", self.current_language))
            return
        latest = max(log_files, key=lambda path: path.stat().st_mtime)
        self._open_path(str(latest))

    def _open_path(self, path):
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as error:
            QMessageBox.warning(self, APP_TITLE, str(error))

    def show_about(self):
        QMessageBox.information(
            self,
            APP_TITLE,
            tr_text(
                "about_message",
                self.current_language,
                title=APP_TITLE,
                version=APP_VERSION,
                author=APP_AUTHOR,
                license=tr_text("footer_license", self.current_language),
            ),
        )

    def closeEvent(self, event):
        self.save_path_settings()
        self.close_current_log_file()
        super().closeEvent(event)


QT_STYLE = """
* {
    font-family: "Segoe UI", "Arial";
    font-size: 10pt;
    color: #eef7ff;
}
QMainWindow {
    background: #4e555f;
}
QDialog {
    background: #4e555f;
}
QWidget#Root {
    background: #4e555f;
}
QWidget {
    background: transparent;
}
#Header, #Card {
    background: #20252b;
    border: 1px solid #8f7658;
    border-radius: 8px;
}
#Header {
    background: #20252b;
}
#Footer {
    background: transparent;
}
#AppTitle {
    font-size: 14pt;
    font-weight: 700;
    color: #f8fbff;
}
#DialogTitle {
    font-size: 15pt;
    font-weight: 700;
    color: #f8fbff;
}
#MainTitle {
    font-size: 18pt;
    font-weight: 700;
    color: #f8fbff;
}
#CardTitle {
    color: #ff9300;
    font-weight: 700;
    padding: 3px 0 5px 0;
}
#CardTitleInline {
    color: #65efff;
    font-weight: 700;
    padding: 0 0 2px 0;
}
#Muted, #FieldLabel {
    color: #9bb7bc;
}
#FieldLabel {
    font-size: 9pt;
}
#StatusBadge {
    background: #15191f;
    border: 1px solid #8f7658;
    border-radius: 7px;
    max-height: 25px;
}
QLabel#StatusText {
    font-size: 8pt;
}
QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QSpinBox, QComboBox {
    background: #15191f;
    border: 1px solid #8f7658;
    border-radius: 6px;
    padding: 5px;
    color: #eef7ff;
    selection-background-color: #00a5dc;
}
QComboBox {
    padding-right: 20px;
}
QComboBox::drop-down {
    border: 0;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #15191f;
    border: 1px solid #8f7658;
    selection-background-color: #00a5dc;
    outline: 0;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QListWidget:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #c28a45;
}
QListWidget::item {
    min-height: 24px;
    padding: 4px 7px;
    border-radius: 4px;
}
QListWidget::item:hover {
    background: #2f6f83;
}
QListWidget::item:selected {
    background: #00a5dc;
}
QCheckBox {
    spacing: 7px;
    color: #eef7ff;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #8f7658;
    border-radius: 4px;
    background: rgba(4, 10, 22, 218);
}
QCheckBox::indicator:hover {
    border: 1px solid #c28a45;
}
QCheckBox::indicator:checked {
    background: #00a5dc;
    border: 1px solid #c28a45;
}
QPushButton, QToolButton {
    background: #20252b;
    border: 1px solid #8f7658;
    border-radius: 6px;
    padding: 5px 8px;
    color: #f8fbff;
    min-height: 24px;
}
QPushButton:hover, QToolButton:hover {
    background: #2c333b;
    border: 1px solid #c28a45;
}
QPushButton:pressed, QToolButton:pressed {
    background: #3b2e1c;
}
QPushButton:disabled {
    color: #73869a;
    background: rgba(17, 24, 38, 180);
    border: 1px solid rgba(83, 104, 128, 75);
}
#PrimaryButton {
    background: #ff9300;
    border: 1px solid #ff9300;
    font-weight: 700;
    color: #091017;
}
#PrimaryButton:hover {
    background: #ffb24a;
}
#GhostButton {
    background: #20252b;
}
#AboutButton {
    background: #20252b;
    border: 1px solid #8f7658;
    border-radius: 6px;
    padding: 0;
    font-size: 9pt;
}
#AboutButton:hover {
    background: #2c333b;
    border: 1px solid #c28a45;
}
#HeaderIconButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
}
#AddonIconButton {
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0;
}
#PathIconButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}
QProgressBar {
    background: #15191f;
    border: 1px solid #8f7658;
    border-radius: 5px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: #00a5dc;
    border-radius: 5px;
}
QSplitter::handle {
    background: transparent;
    width: 8px;
}
QScrollArea {
    border: 0;
    background: transparent;
}
QScrollBar:vertical {
    background: #15191f;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #ff9300;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


def run_qt_app():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle("Fusion")
    icon_path = Path(__file__).parent / "assets" / "icon.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
        if os.name == "nt":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RaiZo.PBOBuilder")
            except Exception:
                pass
    window = ModernPboBuilderWindow()
    window.show()
    return app.exec()
