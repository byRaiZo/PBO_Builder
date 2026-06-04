import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .build import build_all
from .constants import *
from .errors import BuildError
from .files import clear_full_temp_folder, clear_temp_folder
from .preflight import run_preflight_for_targets
from .system import *
from .targets import detect_addon_targets
from .tools import find_cfgconvert, find_dayz_binarize, find_dssignfile, find_p3d_obfuscator

class ToolTip:
    def __init__(self, widget, text, delay_ms=500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id = None
        self.window = None
        widget.bind("<Enter>", self.schedule)
        widget.bind("<Leave>", self.hide)
        widget.bind("<ButtonPress>", self.hide)

    def schedule(self, event=None):
        self.cancel()
        self.after_id = self.widget.after(self.delay_ms, self.show)

    def cancel(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self):
        if self.window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        self.window.configure(bg=GRAPHITE_BORDER)
        label = tk.Label(
            self.window,
            text=self.text,
            justify="left",
            bg=GRAPHITE_FIELD,
            fg=GRAPHITE_TEXT,
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=5,
            font=("Segoe UI", 9),
            wraplength=440,
        )
        label.pack(ipadx=1, ipady=1)

    def hide(self, event=None):
        self.cancel()
        if self.window:
            self.window.destroy()
            self.window = None

def add_tooltip(widget, text):
    if text:
        ToolTip(widget, text)

class PboBuilderByRaiZoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.saved_settings = load_saved_settings()
        self.title(APP_TITLE)
        self.set_window_icon()

        saved_geometry = self.saved_settings.get("window_geometry", "")
        self.geometry(saved_geometry if is_safe_window_geometry(saved_geometry) else "1080x900")
        self.minsize(960, 830)
        self._apply_graphite_theme()

        self.log_queue = queue.Queue()
        self.worker_thread = None
        self.is_building = False
        self.current_log_file = None
        self.current_log_path = ""
        self.current_addon_targets = []
        self.geometry_save_after_id = None
        self.status_var = tk.StringVar(value="Idle")

        saved_pbo_name = self.saved_settings.get("pbo_name", self.saved_settings.get("prefix_root", ""))
        saved_output_root = self.saved_settings.get("output_root", self.saved_settings.get("output_addons", ""))
        self.source_root_var = tk.StringVar(value=self.saved_settings.get("source_root", ""))
        self.output_root_var = tk.StringVar(value=saved_output_root)
        self.pbo_name_var = tk.StringVar(value=saved_pbo_name)
        self.use_binarize_var = tk.BooleanVar(value=self.saved_settings.get("use_binarize", True))
        self.protect_p3d_var = tk.BooleanVar(value=self.saved_settings.get("protect_p3d", False))
        self.convert_config_var = tk.BooleanVar(value=self.saved_settings.get("convert_config", True))
        self.sign_pbos_var = tk.BooleanVar(value=self.saved_settings.get("sign_pbos", True))
        self.force_rebuild_var = tk.BooleanVar(value=self.saved_settings.get("force_rebuild", False))
        self.preflight_before_build_var = tk.BooleanVar(value=self.saved_settings.get("preflight_before_build", False))
        self.max_processes_var = tk.IntVar(value=self.saved_settings.get("max_processes", get_default_max_processes()))
        self.binarize_exe_var = tk.StringVar(value=self.saved_settings.get("binarize_exe", find_dayz_binarize()))
        self.p3d_obfuscator_exe_var = tk.StringVar(value=self.saved_settings.get("p3d_obfuscator_exe", find_p3d_obfuscator()))
        self.cfgconvert_exe_var = tk.StringVar(value=self.saved_settings.get("cfgconvert_exe", find_cfgconvert()))
        self.dssignfile_exe_var = tk.StringVar(value=self.saved_settings.get("dssignfile_exe", find_dssignfile()))
        self.private_key_var = tk.StringVar(value=self.saved_settings.get("private_key", ""))
        self.project_root_var = tk.StringVar(value=self.saved_settings.get("project_root", DEFAULT_PROJECT_ROOT))
        self.temp_dir_var = tk.StringVar(value=self.saved_settings.get("temp_dir", DEFAULT_TEMP_DIR))
        self.exclude_patterns_var = tk.StringVar(value=self.saved_settings.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS))

        self._build_ui()
        self.set_status("Idle", "ready")
        self.refresh_addon_list(select_saved=True)
        self._poll_log_queue()

        self.bind("<Configure>", self.on_window_configure)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def set_window_icon(self):
        icon_path = resource_path(APP_ICON_FILE)
        if not os.path.isfile(icon_path):
            return
        try:
            self.iconbitmap(icon_path)
        except Exception:
            try:
                icon_image = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon_image)
            except Exception:
                pass

    def _apply_graphite_theme(self):
        self.configure(bg=GRAPHITE_BG)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=GRAPHITE_BG, foreground=GRAPHITE_TEXT, fieldbackground=GRAPHITE_FIELD, font=("Segoe UI", 10))
        style.configure("TFrame", background=GRAPHITE_BG)
        style.configure("Header.TFrame", background=GRAPHITE_HEADER)
        style.configure("Card.TFrame", background=GRAPHITE_CARD)
        style.configure("TLabelframe", background=GRAPHITE_CARD, foreground=GRAPHITE_TEXT, bordercolor=GRAPHITE_BORDER_SOFT, lightcolor=GRAPHITE_CARD, darkcolor=GRAPHITE_CARD, relief="flat", padding=18)
        style.configure("TLabelframe.Label", background=GRAPHITE_CARD, foreground=GRAPHITE_TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=GRAPHITE_BG, foreground=GRAPHITE_TEXT)
        style.configure("Header.TLabel", background=GRAPHITE_HEADER, foreground=GRAPHITE_TEXT)
        style.configure("TCheckbutton", background=GRAPHITE_CARD, foreground=GRAPHITE_TEXT, padding=5)
        style.configure("TButton", background=GRAPHITE_CARD_SOFT, foreground=GRAPHITE_TEXT, bordercolor=GRAPHITE_CARD_SOFT, lightcolor=GRAPHITE_CARD_SOFT, darkcolor=GRAPHITE_CARD_SOFT, focusthickness=0, focuscolor=GRAPHITE_CARD_SOFT, relief="flat", padding=(12, 8))
        style.configure("TEntry", fieldbackground=GRAPHITE_FIELD, background=GRAPHITE_FIELD, foreground=GRAPHITE_TEXT, insertcolor=GRAPHITE_TEXT, bordercolor=GRAPHITE_BORDER, lightcolor=GRAPHITE_FIELD, darkcolor=GRAPHITE_FIELD, relief="flat", padding=7)
        style.configure("TSpinbox", fieldbackground=GRAPHITE_FIELD, background=GRAPHITE_FIELD, foreground=GRAPHITE_TEXT, insertcolor=GRAPHITE_TEXT, bordercolor=GRAPHITE_BORDER, lightcolor=GRAPHITE_FIELD, darkcolor=GRAPHITE_FIELD, relief="flat", padding=6)
        style.configure("Horizontal.TProgressbar", background=GRAPHITE_ACCENT, troughcolor=GRAPHITE_CARD, bordercolor=GRAPHITE_CARD, lightcolor=GRAPHITE_ACCENT, darkcolor=GRAPHITE_ACCENT_DARK)
        style.configure("Vertical.TScrollbar", background=GRAPHITE_CARD_SOFT, troughcolor=GRAPHITE_BG, bordercolor=GRAPHITE_BG, arrowcolor=GRAPHITE_MUTED, relief="flat")
        style.map("TButton", background=[("active", GRAPHITE_BORDER), ("pressed", GRAPHITE_ACCENT_DARK)], foreground=[("disabled", GRAPHITE_MUTED)])
        style.map("TCheckbutton", background=[("active", GRAPHITE_CARD)], foreground=[("disabled", GRAPHITE_MUTED)])
        style.map("TEntry", fieldbackground=[("readonly", GRAPHITE_FIELD), ("disabled", GRAPHITE_CARD)], foreground=[("disabled", GRAPHITE_MUTED)])
        style.map("TSpinbox", fieldbackground=[("readonly", GRAPHITE_FIELD), ("disabled", GRAPHITE_CARD)], foreground=[("disabled", GRAPHITE_MUTED)])

    def _build_ui(self):
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=GRAPHITE_HEADER, bd=0, highlightthickness=0)
        header.pack(fill="x", pady=(0, 10), ipady=5)

        header_left = tk.Frame(header, bg=GRAPHITE_HEADER, bd=0, highlightthickness=0)
        header_left.pack(side="left", fill="x", expand=True, padx=(14, 8))

        title = tk.Label(
            header_left,
            text=APP_TITLE,
            bg=GRAPHITE_HEADER,
            fg=GRAPHITE_TEXT,
            font=("Segoe UI", 18, "bold"),
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            header_left,
            text="Build selected DayZ addons into Addons and Keys output folders",
            bg=GRAPHITE_HEADER,
            fg=GRAPHITE_MUTED,
            font=("Segoe UI", 9),
        )
        subtitle.pack(anchor="w", pady=(0, 0))

        header_right = tk.Frame(header, bg=GRAPHITE_HEADER, bd=0, highlightthickness=0)
        header_right.pack(side="right", padx=(8, 14))

        self.about_button = tk.Button(
            header_right,
            text="About",
            command=self.open_about_window,
            bg=GRAPHITE_CARD_SOFT,
            fg=GRAPHITE_TEXT,
            activebackground=GRAPHITE_BORDER,
            activeforeground=GRAPHITE_TEXT,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=6,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self.about_button.pack(side="right")
        self._attach_button_hover(self.about_button, GRAPHITE_CARD_SOFT, GRAPHITE_BORDER, GRAPHITE_BORDER)
        add_tooltip(self.about_button, "Show version, author, and safety information.")

        self.licence_button = tk.Button(
            header_right,
            text="Licence",
            command=self.open_licence_window,
            bg=GRAPHITE_CARD_SOFT,
            fg=GRAPHITE_TEXT,
            activebackground=GRAPHITE_BORDER,
            activeforeground=GRAPHITE_TEXT,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=6,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self.licence_button.pack(side="right", padx=(0, 8))
        self._attach_button_hover(self.licence_button, GRAPHITE_CARD_SOFT, GRAPHITE_BORDER, GRAPHITE_BORDER)
        add_tooltip(self.licence_button, "Show licence terms and warranty disclaimer.")

        self.options_button = tk.Button(
            header_right,
            text="Options",
            command=self.open_options_window,
            bg=GRAPHITE_CARD_SOFT,
            fg=GRAPHITE_TEXT,
            activebackground=GRAPHITE_BORDER,
            activeforeground=GRAPHITE_TEXT,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=6,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self.options_button.pack(side="right", padx=(0, 8))
        self._attach_button_hover(self.options_button, GRAPHITE_CARD_SOFT, GRAPHITE_BORDER, GRAPHITE_BORDER)
        add_tooltip(self.options_button, "Open tool paths, temp folder, project root, private key, and exclude pattern settings.")

        settings = ttk.LabelFrame(outer, text="Build settings", padding=10)
        settings.pack(fill="x", pady=(0, 10))
        self._add_folder_row(
            settings,
            0,
            "Source root",
            self.source_root_var,
            self.choose_source_root,
            "Folder containing addon folders. If this folder itself contains config.cpp, it will be built as one addon.",
            self.open_source_root_folder,
            "Open the selected Source root folder in Windows Explorer.",
        )
        self._add_folder_row(
            settings,
            1,
            "Output root",
            self.output_root_var,
            self.choose_output_root,
            "Root output folder. The builder creates Addons and Keys inside this folder automatically.",
            self.open_output_folder,
            "Open the selected Output root folder in Windows Explorer.",
        )
        label = ttk.Label(settings, text="PBO name")
        label.grid(row=2, column=0, sticky="w", pady=3)
        add_tooltip(label, "Optional PBO filename override. Only used when exactly one addon is selected.")
        entry = ttk.Entry(settings, textvariable=self.pbo_name_var)
        entry.grid(row=2, column=1, sticky="ew", pady=3, padx=(8, 8))
        add_tooltip(entry, "Leave empty to use the selected addon folder name. Only applies to single-addon builds.")
        hint_frame = ttk.Frame(settings, width=230)
        hint_frame.grid(row=2, column=2, sticky="e", pady=3)
        hint_frame.grid_propagate(False)

        hint = ttk.Label(hint_frame, text="Optional, single-addon builds only", foreground=GRAPHITE_MUTED)
        hint.pack(side="right", fill="x")
        add_tooltip(hint, "For multi-addon builds, each PBO always uses its addon folder name.")

        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(2, minsize=230)

        options_frame = ttk.LabelFrame(outer, text="Build options", padding=12)
        options_frame.pack(fill="x", pady=(0, 10))

        pipeline_label = ttk.Label(options_frame, text="Build pipeline", foreground=GRAPHITE_MUTED)
        pipeline_label.grid(row=0, column=0, sticky="w", pady=(0, 5), padx=(0, 14))
        add_tooltip(pipeline_label, "Main build steps that change how addon files are processed before packing.")
        self._add_checkbutton(options_frame, "Binarize P3D", self.use_binarize_var, 0, 1, "Run DayZ Tools binarize.exe before packing addons that contain P3D files.")
        self._add_checkbutton(options_frame, "CPP to BIN", self.convert_config_var, 0, 2, "Convert root and nested config.cpp files to config.bin in staging before packing.")
        self._add_checkbutton(options_frame, "Sign PBOs", self.sign_pbos_var, 0, 3, "Sign built PBOs with DSSignFile.exe and your .biprivatekey.")
        self._add_checkbutton(options_frame, "Protect P3D", self.protect_p3d_var, 1, 1, "Run P3DObfuscator.exe after P3D binarize and before packing.")

        safety_label = ttk.Label(options_frame, text="Safety", foreground=GRAPHITE_MUTED)
        safety_label.grid(row=2, column=0, sticky="w", pady=(0, 5), padx=(0, 14))
        add_tooltip(safety_label, "Safety and validation options. Content-safe cache checks are always enabled internally.")
        self._add_checkbutton(options_frame, "Force rebuild", self.force_rebuild_var, 2, 1, "Ignore the build cache, refresh selected addon temp folders, and rebuild all selected addons.")
        self._add_checkbutton(options_frame, "Preflight before build", self.preflight_before_build_var, 2, 2, "Run syntax and path checks before building. Errors stop the build; warnings only get logged.")

        performance_label = ttk.Label(options_frame, text="Performance", foreground=GRAPHITE_MUTED)
        performance_label.grid(row=3, column=0, sticky="w", pady=(0, 2), padx=(0, 14))
        add_tooltip(performance_label, "Performance tuning for external DayZ Tools processes.")

        max_frame = ttk.Frame(options_frame)
        max_frame.grid(row=3, column=1, columnspan=3, sticky="w", pady=(0, 2), padx=(0, 0))
        label = ttk.Label(max_frame, text="Max processes")
        label.pack(side="left")
        add_tooltip(label, f"Passed to binarize.exe as maxProcesses. Default uses all available logical threads: {get_default_max_processes()}.")
        spinbox = ttk.Spinbox(max_frame, from_=1, to=64, textvariable=self.max_processes_var, width=8)
        spinbox.pack(side="left", padx=(8, 0))
        add_tooltip(spinbox, "How many worker processes Binarize may use. Higher is not always faster, especially on slower CPUs or disks.")

        options_frame.columnconfigure(4, weight=1)

        addons_frame = ttk.LabelFrame(outer, text="Addon selection", padding=12)
        addons_frame.pack(fill="both", expand=True, pady=(0, 10))
        addons_frame.columnconfigure(0, weight=1)
        addons_frame.rowconfigure(0, weight=1)
        self.addon_listbox = tk.Listbox(
            addons_frame,
            selectmode="extended",
            bg=GRAPHITE_FIELD,
            fg=GRAPHITE_TEXT,
            selectbackground="#6f2f2f",
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=GRAPHITE_BORDER,
            highlightcolor=GRAPHITE_ACCENT,
            font=("Consolas", 10),
            height=4,
            exportselection=False,
        )
        self.addon_listbox.grid(row=0, column=0, sticky="nsew")
        add_tooltip(self.addon_listbox, "Select which addons to build. Hold Ctrl or Shift to select multiple entries.")
        addon_scrollbar = ttk.Scrollbar(addons_frame, command=self.addon_listbox.yview)
        addon_scrollbar.grid(row=0, column=1, sticky="ns")
        self.addon_listbox.configure(yscrollcommand=addon_scrollbar.set)
        self.addon_listbox.bind("<<ListboxSelect>>", lambda event: self.save_path_settings())
        addon_buttons = ttk.Frame(addons_frame)
        addon_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        refresh_button = ttk.Button(addon_buttons, text="Refresh addons", command=self.refresh_addon_list)
        refresh_button.pack(side="left")
        add_tooltip(refresh_button, "Refresh the addon list from the selected Source root.")
        select_all_button = ttk.Button(addon_buttons, text="Select all", command=self.select_all_addons)
        select_all_button.pack(side="left", padx=(8, 0))
        add_tooltip(select_all_button, "Select all detected addons for the next build.")
        select_none_button = ttk.Button(addon_buttons, text="Select none", command=self.select_no_addons)
        select_none_button.pack(side="left", padx=(8, 0))
        add_tooltip(select_none_button, "Clear the addon selection.")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(6, 0))
        primary_actions = ttk.Frame(actions)
        primary_actions.pack(fill="x")
        secondary_actions = ttk.Frame(actions)
        secondary_actions.pack(fill="x", pady=(4, 0))
        self.build_button = self._make_action_button(primary_actions, "Build PBOs", self.start_build, primary=True, large=True, tooltip="Build the currently selected addon(s).")
        self.preflight_button = self._make_action_button(primary_actions, "Preflight", self.start_preflight, variant="preflight", large=True, tooltip="Check selected addon(s) for config syntax errors and missing referenced files before packing.")
        self.status_badge = tk.Label(
            primary_actions,
            text="Ready",
            bg=GRAPHITE_READY,
            fg="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=5,
            font=("Segoe UI", 9, "bold"),
        )
        self.status_badge.pack(side="left", padx=(14, 6))
        add_tooltip(self.status_badge, "Current builder status.")

        self.status_label = ttk.Label(primary_actions, textvariable=self.status_var, foreground=GRAPHITE_MUTED, width=20)
        self.status_label.pack(side="left", padx=(0, 4))
        add_tooltip(self.status_label, "Current builder status.")
        self.progress = ttk.Progressbar(primary_actions, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.clear_button = self._make_action_button(secondary_actions, "Clear log", self.clear_log, tooltip="Clear the visible log window only. Saved log files are not deleted.")
        self.clear_temp_button = self._make_action_button(secondary_actions, "Clear build temp", self.clear_temp_from_ui, tooltip="Safely clear only PBO Builder(byRaiZo) temp data. Unrelated files are left untouched.")
        self.clear_full_temp_button = self._make_action_button(secondary_actions, "Clear all temp", self.clear_full_temp_from_ui, tooltip="Delete all contents inside the selected temp root after confirmation. Uses the same safety checks as temp cleanup.")
        self.clear_cache_button = self._make_action_button(secondary_actions, "Clear build cache", self.clear_build_cache_from_ui, tooltip="Clear build-cache entries only for the selected source root and selected addon(s).")
        self.open_logs_button = self._make_action_button(secondary_actions, "Open logs", self.open_logs_folder, tooltip="Open the folder containing saved build logs.")
        self.latest_log_button = self._make_action_button(secondary_actions, "Latest log", self.open_latest_log, tooltip="Open the newest saved build log file.")

        log_frame = ttk.LabelFrame(outer, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.log_text = tk.Text(log_frame, wrap="word", height=42, font=("Consolas", 9), bg=GRAPHITE_CARD, fg=GRAPHITE_TEXT, insertbackground=GRAPHITE_TEXT, selectbackground=GRAPHITE_ACCENT_DARK, selectforeground="#ffffff", relief="flat", borderwidth=0, highlightthickness=1, highlightbackground=GRAPHITE_BORDER, highlightcolor=GRAPHITE_ACCENT)
        self.log_text.pack(side="left", fill="both", expand=True)
        self.configure_log_tags()
        add_tooltip(self.log_text, "Build output, Binarize output, signing output, warnings, and errors.")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.version_footer = tk.Label(
            self,
            text=f"v{APP_VERSION}",
            bg=GRAPHITE_BG,
            fg=GRAPHITE_MUTED,
            font=("Segoe UI", 9),
        )
        self.version_footer.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-6)
        add_tooltip(self.version_footer, "Version information.")

    def _add_checkbutton(self, parent, text, variable, row, column, tooltip):
        def refresh_toggle():
            if variable.get():
                checkbox.configure(
                    text="✓ " + text,
                    bg=GRAPHITE_CARD_SOFT,
                    fg=GRAPHITE_TEXT,
                    activebackground=GRAPHITE_BORDER,
                    activeforeground=GRAPHITE_TEXT,
                )
            else:
                checkbox.configure(
                    text="  " + text,
                    bg=GRAPHITE_FIELD,
                    fg=GRAPHITE_MUTED,
                    activebackground=GRAPHITE_CARD_SOFT,
                    activeforeground=GRAPHITE_TEXT,
                )

        def on_toggle():
            refresh_toggle()
            self.save_path_settings()

        checkbox = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=on_toggle,
            indicatoron=False,
            selectcolor=GRAPHITE_CARD_SOFT,
            relief="flat",
            borderwidth=0,
            padx=9,
            pady=4,
            font=("Segoe UI", 9),
            cursor="hand2",
            anchor="center",
        )
        checkbox.grid(row=row, column=column, sticky="w", pady=(0, 4), padx=(0, 8))
        refresh_toggle()
        add_tooltip(checkbox, tooltip)
        return checkbox

    def _attach_button_hover(self, button, normal_bg, hover_bg, pressed_bg=None):
        pressed_bg = pressed_bg or hover_bg

        def on_enter(event=None):
            try:
                if str(button.cget("state")) != "disabled":
                    button.configure(bg=hover_bg, activebackground=pressed_bg)
            except Exception:
                pass

        def on_leave(event=None):
            try:
                button.configure(bg=normal_bg, activebackground=pressed_bg)
            except Exception:
                pass

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def set_status(self, text, state="ready"):
        self.status_var.set(text)

        if not hasattr(self, "status_badge"):
            return

        state_map = {
            "ready": ("Ready", GRAPHITE_READY),
            "building": ("Building", GRAPHITE_BUILDING),
            "preflight": ("Preflight", GRAPHITE_PREFLIGHT),
            "success": ("Done", GRAPHITE_SUCCESS_DARK),
            "error": ("Error", GRAPHITE_ERROR_DARK),
        }

        badge_text, badge_bg = state_map.get(state, state_map["ready"])
        self.status_badge.configure(text=badge_text, bg=badge_bg)

    def _make_action_button(self, parent, text, command, primary=False, tooltip="", variant="", large=False):
        if primary:
            bg = GRAPHITE_ACCENT_DARK
            fg = "#ffffff"
            active_bg = GRAPHITE_ACCENT
            hover_bg = GRAPHITE_ACCENT_HOVER
            active_fg = "#ffffff"
            weight = "bold"
        elif variant == "preflight":
            bg = GRAPHITE_PREFLIGHT
            fg = "#ffffff"
            active_bg = GRAPHITE_PREFLIGHT_ACTIVE
            hover_bg = GRAPHITE_PREFLIGHT_HOVER
            active_fg = "#ffffff"
            weight = "bold"
        else:
            bg = GRAPHITE_CARD_SOFT
            fg = GRAPHITE_TEXT
            active_bg = GRAPHITE_BORDER
            hover_bg = GRAPHITE_BORDER
            active_fg = GRAPHITE_TEXT
            weight = "normal"

        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            relief="flat",
            borderwidth=0,
            padx=14 if large else 9,
            pady=8 if large else 5,
            font=("Segoe UI", 10 if large else 9, weight),
            cursor="hand2",
        )
        button.pack(side="left", padx=(0 if primary else 8, 0))
        self._attach_button_hover(button, bg, hover_bg, active_bg)
        add_tooltip(button, tooltip)
        return button

    def _add_folder_row(self, parent, row, label, variable, command, tooltip="", open_command=None, open_tooltip=""):
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", pady=3)
        add_tooltip(label_widget, tooltip)

        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=3, padx=(8, 8))
        add_tooltip(entry, tooltip)

        action_frame = ttk.Frame(parent, width=230)
        action_frame.grid(row=row, column=2, sticky="e", pady=3)
        action_frame.grid_propagate(False)

        if open_command:
            open_button = ttk.Button(action_frame, text="Open", command=open_command, width=8)
            open_button.pack(side="right")
            add_tooltip(open_button, open_tooltip or "Open the selected folder in Windows Explorer.")

            browse_button = ttk.Button(action_frame, text="Browse", command=command, width=10)
            browse_button.pack(side="right", padx=(0, 6))
            add_tooltip(browse_button, tooltip)
        else:
            browse_button = ttk.Button(action_frame, text="Browse", command=command, width=10)
            browse_button.pack(side="right")
            add_tooltip(browse_button, tooltip)

    def _add_file_row(self, parent, row, label, variable, command, tooltip=""):
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", pady=5)
        add_tooltip(label_widget, tooltip)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(8, 8))
        add_tooltip(entry, tooltip)
        button = ttk.Button(parent, text="Browse", command=command)
        button.grid(row=row, column=2, sticky="e", pady=5)
        add_tooltip(button, tooltip)

    def open_licence_window(self):
        licence = tk.Toplevel(self)
        licence.title("Licence")
        licence.geometry("720x560")
        licence.minsize(600, 420)
        licence.configure(bg=GRAPHITE_BG)
        licence.transient(self)
        licence.grab_set()

        container = ttk.Frame(licence, padding=18)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="Licence", font=("Segoe UI", 20, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(container, text=APP_LICENSE_NAME, foreground=GRAPHITE_MUTED)
        subtitle.pack(anchor="w", pady=(6, 14))

        text = tk.Text(
            container,
            wrap="word",
            bg=GRAPHITE_FIELD,
            fg=GRAPHITE_TEXT,
            insertbackground=GRAPHITE_TEXT,
            selectbackground=GRAPHITE_ACCENT_DARK,
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=GRAPHITE_BORDER,
            highlightcolor=GRAPHITE_ACCENT,
            font=("Segoe UI", 10),
        )
        text.pack(side="left", fill="both", expand=True, pady=(0, 12))
        text.insert("1.0", APP_LICENSE_TEXT)
        text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(container, command=text.yview)
        scrollbar.pack(side="right", fill="y", pady=(0, 12))
        text.configure(yscrollcommand=scrollbar.set)

        close_button = tk.Button(
            container,
            text="Close",
            command=licence.destroy,
            bg=GRAPHITE_CARD_SOFT,
            fg=GRAPHITE_TEXT,
            activebackground=GRAPHITE_BORDER,
            activeforeground=GRAPHITE_TEXT,
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        close_button.pack(anchor="e")

    def open_about_window(self):
        about = tk.Toplevel(self)
        about.title("About")
        about.geometry("520x360")
        about.minsize(480, 320)
        about.configure(bg=GRAPHITE_BG)
        about.transient(self)
        about.grab_set()
        container = ttk.Frame(about, padding=18)
        container.pack(fill="both", expand=True)
        title = ttk.Label(container, text=APP_TITLE, font=("Segoe UI", 20, "bold"))
        title.pack(anchor="w")
        version = ttk.Label(container, text=f"Version: {APP_VERSION}", foreground=GRAPHITE_MUTED)
        version.pack(anchor="w", pady=(6, 0))
        author = ttk.Label(container, text=f"Author: {APP_AUTHOR}", foreground=GRAPHITE_MUTED)
        author.pack(anchor="w", pady=(2, 14))
        info_text = (
            "DayZ PBO build helper for packing, binarizing, signing, validating, and preparing addon output folders."
            + chr(10) + chr(10)
            + f"Licence: {APP_LICENSE_NAME}" + chr(10)
            + "Copyright (c) 2026 RaiZo" + chr(10) + chr(10)
            + "Important:" + chr(10)
            + "- Never share your .biprivatekey." + chr(10)
            + "- Only distribute the matching .bikey." + chr(10)
            + "- Always check generated PBOs before release." + chr(10) + chr(10)
            + "This tool is provided as-is without warranty."
        )
        text = tk.Text(container, height=9, wrap="word", bg=GRAPHITE_FIELD, fg=GRAPHITE_TEXT, insertbackground=GRAPHITE_TEXT, selectbackground=GRAPHITE_ACCENT_DARK, selectforeground="#ffffff", relief="flat", borderwidth=0, highlightthickness=1, highlightbackground=GRAPHITE_BORDER, highlightcolor=GRAPHITE_ACCENT, font=("Segoe UI", 10))
        text.pack(fill="both", expand=True, pady=(0, 12))
        text.insert("1.0", info_text)
        text.configure(state="disabled")
        close_button = tk.Button(container, text="Close", command=about.destroy, bg=GRAPHITE_CARD_SOFT, fg=GRAPHITE_TEXT, activebackground=GRAPHITE_BORDER, activeforeground=GRAPHITE_TEXT, relief="flat", borderwidth=0, padx=14, pady=8, font=("Segoe UI", 10), cursor="hand2")
        close_button.pack(anchor="e")

    def open_options_window(self):
        options = tk.Toplevel(self)
        options.title("Options")
        options.geometry("900x540")
        options.minsize(760, 480)
        options.configure(bg=GRAPHITE_BG)
        options.transient(self)
        options.grab_set()
        container = ttk.Frame(options, padding=16)
        container.pack(fill="both", expand=True)
        title = ttk.Label(container, text="Options", font=("Segoe UI", 17, "bold"))
        title.pack(anchor="w", pady=(0, 12))
        options_frame = ttk.LabelFrame(container, text="Tool paths and build settings", padding=14)
        options_frame.pack(fill="both", expand=True)
        options_frame.columnconfigure(1, weight=1)
        self._add_file_row(options_frame, 0, "binarize.exe", self.binarize_exe_var, self.choose_binarize_exe, "Path to DayZ Tools binarize.exe.")
        self._add_file_row(options_frame, 1, "CfgConvert.exe", self.cfgconvert_exe_var, self.choose_cfgconvert_exe, "Path to DayZ Tools CfgConvert.exe.")
        self._add_file_row(options_frame, 2, "P3DObfuscator.exe", self.p3d_obfuscator_exe_var, self.choose_p3d_obfuscator_exe, "Path to P3DObfuscator.exe.")
        self._add_file_row(options_frame, 3, "DSSignFile.exe", self.dssignfile_exe_var, self.choose_dssignfile_exe, "Path to DayZ Tools DSSignFile.exe.")
        self._add_file_row(options_frame, 4, "Private key", self.private_key_var, self.choose_private_key, "Your .biprivatekey. Never distribute this file.")
        self._add_folder_row(options_frame, 5, "Project root", self.project_root_var, self.choose_project_root, "Usually P: or your DayZ project drive root.")
        self._add_folder_row(options_frame, 6, "Temp dir", self.temp_dir_var, self.choose_temp_dir, "Temporary staging folder. Clear build temp only removes known builder temp folders inside this path.")
        ttk.Label(options_frame, text="Exclude patterns").grid(row=7, column=0, sticky="nw", pady=5)
        exclude_entry = tk.Text(options_frame, height=5, bg=GRAPHITE_FIELD, fg=GRAPHITE_TEXT, insertbackground=GRAPHITE_TEXT, selectbackground=GRAPHITE_ACCENT_DARK, selectforeground="#ffffff", relief="flat", borderwidth=0, highlightthickness=1, highlightbackground=GRAPHITE_BORDER, highlightcolor=GRAPHITE_ACCENT, font=("Segoe UI", 10))
        exclude_entry.grid(row=7, column=1, columnspan=2, sticky="nsew", pady=5, padx=(8, 0))
        exclude_entry.insert("1.0", self.exclude_patterns_var.get())
        add_tooltip(exclude_entry, "Comma, semicolon, or newline separated exclude patterns. Used internally by the builder.")
        options_frame.rowconfigure(7, weight=1)
        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(12, 0))

        def save_and_close():
            self.exclude_patterns_var.set(exclude_entry.get("1.0", "end").strip())
            self.save_path_settings()
            options.destroy()

        save_button = tk.Button(buttons, text="Save", command=save_and_close, bg=GRAPHITE_ACCENT_DARK, fg="#ffffff", activebackground=GRAPHITE_ACCENT, activeforeground="#ffffff", relief="flat", borderwidth=0, padx=14, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2")
        save_button.pack(side="right")
        cancel_button = tk.Button(buttons, text="Cancel", command=options.destroy, bg=GRAPHITE_CARD_SOFT, fg=GRAPHITE_TEXT, activebackground=GRAPHITE_BORDER, activeforeground=GRAPHITE_TEXT, relief="flat", borderwidth=0, padx=14, pady=8, font=("Segoe UI", 10), cursor="hand2")
        cancel_button.pack(side="right", padx=(0, 8))

    def get_selected_addon_names(self):
        selected = []
        for index in self.addon_listbox.curselection():
            selected.append(self.addon_listbox.get(index))
        return selected

    def refresh_addon_list(self, select_saved=False):
        source_root = self.source_root_var.get().strip()
        output_root = self.output_root_var.get().strip()
        output_addons_dir = os.path.join(output_root, "Addons") if output_root else ""
        previous_selection = set(self.get_selected_addon_names())
        saved_selection = set(self.saved_settings.get("selected_addons", [])) if select_saved else set()
        self.addon_listbox.delete(0, "end")
        self.current_addon_targets = []
        if not source_root or not os.path.isdir(source_root):
            return
        self.current_addon_targets = detect_addon_targets(source_root, output_addons_dir)
        for name, path in self.current_addon_targets:
            self.addon_listbox.insert("end", name)
        names = [name for name, path in self.current_addon_targets]
        if saved_selection:
            selection = saved_selection
        elif previous_selection:
            selection = previous_selection
        else:
            selection = set(names)
        for index, name in enumerate(names):
            if name in selection:
                self.addon_listbox.selection_set(index)
        self.save_path_settings()

    def select_all_addons(self):
        self.addon_listbox.selection_set(0, "end")
        self.save_path_settings()

    def select_no_addons(self):
        self.addon_listbox.selection_clear(0, "end")
        self.save_path_settings()

    def save_path_settings(self):
        try:
            max_processes = int(self.max_processes_var.get())
        except Exception:
            max_processes = get_default_max_processes()
        data = {
            "source_root": self.source_root_var.get().strip(),
            "output_root": self.output_root_var.get().strip(),
            "pbo_name": self.pbo_name_var.get().strip(),
            "use_binarize": bool(self.use_binarize_var.get()),
            "protect_p3d": bool(self.protect_p3d_var.get()),
            "convert_config": bool(self.convert_config_var.get()),
            "sign_pbos": bool(self.sign_pbos_var.get()),
            "force_rebuild": bool(self.force_rebuild_var.get()),
            "preflight_before_build": bool(self.preflight_before_build_var.get()),
            "max_processes": max_processes,
            "binarize_exe": self.binarize_exe_var.get().strip(),
            "p3d_obfuscator_exe": self.p3d_obfuscator_exe_var.get().strip(),
            "cfgconvert_exe": self.cfgconvert_exe_var.get().strip(),
            "dssignfile_exe": self.dssignfile_exe_var.get().strip(),
            "private_key": self.private_key_var.get().strip(),
            "project_root": self.project_root_var.get().strip(),
            "temp_dir": self.temp_dir_var.get().strip(),
            "exclude_patterns": self.exclude_patterns_var.get().strip(),
            "selected_addons": self.get_selected_addon_names() if hasattr(self, "addon_listbox") else [],
            "window_geometry": self.geometry() if is_safe_window_geometry(self.geometry()) else self.saved_settings.get("window_geometry", ""),
        }
        save_saved_settings(data)

    def choose_source_root(self):
        path = filedialog.askdirectory(title="Select source root", initialdir=get_initial_dir_from_value(self.source_root_var.get(), self.output_root_var.get()))
        if path:
            self.source_root_var.set(path)
            self.refresh_addon_list()
            self.save_path_settings()

    def choose_output_root(self):
        path = filedialog.askdirectory(title="Select output root folder", initialdir=get_initial_dir_from_value(self.output_root_var.get(), self.source_root_var.get()))
        if path:
            self.output_root_var.set(path)
            self.refresh_addon_list()
            self.save_path_settings()

    def choose_project_root(self):
        path = filedialog.askdirectory(title="Select project root, usually P:", initialdir=get_initial_dir_from_value(self.project_root_var.get(), self.source_root_var.get()))
        if path:
            if len(path) == 3 and path[1] == ":" and path.endswith(WIN_SEP):
                path = path[:2]
            self.project_root_var.set(path)
            self.save_path_settings()

    def choose_temp_dir(self):
        path = filedialog.askdirectory(title="Select temporary build directory", initialdir=get_initial_dir_from_value(self.temp_dir_var.get(), self.source_root_var.get()))
        if path:
            self.temp_dir_var.set(path)
            self.save_path_settings()

    def choose_binarize_exe(self):
        path = filedialog.askopenfilename(title="Select binarize.exe", initialdir=get_initial_dir_from_value(self.binarize_exe_var.get(), self.project_root_var.get()), filetypes=[("binarize.exe", "binarize.exe"), ("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.binarize_exe_var.set(path)
            self.save_path_settings()

    def choose_cfgconvert_exe(self):
        path = filedialog.askopenfilename(title="Select CfgConvert.exe", initialdir=get_initial_dir_from_value(self.cfgconvert_exe_var.get(), self.project_root_var.get()), filetypes=[("CfgConvert.exe", "CfgConvert.exe"), ("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.cfgconvert_exe_var.set(path)
            self.save_path_settings()

    def choose_p3d_obfuscator_exe(self):
        path = filedialog.askopenfilename(title="Select P3DObfuscator.exe", initialdir=get_initial_dir_from_value(self.p3d_obfuscator_exe_var.get(), self.project_root_var.get()), filetypes=[("P3DObfuscator", "*.exe"), ("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.p3d_obfuscator_exe_var.set(path)
            self.save_path_settings()

    def choose_dssignfile_exe(self):
        path = filedialog.askopenfilename(title="Select DSSignFile.exe", initialdir=get_initial_dir_from_value(self.dssignfile_exe_var.get(), self.project_root_var.get()), filetypes=[("DSSignFile.exe", "DSSignFile.exe"), ("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.dssignfile_exe_var.set(path)
            self.save_path_settings()

    def choose_private_key(self):
        path = filedialog.askopenfilename(title="Select private key", initialdir=get_initial_dir_from_value(self.private_key_var.get(), self.output_root_var.get()), filetypes=[("BI private key", "*.biprivatekey"), ("All files", "*.*")])
        if path:
            self.private_key_var.set(path)
            self.save_path_settings()

    def validate_preflight_settings(self):
        self.refresh_addon_list()
        source_root = self.source_root_var.get().strip()
        if not source_root:
            raise BuildError("Select a source root folder.")
        if not os.path.isdir(source_root):
            raise BuildError(f"Source root does not exist: {source_root}")
        selected_addons = self.get_selected_addon_names()
        if not selected_addons:
            raise BuildError("Select at least one addon to check.")
        selected_set = set(selected_addons)
        targets = [(name, path) for name, path in self.current_addon_targets if name in selected_set]
        if not targets:
            raise BuildError("No selected addon targets found.")
        settings = {
            "cfgconvert_exe": self.cfgconvert_exe_var.get().strip(),
            "project_root": self.project_root_var.get().strip() or DEFAULT_PROJECT_ROOT,
            "temp_dir": self.temp_dir_var.get().strip() or DEFAULT_TEMP_DIR,
            "exclude_patterns": self.exclude_patterns_var.get().strip(),
        }
        self.save_path_settings()
        return settings, targets

    def start_preflight(self):
        if self.is_building:
            return
        try:
            settings, targets = self.validate_preflight_settings()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.current_log_path = str(create_build_log_path())
        settings["log_file"] = self.current_log_path
        if self.current_log_path:
            Path(self.current_log_path).parent.mkdir(parents=True, exist_ok=True)
            self.current_log_file = open(self.current_log_path, "w", encoding="utf-8")
        self.is_building = True
        self.build_button.configure(state="disabled")
        self.preflight_button.configure(state="disabled")
        self.progress.configure(value=0, maximum=100)
        self.set_status("Preflight running...", "preflight")
        self.log("Starting preflight check...")
        if self.current_log_path:
            self.log(f"Log file: {self.current_log_path}")
        self.worker_thread = threading.Thread(target=self._preflight_worker, args=(settings, targets), daemon=True)
        self.worker_thread.start()

    def _preflight_worker(self, settings, targets):
        try:
            result = run_preflight_for_targets(settings, targets, self.thread_log, self.thread_progress)
            self.log_queue.put(("preflight_done", (result.errors, result.warnings)))
        except Exception as e:
            self.log_queue.put(("error", str(e)))

    def validate_settings(self):
        self.refresh_addon_list()
        source_root = self.source_root_var.get().strip()
        output_root = self.output_root_var.get().strip()
        if not source_root:
            raise BuildError("Select a source root folder.")
        if not os.path.isdir(source_root):
            raise BuildError(f"Source root does not exist: {source_root}")
        if not output_root:
            raise BuildError("Select an output root folder.")
        selected_addons = self.get_selected_addon_names()
        if not selected_addons:
            raise BuildError("Select at least one addon to build.")
        if self.pbo_name_var.get().strip() and len(selected_addons) > 1:
            raise BuildError("PBO name override can only be used when exactly one addon is selected.")
        if self.use_binarize_var.get():
            binarize_exe = self.binarize_exe_var.get().strip()
            if not binarize_exe:
                raise BuildError("Select binarize.exe or disable P3D binarize.")
            if not os.path.isfile(binarize_exe):
                raise BuildError(f"binarize.exe does not exist: {binarize_exe}")
        if self.protect_p3d_var.get():
            if not self.use_binarize_var.get():
                raise BuildError("Protect P3D requires enabled P3D binarize.")
            p3d_obfuscator_exe = self.p3d_obfuscator_exe_var.get().strip()
            if not p3d_obfuscator_exe:
                raise BuildError("Select P3DObfuscator.exe or disable Protect P3D.")
            if not os.path.isfile(p3d_obfuscator_exe):
                raise BuildError(f"P3DObfuscator.exe does not exist: {p3d_obfuscator_exe}")
        if self.convert_config_var.get():
            cfgconvert_exe = self.cfgconvert_exe_var.get().strip()
            if not cfgconvert_exe:
                raise BuildError("Select CfgConvert.exe or disable CPP to BIN.")
            if not os.path.isfile(cfgconvert_exe):
                raise BuildError(f"CfgConvert.exe does not exist: {cfgconvert_exe}")
        if self.sign_pbos_var.get():
            dssignfile_exe = self.dssignfile_exe_var.get().strip()
            private_key = self.private_key_var.get().strip()
            if not dssignfile_exe:
                raise BuildError("Select DSSignFile.exe or disable Sign PBOs.")
            if not os.path.isfile(dssignfile_exe):
                raise BuildError(f"DSSignFile.exe does not exist: {dssignfile_exe}")
            if not private_key:
                raise BuildError("Select a .biprivatekey file or disable Sign PBOs.")
            if not os.path.isfile(private_key):
                raise BuildError(f"Private key does not exist: {private_key}")
        try:
            max_processes = int(self.max_processes_var.get())
        except Exception:
            max_processes = get_default_max_processes()
        if max_processes < 1:
            max_processes = 1
        log_path = str(create_build_log_path())
        settings = {
            "source_root": source_root,
            "output_root_dir": output_root,
            "pbo_name": self.pbo_name_var.get().strip(),
            "use_binarize": bool(self.use_binarize_var.get()),
            "protect_p3d": bool(self.protect_p3d_var.get()),
            "convert_config": bool(self.convert_config_var.get()),
            "sign_pbos": bool(self.sign_pbos_var.get()),
            "force_rebuild": bool(self.force_rebuild_var.get()),
            "preflight_before_build": bool(self.preflight_before_build_var.get()),
            "binarize_exe": self.binarize_exe_var.get().strip(),
            "p3d_obfuscator_exe": self.p3d_obfuscator_exe_var.get().strip(),
            "cfgconvert_exe": self.cfgconvert_exe_var.get().strip(),
            "dssignfile_exe": self.dssignfile_exe_var.get().strip(),
            "private_key": self.private_key_var.get().strip(),
            "project_root": self.project_root_var.get().strip() or DEFAULT_PROJECT_ROOT,
            "temp_dir": self.temp_dir_var.get().strip() or DEFAULT_TEMP_DIR,
            "exclude_patterns": self.exclude_patterns_var.get().strip(),
            "max_processes": max_processes,
            "selected_addons": selected_addons,
            "log_file": log_path,
        }
        self.save_path_settings()
        return settings

    def start_build(self):
        if self.is_building:
            return
        try:
            settings = self.validate_settings()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.current_log_path = settings.get("log_file", "")
        if self.current_log_path:
            Path(self.current_log_path).parent.mkdir(parents=True, exist_ok=True)
            self.current_log_file = open(self.current_log_path, "w", encoding="utf-8")
        self.is_building = True
        self.build_button.configure(state="disabled")
        self.preflight_button.configure(state="disabled")
        self.progress.configure(value=0, maximum=100)
        self.set_status("Build running...", "building")
        self.log("Starting build...")
        if self.current_log_path:
            self.log(f"Log file: {self.current_log_path}")
        self.worker_thread = threading.Thread(target=self._build_worker, args=(settings,), daemon=True)
        self.worker_thread.start()

    def _build_worker(self, settings):
        try:
            build_all(settings, self.thread_log, self.thread_progress)
            self.log_queue.put(("done", None))
        except Exception as e:
            self.log_queue.put(("error", str(e)))

    def thread_log(self, message):
        self.log_queue.put(("log", message))

    def thread_progress(self, current, total):
        self.log_queue.put(("progress", (current, total)))

    def configure_log_tags(self):
        self.log_text.tag_configure("log_error", foreground=GRAPHITE_ERROR)
        self.log_text.tag_configure("log_warning", foreground=GRAPHITE_WARNING)
        self.log_text.tag_configure("log_success", foreground=GRAPHITE_SUCCESS)
        self.log_text.tag_configure("log_section", foreground=GRAPHITE_MUTED)
        self.log_text.tag_configure("log_tool", foreground=GRAPHITE_PREFLIGHT_ACTIVE)

    def get_log_tag(self, line):
        stripped = line.strip()
        upper = stripped.upper()

        if not stripped:
            return ""

        if upper.startswith("ERROR") or " ERROR:" in upper:
            return "log_error"

        if upper.startswith("WARNING") or " WARNING:" in upper:
            return "log_warning"

        if (
            "BUILD FINISHED" in upper
            or "COMPLETED SUCCESSFULLY" in upper
            or upper.endswith(" OK")
            or upper.endswith(": OK")
            or "SYNTAX CHECK: OK" in upper
        ):
            return "log_success"

        if stripped.startswith("=" * 8):
            return "log_section"

        if (
            "Binarize" in stripped
            or "CfgConvert" in stripped
            or "DSSignFile" in stripped
            or "Preflight" in stripped
        ):
            return "log_tool"

        return ""

    def _poll_log_queue(self):
        log_batch = []

        def flush_log_batch():
            if log_batch:
                self.log_many(log_batch)
                log_batch.clear()

        try:
            while True:
                item_type, payload = self.log_queue.get_nowait()

                if item_type == "log":
                    log_batch.append(payload)
                    continue

                flush_log_batch()

                if item_type == "progress":
                    current, total = payload
                    maximum = max(total, 1)
                    self.progress.configure(maximum=maximum, value=current)
                    self.set_status(f"Working... {current}/{maximum}", "building")
                elif item_type == "done":
                    self.is_building = False
                    self.build_button.configure(state="normal")
                    self.preflight_button.configure(state="normal")
                    self.progress.configure(value=self.progress.cget("maximum"))
                    self.set_status("Build finished", "success")
                    self.close_current_log_file()
                    messagebox.showinfo(APP_TITLE, "Build finished.")
                elif item_type == "preflight_done":
                    self.is_building = False
                    self.build_button.configure(state="normal")
                    self.preflight_button.configure(state="normal")
                    self.progress.configure(value=self.progress.cget("maximum"))
                    self.set_status("Preflight finished", "success")
                    self.close_current_log_file()
                    errors, warnings = payload
                    if errors:
                        messagebox.showerror(APP_TITLE, f"Preflight finished with {errors} error(s) and {warnings} warning(s).")
                    elif warnings:
                        messagebox.showwarning(APP_TITLE, f"Preflight finished with {warnings} warning(s).")
                    else:
                        messagebox.showinfo(APP_TITLE, "Preflight finished without errors or warnings.")
                elif item_type == "error":
                    self.is_building = False
                    self.build_button.configure(state="normal")
                    self.preflight_button.configure(state="normal")
                    self.log("")
                    self.log(f"ERROR: {payload}")
                    self.set_status("Error", "error")
                    self.close_current_log_file()
                    messagebox.showerror(APP_TITLE, payload)
        except queue.Empty:
            flush_log_batch()

        self.after(100, self._poll_log_queue)

    def log(self, message):
        self.log_many([message])

    def log_many(self, messages):
        lines = [str(message) for message in messages]

        if not lines:
            return

        for line in lines:
            tag = self.get_log_tag(line)
            if tag:
                self.log_text.insert("end", line + chr(10), tag)
            else:
                self.log_text.insert("end", line + chr(10))

        self.log_text.see("end")

        try:
            for line in lines:
                print(line, flush=True)
        except Exception:
            pass

        if self.current_log_file:
            try:
                self.current_log_file.write(chr(10).join(lines) + chr(10))
                self.current_log_file.flush()
            except Exception:
                pass

        self.update_idletasks()

    def on_window_configure(self, event=None):
        if event is not None and event.widget is not self:
            return

        if self.state() == "zoomed":
            return

        if self.geometry_save_after_id:
            try:
                self.after_cancel(self.geometry_save_after_id)
            except Exception:
                pass

        self.geometry_save_after_id = self.after(700, self.save_window_geometry)

    def save_window_geometry(self):
        self.geometry_save_after_id = None

        geometry = self.geometry()

        if not is_safe_window_geometry(geometry):
            return

        self.saved_settings["window_geometry"] = geometry
        save_saved_settings(self.saved_settings)

    def on_close(self):
        try:
            self.save_window_geometry()
            self.save_path_settings()
        except Exception:
            pass

        self.close_current_log_file()
        self.destroy()

    def close_current_log_file(self):
        if self.current_log_file:
            try:
                self.current_log_file.close()
            except Exception:
                pass
            self.current_log_file = None

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def clear_temp_from_ui(self):
        if self.is_building:
            messagebox.showwarning(APP_TITLE, "Cannot clear temp folder while a build is running.")
            return
        temp_dir = self.temp_dir_var.get().strip() or DEFAULT_TEMP_DIR
        if not temp_dir:
            messagebox.showerror(APP_TITLE, "Temp dir is empty.")
            return
        source_root = self.source_root_var.get().strip()
        output_root = self.output_root_var.get().strip()

        confirm_message = (
            "Safely clear PBO Builder(byRaiZo) temp data?" + chr(10) + chr(10)
            + "Temp root:" + chr(10)
            + temp_dir + chr(10) + chr(10)
            + "Only known builder temp folders will be removed:" + chr(10)
            + "addons, preflight, staging, binarized, configs, _binarize_textures" + chr(10) + chr(10)
            + "Unrelated files and folders in the temp root will be left untouched."
        )
        confirm = messagebox.askyesno(APP_TITLE, confirm_message)
        if not confirm:
            return
        try:
            clear_temp_folder(temp_dir, self.log, source_root, output_root)
            messagebox.showinfo(APP_TITLE, "Builder temp data cleared.")
        except Exception as e:
            self.log("")
            self.log(f"ERROR: {e}")
            messagebox.showerror(APP_TITLE, str(e))

    def clear_full_temp_from_ui(self):
        if self.is_building:
            messagebox.showwarning(APP_TITLE, "Cannot clear all temp while a build is running.")
            return

        temp_dir = self.temp_dir_var.get().strip() or DEFAULT_TEMP_DIR

        if not temp_dir:
            messagebox.showerror(APP_TITLE, "Temp dir is empty.")
            return

        source_root = self.source_root_var.get().strip()
        output_root = self.output_root_var.get().strip()

        confirm_message = (
            "Clear ALL selected temp folder contents?" + chr(10) + chr(10)
            + "Temp root:" + chr(10)
            + temp_dir + chr(10) + chr(10)
            + "This removes every file and folder inside the temp root, except the builder marker file." + chr(10)
            + "Only use this if the temp root is dedicated to PBO Builder(byRaiZo)." + chr(10) + chr(10)
            + "The same safety checks are used to reject dangerous paths."
        )

        confirm = messagebox.askyesno(APP_TITLE, confirm_message)

        if not confirm:
            return

        try:
            clear_full_temp_folder(temp_dir, self.log, source_root, output_root)
            messagebox.showinfo(APP_TITLE, "All temp folder contents cleared.")
        except Exception as e:
            self.log("")
            self.log(f"ERROR: {e}")
            messagebox.showerror(APP_TITLE, str(e))

    def open_folder_in_explorer(self, folder_path, empty_message, missing_message):
        folder_path = folder_path.strip() if folder_path else ""

        if not folder_path:
            messagebox.showerror(APP_TITLE, empty_message)
            return

        if not os.path.isdir(folder_path):
            messagebox.showerror(APP_TITLE, missing_message.format(folder_path=folder_path))
            return

        try:
            if os.name == "nt":
                os.startfile(folder_path)
            else:
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))

    def open_source_root_folder(self):
        source_root = self.source_root_var.get().strip()
        self.open_folder_in_explorer(
            source_root,
            "Source root folder is empty.",
            "Source root folder does not exist: {folder_path}",
        )

    def open_output_folder(self):
        output_root = self.output_root_var.get().strip()
        self.open_folder_in_explorer(
            output_root,
            "Output root folder is empty.",
            "Output root folder does not exist: {folder_path}",
        )

    def open_logs_folder(self):
        logs_dir = get_logs_dir()
        try:
            if os.name == "nt":
                os.startfile(str(logs_dir))
            else:
                subprocess.Popen(["xdg-open", str(logs_dir)])
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))

    def open_latest_log(self):
        logs_dir = get_logs_dir()
        log_files = list(logs_dir.glob("build_*.log"))
        if not log_files:
            messagebox.showinfo(APP_TITLE, "No build logs found yet.")
            return
        latest_log = max(log_files, key=lambda path: path.stat().st_mtime)
        try:
            if os.name == "nt":
                os.startfile(str(latest_log))
            else:
                subprocess.Popen(["xdg-open", str(latest_log)])
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))

    def clear_build_cache_from_ui(self):
        if self.is_building:
            messagebox.showwarning(APP_TITLE, "Cannot clear build cache while a build is running.")
            return
        source_root = self.source_root_var.get().strip()
        selected_addons = self.get_selected_addon_names()
        if not source_root:
            messagebox.showerror(APP_TITLE, "Source root is empty.")
            return
        if not os.path.isdir(source_root):
            messagebox.showerror(APP_TITLE, f"Source root does not exist: {source_root}")
            return
        if not selected_addons:
            messagebox.showerror(APP_TITLE, "Select at least one addon whose cache should be cleared.")
            return
        cache = load_build_cache()
        cache_key_root = os.path.abspath(source_root).lower()
        source_cache = cache.get(cache_key_root, {})
        if not source_cache:
            self.log(f"No build cache found for source root: {source_root}")
            messagebox.showinfo(APP_TITLE, "No build cache found for the selected source root.")
            return
        selected_text = chr(10).join([f"- {name}" for name in selected_addons])
        confirm_message = "Clear build cache for the selected addon(s)?" + chr(10) + chr(10) + "Source root: " + source_root + chr(10) + chr(10) + selected_text
        confirm = messagebox.askyesno(APP_TITLE, confirm_message)
        if not confirm:
            return
        cleared = 0
        for addon_name in selected_addons:
            if addon_name in source_cache:
                del source_cache[addon_name]
                cleared += 1
                self.log(f"Cleared build cache for addon: {addon_name}")
            else:
                self.log(f"No cache entry for addon: {addon_name}")
        if source_cache:
            cache[cache_key_root] = source_cache
        elif cache_key_root in cache:
            del cache[cache_key_root]
        save_build_cache(cache)
        messagebox.showinfo(APP_TITLE, f"Cleared {cleared} cache entrie(s).")

