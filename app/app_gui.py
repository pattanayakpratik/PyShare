"""
==========================================================================
PyShare v4.9.0 - Cyberpunk Neon Liquid Glass Native Desktop GUI
Exact 3-Pillar Studio Layout Matching Web UI (host_dark.png & client_dark.png)
Zero Browser • Dual Host & Client Mode • Quick Share Drag & Drop Staging
==========================================================================
"""

import os
import io
import sys
import time
import socket
import threading
import tempfile
import shutil
import subprocess
import requests

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image

try:
    import windnd
    DND_SUPPORTED = True
except ImportError:
    DND_SUPPORTED = False

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import main

# =========================================================================
# CYBERPUNK NEON LIQUID GLASS DESIGN SYSTEM (Exact match to styles.css)
# =========================================================================
THEME = {
    "dark": {
        "bg_root": "#060913",              # Deep cosmic obsidian
        "card_bg": "#0d1424",              # Translucent liquid glass
        "card_border": "#1a263c",          # Subtle glass border
        "card_border_glow": "#00f0ff",     # Cyan glowing border for dropzones
        "card_hover": "#121c32",           # Hover state
        "input_bg": "#070c17",             # Deep sunken input
        "input_border": "#1e2c44",         # Input border
        "text_main": "#f8fafc",            # Crisp white
        "text_sub": "#94a3b8",             # Muted slate
        "text_cyan": "#00f0ff",            # Neon cyan
        "accent_cyan": "#00f0ff",          # Neon cyan
        "accent_blue": "#3b82f6",          # Electric blue
        "accent_violet": "#a855f7",        # Purple
        "accent_green": "#10b981",         # Emerald
        "accent_red": "#ef4444",           # Rose red
        "btn_pill_bg": "#151f33",          # Dark glass pill button
        "btn_pill_border": "#22324f",      # Button border
        "btn_pill_hover": "#1e2e4a",       # Button hover
        "row_bg": "#0b1220",               # List row background
        "row_border": "#162238",           # List row border
        "row_hover": "#131d31",            # List row hover
        "qr_bg": "#ffffff",                # Crisp white for QR code
        "segmented_bg": "#0a0f1d",
        "segmented_selected": "#0284c7"
    },
    "light": {
        "bg_root": "#f1f5f9",
        "card_bg": "#ffffff",
        "card_border": "#e2e8f0",
        "card_border_glow": "#0284c7",
        "card_hover": "#f8fafc",
        "input_bg": "#f8fafc",
        "input_border": "#cbd5e1",
        "text_main": "#0f172a",
        "text_sub": "#64748b",
        "text_cyan": "#0284c7",
        "accent_cyan": "#0284c7",
        "accent_blue": "#2563eb",
        "accent_violet": "#7c3aed",
        "accent_green": "#059669",
        "accent_red": "#dc2626",
        "btn_pill_bg": "#e2e8f0",
        "btn_pill_border": "#cbd5e1",
        "btn_pill_hover": "#cbd5e1",
        "row_bg": "#f8fafc",
        "row_border": "#e2e8f0",
        "row_hover": "#f1f5f9",
        "qr_bg": "#ffffff",
        "segmented_bg": "#e2e8f0",
        "segmented_selected": "#0284c7"
    }
}

# --- HELPER UTILITIES ---
def format_size(bytes_size):
    if not bytes_size or bytes_size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(bytes_size)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.1f} {units[i]}"

def get_file_icon(filename):
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif']:
        return '🖼️'
    if ext in ['mp4', 'mkv', 'mov', 'webm', 'avi', 'wmv', 'm4v']:
        return '🎬'
    if ext in ['mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a', 'wma']:
        return '🎵'
    if ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'csv']:
        return '📄'
    if ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz']:
        return '📦'
    if ext in ['html', 'css', 'js', 'json', 'py', 'ts', 'jsx', 'tsx', 'cpp', 'c', 'java', 'go', 'rs']:
        return '💻'
    return '📁'

def truncate_path(path, max_len=32):
    if not path:
        return ""
    if len(path) <= max_len:
        return path
    parts = path.split(os.sep)
    if len(parts) > 2:
        return f"{parts[0]}{os.sep}...{os.sep}{parts[-1]}"
    return "..." + path[-(max_len - 3):]

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    cand = os.path.join(base_path, relative_path)
    if os.path.exists(cand):
        return cand
    
    web_cand = os.path.abspath(os.path.join(base_path, "..", "web", relative_path))
    if os.path.exists(web_cand):
        return web_cand
        
    parent_cand = os.path.abspath(os.path.join(base_path, "..", relative_path))
    if os.path.exists(parent_cand):
        return parent_cand

    return cand


class PyShareApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Load Persistent User Configuration
        self.app_config = main.load_app_config()
        self.defaults = main.get_default_directories()
        self.client_download_dir = self.app_config.get("client_download_dir", self.defaults["client_download_dir"])
        os.makedirs(self.client_download_dir, exist_ok=True)

        # Active Theme (default Dark)
        self.active_mode = self.app_config.get("theme", "dark")
        ctk.set_appearance_mode(self.active_mode)
        ctk.set_default_color_theme("blue")
        self.colors = THEME[self.active_mode]

        self.title("PyShare — Local & P2P Quick Share")
        self.geometry("1240x780")
        self.minsize(1050, 680)
        self.configure(fg_color=self.colors["bg_root"])

        # Set Window Icon
        icon_path = resource_path("app_icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # State Variables
        self.current_mode = "host"  # "host" or "client"
        self.active_hub_tab = "log" # "log" or "clipboard"
        self.client_session = requests.Session()
        self.client_connected = False
        self.client_host_url = ""
        self.client_files = []
        self.client_selected_upload_files = []
        self.is_client_uploading = False
        self.is_client_downloading = False

        # Host State Cache
        self.cached_qr_path = os.path.join(main.BASE_DIR, "qrcode.png") if getattr(main, 'BASE_DIR', '') else resource_path("qrcode.png")
        self.qr_ctk_image = None
        self.last_qr_timestamp = 0
        self.search_shared_query = ""
        self.search_received_query = ""
        self.search_client_query = ""

        # Build Full Liquid Glass Layout
        self.build_top_navbar()
        self.build_status_bar()
        self.build_content_container()

        # Initialize Host Server in Background
        self.start_host_server()

        # Register Native Drag & Drop if available
        if DND_SUPPORTED:
            try:
                windnd.hook_dropfiles(self, func=self.on_drop_files, force_unicode=True)
            except Exception as e:
                print(f"[*] Drag-and-drop hook notice: {e}")

        # Start Periodic GUI Refresh Ticker
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(500, self.refresh_ticker)

    # =========================================================================
    # 1. TOP NAVBAR (Liquid Glass Style with Centered Brand & Action Icons)
    # =========================================================================
    def build_top_navbar(self):
        self.navbar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=self.colors["bg_root"])
        self.navbar.pack(side="top", fill="x", padx=16, pady=(10, 0))

        # Left: Theme Toggle Circular Icon Button
        left_actions = ctk.CTkFrame(self.navbar, fg_color="transparent")
        left_actions.pack(side="left")

        self.theme_btn = ctk.CTkButton(
            left_actions,
            text="🌓",
            width=36,
            height=36,
            corner_radius=18,
            font=ctk.CTkFont(size=14),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left")

        # Center Brand Logo with Neon Cyan Gradient Feel
        brand_frame = ctk.CTkFrame(self.navbar, fg_color="transparent")
        brand_frame.pack(side="left", expand=True)

        logo_img_path = resource_path("app_icon.png")
        if os.path.isfile(logo_img_path):
            try:
                pil_logo = Image.open(logo_img_path).resize((28, 28))
                ctk_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(28, 28))
                logo_lbl = ctk.CTkLabel(brand_frame, image=ctk_logo, text="")
                logo_lbl.pack(side="left", padx=(0, 8))
            except Exception:
                pass

        brand_lbl = ctk.CTkLabel(
            brand_frame,
            text="PyShare",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=self.colors["accent_cyan"]
        )
        brand_lbl.pack(side="left")

        # Mode Switcher (Host vs Client)
        self.mode_switcher = ctk.CTkSegmentedButton(
            brand_frame,
            values=["📡 Host Mode", "📱 Client Mode"],
            command=self.on_mode_change,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            selected_color=self.colors["segmented_selected"],
            selected_hover_color=self.colors["accent_blue"],
            height=32
        )
        self.mode_switcher.set("📡 Host Mode")
        self.mode_switcher.pack(side="left", padx=16)

        # Right Action Buttons
        right_actions = ctk.CTkFrame(self.navbar, fg_color="transparent")
        right_actions.pack(side="right")

    # =========================================================================
    # 2. STATUS BAR (Centered Status Pill with Glowing Dot & IP)
    # =========================================================================
    def build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self.status_bar.pack(fill="x", padx=16, pady=(4, 8))

        self.status_pill = ctk.CTkFrame(
            self.status_bar,
            corner_radius=20,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"],
            height=28
        )
        self.status_pill.pack(side="top")

        pill_inner = ctk.CTkFrame(self.status_pill, fg_color="transparent")
        pill_inner.pack(padx=14, pady=4)

        self.status_dot = ctk.CTkLabel(
            pill_inner,
            text="●",
            text_color=self.colors["accent_green"],
            font=ctk.CTkFont(size=13)
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_text_lbl = ctk.CTkLabel(
            pill_inner,
            text=f"Server IP: {main.get_ip()}:{main.ACTUAL_PORT}",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=self.colors["text_main"]
        )
        self.status_text_lbl.pack(side="left")

    # =========================================================================
    # 3. CONTENT CONTAINER (Switches Between Host & Client Frames)
    # =========================================================================
    def build_content_container(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Host View Frame (3-Pillar Studio Layout)
        self.host_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.build_host_3_pillar_view()

        # Client View Frame (Clean Mobile/Desktop Client Layout)
        self.client_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.build_client_view()

        # Default Show Host
        self.host_frame.pack(fill="both", expand=True)

    def on_mode_change(self, selected_mode):
        if "Host" in selected_mode:
            self.current_mode = "host"
            self.client_frame.pack_forget()
            self.host_frame.pack(fill="both", expand=True)
            self.status_dot.configure(text_color=self.colors["accent_green"])
            self.status_text_lbl.configure(text=f"Server IP: {main.get_ip()}:{main.ACTUAL_PORT}")
            self.refresh_host_ui()
        else:
            self.current_mode = "client"
            self.host_frame.pack_forget()
            self.client_frame.pack(fill="both", expand=True)
            if self.client_connected:
                self.status_dot.configure(text_color=self.colors["accent_green"])
                self.status_text_lbl.configure(text=f"Connected to Host ({self.client_host_url.replace('http://', '')})")
            else:
                self.status_dot.configure(text_color=self.colors["text_sub"])
                self.status_text_lbl.configure(text="Disconnected from Host")
            self.refresh_client_ui()

    def toggle_theme(self):
        new_mode = "light" if self.active_mode == "dark" else "dark"
        self.active_mode = new_mode
        self.colors = THEME[new_mode]
        ctk.set_appearance_mode(new_mode)
        self.app_config["theme"] = new_mode
        main.save_app_config(self.app_config)

    # =========================================================================
    # 4. HOST MODE: EXACT 3-PILLAR STUDIO LAYOUT (Matching host_dark.png)
    # =========================================================================
    def build_host_3_pillar_view(self):
        # Pillar 1: "Add to Shared" Dropzone Card (Left, fixed width)
        self.col_send = ctk.CTkFrame(
            self.host_frame,
            width=280,
            corner_radius=22,
            fg_color=self.colors["card_bg"],
            border_width=2,
            border_color=self.colors["card_border_glow"]
        )
        self.col_send.pack(side="left", fill="y", padx=(0, 12))
        self.col_send.pack_propagate(False)
        self.build_pillar_1_dropzone()

        # Pillar 2: "Connect Device & Live Hub" (Center, fixed width)
        self.col_connect = ctk.CTkFrame(
            self.host_frame,
            width=350,
            corner_radius=22,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        self.col_connect.pack(side="left", fill="y", padx=(0, 12))
        self.col_connect.pack_propagate(False)
        self.build_pillar_2_connect_hub()

        # Pillar 3: Dual File Managers (Right, expands to fill remaining width)
        self.col_files = ctk.CTkFrame(self.host_frame, fg_color="transparent")
        self.col_files.pack(side="right", fill="both", expand=True)
        self.build_pillar_3_file_managers()

    # --- PILLAR 1: ADD TO SHARED DROPZONE ---
    def build_pillar_1_dropzone(self):
        drop_inner = ctk.CTkFrame(self.col_send, fg_color="transparent")
        drop_inner.pack(fill="both", expand=True, padx=14, pady=16)

        # Glowing Tray Upload Icon
        icon_frame = ctk.CTkFrame(drop_inner, width=72, height=72, corner_radius=18, fg_color=self.colors["btn_pill_bg"])
        icon_frame.pack(pady=(12, 10))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="📤", font=ctk.CTkFont(size=34)).pack(expand=True)

        ctk.CTkLabel(
            drop_inner,
            text="Add to Shared",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=self.colors["text_main"]
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            drop_inner,
            text="Drag & Drop files here\nor click below",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.colors["text_sub"],
            justify="center"
        ).pack(pady=(0, 14))

        # Vibrant Gradient Select Files Button
        ctk.CTkButton(
            drop_inner,
            text="Select Files",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=12,
            fg_color=self.colors["accent_blue"],
            hover_color="#2563eb",
            command=self.add_files_to_host_share
        ).pack(fill="x", pady=4)

        # Add Folder Button
        ctk.CTkButton(
            drop_inner,
            text="📁 Add Folder...",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=34,
            corner_radius=10,
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.add_folder_to_host_share
        ).pack(fill="x", pady=3)

        # Clear All Button
        ctk.CTkButton(
            drop_inner,
            text="🗑️ Clear All Staged",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            height=28,
            corner_radius=8,
            fg_color="transparent",
            text_color=self.colors["accent_red"],
            hover_color=self.colors["btn_pill_bg"],
            command=self.clear_all_staged_files
        ).pack(fill="x", pady=(6, 0))

        # Bottom Quick Share Explainer
        hint_card = ctk.CTkFrame(drop_inner, corner_radius=10, fg_color=self.colors["input_bg"], border_width=1, border_color=self.colors["input_border"])
        hint_card.pack(fill="x", side="bottom", pady=(8, 0))
        ctk.CTkLabel(
            hint_card,
            text="⚡ Quick Share Model\nOnly files you drop or select are shared.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_sub"],
            justify="center"
        ).pack(padx=8, pady=8)

    # --- PILLAR 2: CONNECT DEVICE & LIVE HUB ---
    def build_pillar_2_connect_hub(self):
        hub_frame = ctk.CTkFrame(self.col_connect, fg_color="transparent")
        hub_frame.pack(fill="both", expand=True, padx=12, pady=10)

        # Title
        ctk.CTkLabel(
            hub_frame,
            text="📱 Connect Device",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self.colors["text_main"]
        ).pack(pady=(2, 6))

        # Network Mode Pill (Local Wi-Fi vs Internet Mode)
        net_pill = ctk.CTkFrame(hub_frame, corner_radius=12, fg_color=self.colors["input_bg"], border_width=1, border_color=self.colors["input_border"])
        net_pill.pack(fill="x", pady=(0, 6))

        net_inner = ctk.CTkFrame(net_pill, fg_color="transparent")
        net_inner.pack(fill="x", padx=8, pady=6)

        net_info = ctk.CTkFrame(net_inner, fg_color="transparent")
        net_info.pack(side="left")

        ctk.CTkLabel(
            net_info,
            text="🏠 Local Wi-Fi",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=self.colors["text_main"]
        ).pack(anchor="w")

        self.tunnel_sub_lbl = ctk.CTkLabel(
            net_info,
            text="Same Wi-Fi / Hotspot",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_sub"]
        )
        self.tunnel_sub_lbl.pack(anchor="w")

        self.btn_toggle_tunnel = ctk.CTkButton(
            net_inner,
            text="🌐 Enable Internet",
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.toggle_cloudflare_tunnel
        )
        self.btn_toggle_tunnel.pack(side="right")

        # QR White Card (Matching exact web look: Pure white rounded square)
        qr_white_card = ctk.CTkFrame(hub_frame, corner_radius=16, fg_color=self.colors["qr_bg"], width=144, height=144)
        qr_white_card.pack(pady=2)
        qr_white_card.pack_propagate(False)

        self.qr_wrapper = ctk.CTkLabel(qr_white_card, text="[QR Code]")
        self.qr_wrapper.pack(expand=True)

        ctk.CTkLabel(
            hub_frame,
            text="Scan to connect",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_sub"]
        ).pack(pady=(2, 4))

        # PIN Code Display Box (Cyan Neon Numbers + Progress Line)
        pin_box = ctk.CTkFrame(
            hub_frame,
            corner_radius=14,
            fg_color=self.colors["input_bg"],
            border_width=1,
            border_color=self.colors["input_border"]
        )
        pin_box.pack(fill="x", pady=4)

        pin_meta = ctk.CTkFrame(pin_box, fg_color="transparent")
        pin_meta.pack(fill="x", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            pin_meta,
            text="PIN CODE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self.colors["text_sub"]
        ).pack(side="left")

        self.pin_timer_lbl = ctk.CTkLabel(
            pin_meta,
            text="30s",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=self.colors["accent_cyan"]
        )
        self.pin_timer_lbl.pack(side="right")

        # Big Glowing Digital PIN with space between digits
        self.live_pin_lbl = ctk.CTkLabel(
            pin_box,
            text="----",
            font=ctk.CTkFont(family="Consolas", size=28, weight="bold"),
            text_color=self.colors["accent_cyan"]
        )
        self.live_pin_lbl.pack(pady=2)

        # Neon Cyan / Purple Accent Bar
        self.pin_timer_bar = ctk.CTkProgressBar(pin_box, height=3, corner_radius=0)
        self.pin_timer_bar.pack(fill="x", padx=10, pady=(2, 6))
        self.pin_timer_bar.set(1.0)
        self.pin_timer_bar.configure(progress_color=self.colors["accent_cyan"], fg_color=self.colors["btn_pill_bg"])

        # PIN Action Buttons Row
        pin_actions = ctk.CTkFrame(pin_box, fg_color="transparent")
        pin_actions.pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkButton(
            pin_actions,
            text="🔄 Rotate",
            height=24,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.force_rotate_host_pin
        ).pack(side="left", expand=True, padx=2)

        ctk.CTkButton(
            pin_actions,
            text="📋 Copy PIN",
            height=24,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.copy_host_pin
        ).pack(side="right", expand=True, padx=2)

        # Tabbed Live Hub (Activity Log & Quick Clipboard)
        hub_tab_container = ctk.CTkFrame(hub_frame, corner_radius=14, fg_color=self.colors["input_bg"], border_width=1, border_color=self.colors["input_border"])
        hub_tab_container.pack(fill="x", pady=(6, 2))

        # Hub Segmented Switcher
        self.hub_switcher = ctk.CTkSegmentedButton(
            hub_tab_container,
            values=["⚡ Live Log", "📋 Quick Clipboard"],
            command=self.on_hub_tab_change,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            selected_color=self.colors["btn_pill_bg"],
            selected_hover_color=self.colors["btn_pill_hover"],
            height=26
        )
        self.hub_switcher.set("⚡ Live Log")
        self.hub_switcher.pack(fill="x", padx=6, pady=6)

        # Pane 1: Activity Log
        self.hub_log_pane = ctk.CTkTextbox(
            hub_tab_container,
            height=85,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=self.colors["card_bg"],
            text_color=self.colors["text_main"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        self.hub_log_pane.pack(fill="x", padx=6, pady=(0, 6))
        self.hub_log_pane.insert("1.0", "[00:00:00] Server started. Ready for connections.\n")
        self.hub_log_pane.configure(state="disabled")

        # Pane 2: Clipboard Pane (hidden by default)
        self.hub_clip_pane = ctk.CTkFrame(hub_tab_container, fg_color="transparent")
        self.hub_clip_input = ctk.CTkEntry(
            self.hub_clip_pane,
            placeholder_text="Type text or paste URL...",
            height=26,
            font=ctk.CTkFont(size=10),
            fg_color=self.colors["card_bg"],
            border_color=self.colors["card_border"]
        )
        self.hub_clip_input.pack(fill="x", padx=6, pady=(0, 4))

        clip_btn_row = ctk.CTkFrame(self.hub_clip_pane, fg_color="transparent")
        clip_btn_row.pack(fill="x", padx=6, pady=(0, 6))

        ctk.CTkButton(
            clip_btn_row,
            text="Send",
            height=24,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["accent_blue"],
            command=self.broadcast_host_clipboard
        ).pack(side="left", expand=True, padx=(0, 4))

        ctk.CTkButton(
            clip_btn_row,
            text="Copy Current",
            height=24,
            corner_radius=8,
            font=ctk.CTkFont(size=10),
            fg_color=self.colors["btn_pill_bg"],
            command=self.copy_current_host_clipboard
        ).pack(side="right", expand=True)

    def on_hub_tab_change(self, tab):
        if "Log" in tab:
            self.active_hub_tab = "log"
            self.hub_clip_pane.pack_forget()
            self.hub_log_pane.pack(fill="x", padx=8, pady=(0, 8))
        else:
            self.active_hub_tab = "clip"
            self.hub_log_pane.pack_forget()
            self.hub_clip_pane.pack(fill="x", padx=0, pady=(0, 8))

    # --- PILLAR 3: DUAL FILE MANAGERS (Received Files on Top, Shared Files on Bottom) ---
    def build_pillar_3_file_managers(self):
        # Card 1 (Top Half): Received Files
        self.card_received = ctk.CTkFrame(
            self.col_files,
            corner_radius=22,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        self.card_received.pack(fill="both", expand=True, pady=(0, 10))
        self.build_received_files_card()

        # Card 2 (Bottom Half): Shared Files (Quick Share Staged)
        self.card_shared = ctk.CTkFrame(
            self.col_files,
            corner_radius=22,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        self.card_shared.pack(fill="both", expand=True)
        self.build_shared_files_card()

    # --- RECEIVED FILES CARD ---
    def build_received_files_card(self):
        # Header
        header = ctk.CTkFrame(self.card_received, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left")

        ctk.CTkLabel(
            title_col,
            text="📥 Received Files",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self.colors["text_main"]
        ).pack(side="left")

        self.rx_count_lbl = ctk.CTkLabel(
            title_col,
            text="0 files",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_sub"]
        )
        self.rx_count_lbl.pack(side="left", padx=6)

        # Action Pills Row
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        ctk.CTkButton(
            actions,
            text="📦 ZIP All",
            width=68,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda: os.startfile(f"http://127.0.0.1:{main.ACTUAL_PORT}/api/zip?folder=received")
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions,
            text="📂 Open Folder",
            width=88,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda: os.startfile(main.UPLOAD_DIR)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions,
            text="📁 Change",
            width=66,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.change_host_received_folder
        ).pack(side="left", padx=2)

        # Search Bar
        search_frame = ctk.CTkFrame(self.card_received, fg_color="transparent")
        search_frame.pack(fill="x", padx=14, pady=(0, 4))

        self.search_received_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search received...",
            height=28,
            corner_radius=8,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["input_bg"],
            border_color=self.colors["input_border"]
        )
        self.search_received_entry.pack(fill="x")
        self.search_received_entry.bind("<KeyRelease>", self.on_search_received)

        # Scroll Area for Received Files
        self.received_scroll = ctk.CTkScrollableFrame(self.card_received, fg_color="transparent")
        self.received_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def on_search_received(self, event=None):
        self.search_received_query = self.search_received_entry.get().strip().lower()
        self.refresh_host_received_files_list()

    # --- SHARED FILES CARD ---
    def build_shared_files_card(self):
        header = ctk.CTkFrame(self.card_shared, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left")

        ctk.CTkLabel(
            title_col,
            text="📤 Shared Files",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self.colors["text_main"]
        ).pack(side="left")

        self.tx_count_lbl = ctk.CTkLabel(
            title_col,
            text="0 files staged",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_sub"]
        )
        self.tx_count_lbl.pack(side="left", padx=6)

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        ctk.CTkButton(
            actions,
            text="➕ Add",
            width=58,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.add_files_to_host_share
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions,
            text="🗑️ Clear",
            width=62,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            text_color=self.colors["accent_red"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.clear_all_staged_files
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions,
            text="📦 ZIP All",
            width=68,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda: os.startfile(f"http://127.0.0.1:{main.ACTUAL_PORT}/api/zip?folder=shared")
        ).pack(side="left", padx=2)

        search_frame = ctk.CTkFrame(self.card_shared, fg_color="transparent")
        search_frame.pack(fill="x", padx=14, pady=(0, 4))

        self.search_shared_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search shared...",
            height=28,
            corner_radius=8,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["input_bg"],
            border_color=self.colors["input_border"]
        )
        self.search_shared_entry.pack(fill="x")
        self.search_shared_entry.bind("<KeyRelease>", self.on_search_shared)

        self.shared_scroll = ctk.CTkScrollableFrame(self.card_shared, fg_color="transparent")
        self.shared_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def on_search_shared(self, event=None):
        self.search_shared_query = self.search_shared_entry.get().strip().lower()
        self.refresh_host_shared_files_list()

    # =========================================================================
    # 5. CLIENT MODE: MATCHING client_dark.png LAYOUT
    # =========================================================================
    def build_client_view(self):
        # Header Connection Card
        conn_card = ctk.CTkFrame(
            self.client_frame,
            corner_radius=20,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        conn_card.pack(fill="x", pady=(0, 10))

        title_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            title_row,
            text="Connect to a PyShare Host (Phone, PC, or Mac)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors["accent_cyan"]
        ).pack(side="left")

        self.client_status_pill = ctk.CTkLabel(
            title_row,
            text="⚪ Not Connected",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors["text_sub"],
            fg_color=self.colors["input_bg"],
            corner_radius=10,
            padx=10,
            pady=4
        )
        self.client_status_pill.pack(side="right")

        # Inputs Row (Host IP, PIN, Connect Button, Auto-Discover Button)
        inputs_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        inputs_row.pack(fill="x", padx=16, pady=(4, 6))

        ctk.CTkLabel(inputs_row, text="Host Address:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.client_host_entry = ctk.CTkEntry(
            inputs_row,
            placeholder_text="192.168.1.5:8010",
            width=180,
            font=ctk.CTkFont(size=12),
            fg_color=self.colors["input_bg"],
            border_color=self.colors["input_border"]
        )
        self.client_host_entry.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(inputs_row, text="Room PIN:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.client_pin_entry = ctk.CTkEntry(
            inputs_row,
            placeholder_text="4-digit PIN",
            width=95,
            font=ctk.CTkFont(size=12),
            fg_color=self.colors["input_bg"],
            border_color=self.colors["input_border"]
        )
        self.client_pin_entry.pack(side="left", padx=(0, 12))

        self.client_connect_btn = ctk.CTkButton(
            inputs_row,
            text="⚡ Connect",
            width=100,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.colors["accent_blue"],
            hover_color="#2563eb",
            command=self.toggle_client_connection
        )
        self.client_connect_btn.pack(side="left", padx=(0, 8))

        self.client_discover_btn = ctk.CTkButton(
            inputs_row,
            text="🔍 Auto-Discover",
            width=120,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.auto_discover_hosts_network
        )
        self.client_discover_btn.pack(side="left")

        # Download Destination Settings Row
        dl_dest_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        dl_dest_row.pack(fill="x", padx=16, pady=(2, 10))

        ctk.CTkLabel(
            dl_dest_row,
            text="📥 Save Downloaded Files To:",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="left", padx=(0, 6))

        self.client_dl_path_lbl = ctk.CTkLabel(
            dl_dest_row,
            text=truncate_path(self.client_download_dir, max_len=45),
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.colors["accent_cyan"]
        )
        self.client_dl_path_lbl.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            dl_dest_row,
            text="📁 Change...",
            height=24,
            width=80,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.change_client_download_folder
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            dl_dest_row,
            text="📂 Open",
            height=24,
            width=50,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda: os.startfile(self.client_download_dir)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            dl_dest_row,
            text="🔄 Reset",
            height=24,
            width=50,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.reset_client_download_folder
        ).pack(side="left", padx=2)

        # Body Split (Left: Download from Host, Right: Send to Host)
        client_body = ctk.CTkFrame(self.client_frame, fg_color="transparent")
        client_body.pack(fill="both", expand=True)

        self.client_download_col = ctk.CTkFrame(
            client_body,
            corner_radius=20,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        self.client_download_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.client_upload_col = ctk.CTkFrame(
            client_body,
            width=420,
            corner_radius=20,
            fg_color=self.colors["card_bg"],
            border_width=1,
            border_color=self.colors["card_border"]
        )
        self.client_upload_col.pack(side="right", fill="both")
        self.client_upload_col.pack_propagate(False)

        # Left: Download Files from Host
        dl_header = ctk.CTkFrame(self.client_download_col, fg_color="transparent")
        dl_header.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(dl_header, text="💾 Download from Host", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        self.client_dl_all_btn = ctk.CTkButton(
            dl_header,
            text="📦 ZIP All",
            width=70,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.client_download_all_zip,
            state="disabled"
        )
        self.client_dl_all_btn.pack(side="right", padx=2)

        self.client_refresh_btn = ctk.CTkButton(
            dl_header,
            text="🔄 Refresh",
            width=70,
            height=26,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.fetch_client_host_files,
            state="disabled"
        )
        self.client_refresh_btn.pack(side="right", padx=2)

        # Search Bar for Host Files (Matching client_dark.png)
        client_search_frame = ctk.CTkFrame(self.client_download_col, fg_color="transparent")
        client_search_frame.pack(fill="x", padx=14, pady=(0, 4))

        self.client_search_entry = ctk.CTkEntry(
            client_search_frame,
            placeholder_text="🔍 Search host files...",
            height=28,
            corner_radius=8,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["input_bg"],
            border_color=self.colors["input_border"]
        )
        self.client_search_entry.pack(fill="x")
        self.client_search_entry.bind("<KeyRelease>", self.on_client_search)

        self.client_files_scroll = ctk.CTkScrollableFrame(self.client_download_col, fg_color="transparent")
        self.client_files_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Right: Send to Host Card (Matching client_dark.png!)
        ul_card = ctk.CTkFrame(
            self.client_upload_col,
            corner_radius=18,
            fg_color=self.colors["input_bg"],
            border_width=2,
            border_color=self.colors["card_border_glow"]
        )
        ul_card.pack(fill="x", padx=12, pady=(10, 6))

        ul_inner = ctk.CTkFrame(ul_card, fg_color="transparent")
        ul_inner.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(ul_inner, text="☁️", font=ctk.CTkFont(size=30)).pack()
        ctk.CTkLabel(ul_inner, text="Send to Host", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=1)
        ctk.CTkLabel(ul_inner, text="Tap here to upload files", font=ctk.CTkFont(size=10), text_color=self.colors["text_sub"]).pack(pady=(0, 6))

        self.client_select_files_btn = ctk.CTkButton(
            ul_inner,
            text="Browse Files",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            corner_radius=10,
            fg_color=self.colors["accent_blue"],
            command=self.client_select_files_for_upload,
            state="disabled"
        )
        self.client_select_files_btn.pack(fill="x")

        # Queued Files Box
        self.client_upload_queue_box = ctk.CTkTextbox(
            self.client_upload_col,
            height=75,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["input_bg"],
            border_width=1,
            border_color=self.colors["input_border"]
        )
        self.client_upload_queue_box.pack(fill="x", padx=12, pady=3)
        self.client_upload_queue_box.insert("1.0", "No files queued for upload.")
        self.client_upload_queue_box.configure(state="disabled")

        self.client_send_btn = ctk.CTkButton(
            self.client_upload_col,
            text="🚀 Upload Queued Files to Host",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            corner_radius=10,
            fg_color=self.colors["accent_green"],
            hover_color="#059669",
            command=self.client_execute_upload,
            state="disabled"
        )
        self.client_send_btn.pack(fill="x", padx=12, pady=3)

        # Client Progress Bar
        self.client_progress_bar = ctk.CTkProgressBar(self.client_upload_col, height=5)
        self.client_progress_bar.pack(fill="x", padx=12, pady=(4, 2))
        self.client_progress_bar.set(0)
        self.client_progress_bar.configure(progress_color=self.colors["accent_cyan"], fg_color=self.colors["btn_pill_bg"])

        self.client_progress_lbl = ctk.CTkLabel(self.client_upload_col, text="Ready", font=ctk.CTkFont(size=10), text_color=self.colors["text_sub"])
        self.client_progress_lbl.pack(padx=12, pady=(0, 4))

        # Client Clipboard Card
        clip_card = ctk.CTkFrame(self.client_upload_col, corner_radius=14, fg_color=self.colors["input_bg"], border_width=1, border_color=self.colors["input_border"])
        clip_card.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        ctk.CTkLabel(clip_card, text="📋 Host Clipboard", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 2))

        self.client_clipboard_entry = ctk.CTkEntry(
            clip_card,
            placeholder_text="Send text to host clipboard...",
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["card_bg"],
            border_color=self.colors["card_border"]
        )
        self.client_clipboard_entry.pack(fill="x", padx=10, pady=3)

        clip_btn_row = ctk.CTkFrame(clip_card, fg_color="transparent")
        clip_btn_row.pack(fill="x", padx=10, pady=(0, 6))

        self.client_clip_send_btn = ctk.CTkButton(
            clip_btn_row,
            text="Send Text",
            width=80,
            height=24,
            corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=self.colors["accent_blue"],
            command=self.client_send_clipboard_to_host,
            state="disabled"
        )
        self.client_clip_send_btn.pack(side="left", padx=(0, 4))

        self.client_clip_copy_btn = ctk.CTkButton(
            clip_btn_row,
            text="Copy Host Text",
            width=100,
            height=24,
            corner_radius=8,
            font=ctk.CTkFont(size=10),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=self.client_copy_host_clipboard,
            state="disabled"
        )
        self.client_clip_copy_btn.pack(side="left")

    # =========================================================================
    # 6. QUICK SHARE STAGING & DRAG-AND-DROP ACTIONS
    # =========================================================================
    def on_drop_files(self, file_paths):
        if not file_paths:
            return
        if self.current_mode == "host":
            count = main.stage_files(file_paths)
            self.refresh_host_shared_files_list()
            self.add_log_entry(f"Added {count} file(s) to Quick Share")
            messagebox.showinfo("Quick Share", f"Added {count} file{'s' if count != 1 else ''} to Quick Share!\nPeers can now download them.")
        else:
            valid_files = [p for p in file_paths if os.path.isfile(p)]
            if not valid_files:
                return
            for vf in valid_files:
                if vf not in self.client_selected_upload_files:
                    self.client_selected_upload_files.append(vf)
            self.update_client_upload_queue_ui()

    def add_files_to_host_share(self):
        paths = filedialog.askopenfilenames(title="Select Specific Files to Quick Share")
        if not paths:
            return
        count = main.stage_files(paths)
        self.refresh_host_shared_files_list()
        self.add_log_entry(f"Added {count} file(s) to Quick Share")
        messagebox.showinfo("Quick Share", f"Added {count} file{'s' if count != 1 else ''} to Quick Share!")

    def add_folder_to_host_share(self):
        folder = filedialog.askdirectory(title="Select Folder to Quick Share")
        if not folder:
            return
        count = main.stage_files([folder])
        self.refresh_host_shared_files_list()
        self.add_log_entry(f"Added {count} file(s) from folder to Quick Share")
        messagebox.showinfo("Quick Share", f"Added {count} file{'s' if count != 1 else ''} from folder to Quick Share!")

    def clear_all_staged_files(self):
        if messagebox.askyesno("Clear All", "Unstage all files from Quick Share?\n(Original files on your disk will NOT be deleted)."):
            main.clear_staged_files()
            self.refresh_host_shared_files_list()
            self.add_log_entry("Cleared all staged files")

    def unstage_host_file(self, filename):
        main.unstage_file(filename)
        self.refresh_host_shared_files_list()
        self.add_log_entry(f"Unstaged: {filename}")

    def add_log_entry(self, msg):
        t = time.strftime("%H:%M:%S")
        self.hub_log_pane.configure(state="normal")
        self.hub_log_pane.insert("1.0", f"[{t}] {msg}\n")
        self.hub_log_pane.configure(state="disabled")

    # =========================================================================
    # 7. FOLDER STORAGE PATH CUSTOMIZATION
    # =========================================================================
    def change_host_shared_folder(self):
        new_dir = filedialog.askdirectory(title="Select Default Shared Directory", initialdir=main.DOWNLOAD_DIR)
        if new_dir and os.path.isdir(new_dir):
            if main.set_custom_shared_dir(new_dir):
                self.refresh_host_shared_files_list()
                self.add_log_entry(f"Shared folder: {new_dir}")
                messagebox.showinfo("Folder Updated", f"Default shared folder set to:\n{new_dir}")

    def change_host_received_folder(self):
        new_dir = filedialog.askdirectory(title="Select Folder to Store Incoming Uploads", initialdir=main.UPLOAD_DIR)
        if new_dir and os.path.isdir(new_dir):
            if main.set_custom_received_dir(new_dir):
                self.refresh_host_received_files_list()
                self.add_log_entry(f"Received folder: {new_dir}")
                messagebox.showinfo("Folder Updated", f"Incoming uploads will now be saved in:\n{new_dir}")

    def change_client_download_folder(self):
        new_dir = filedialog.askdirectory(title="Select Destination Folder for Downloaded Files", initialdir=self.client_download_dir)
        if new_dir and os.path.isdir(new_dir):
            self.client_download_dir = os.path.abspath(new_dir)
            self.client_dl_path_lbl.configure(text=truncate_path(self.client_download_dir, max_len=45))
            self.app_config["client_download_dir"] = self.client_download_dir
            main.save_app_config(self.app_config)
            messagebox.showinfo("Folder Updated", f"Downloaded files will now be saved in:\n{self.client_download_dir}")

    def reset_client_download_folder(self):
        default_dir = self.defaults["client_download_dir"]
        os.makedirs(default_dir, exist_ok=True)
        self.client_download_dir = default_dir
        self.client_dl_path_lbl.configure(text=truncate_path(self.client_download_dir, max_len=45))
        self.app_config["client_download_dir"] = self.client_download_dir
        main.save_app_config(self.app_config)
        messagebox.showinfo("Reset to Default", f"Download destination reset to:\n{default_dir}")

    def open_base_storage_dir(self):
        if os.path.exists(main.BASE_DIR):
            os.startfile(main.BASE_DIR)

    # =========================================================================
    # 8. HOST CONTROLS & SERVER ENGINE
    # =========================================================================
    def start_host_server(self):
        def _run():
            try:
                main.DOWNLOAD_DIR = os.path.abspath(self.app_config.get("shared_dir", self.defaults["shared_dir"]))
                main.UPLOAD_DIR = os.path.abspath(self.app_config.get("received_dir", self.defaults["received_dir"]))
                os.makedirs(main.UPLOAD_DIR, exist_ok=True)
                os.makedirs(main.DOWNLOAD_DIR, exist_ok=True)
                main.BASE_DIR = os.path.dirname(main.DOWNLOAD_DIR)

                main.socketserver.TCPServer.allow_reuse_address = True
                for port in range(main.START_PORT, main.START_PORT + 10):
                    try:
                        server = main.socketserver.ThreadingTCPServer(("", port), main.FinalFileHandler)
                        main.ACTUAL_PORT = port
                        main.httpd = server
                        break
                    except OSError:
                        continue

                main.start_pin_rotator()

                ip = main.get_ip()
                url = f"http://{ip}:{main.ACTUAL_PORT}"
                main.generate_qr(url)

                try:
                    main.zc = main.Zeroconf()
                    desc = {'app': 'PyShare', 'device': socket.gethostname(), 'url': url}
                    info = main.ServiceInfo(
                        "_pyshare._tcp.local.",
                        f"{socket.gethostname()}._pyshare._tcp.local.",
                        addresses=[socket.inet_aton(ip)],
                        port=main.ACTUAL_PORT,
                        properties=desc,
                        server=f"{socket.gethostname()}.local."
                    )
                    main.zc.register_service(info)
                except Exception as e:
                    print(f"[*] mDNS Notice: {e}")

                main.httpd.serve_forever()
            except Exception as e:
                print(f"[!] Server Startup Error: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def force_rotate_host_pin(self):
        with main.state_lock:
            main.PREVIOUS_PIN = main.CURRENT_PIN
            main.CURRENT_PIN = f"{main.random.randint(1000, 9999)}"
            main.NEXT_CHANGE = time.time() + 30
        pin = main.CURRENT_PIN
        self.live_pin_lbl.configure(text=f"{pin[0]}  {pin[1]}  {pin[2]}  {pin[3]}")
        self.update_qr_image()
        self.add_log_entry(f"PIN rotated: {pin}")

    def copy_host_pin(self):
        self.clipboard_clear()
        self.clipboard_append(main.CURRENT_PIN)
        messagebox.showinfo("Copied", f"PIN copied to clipboard:\n{main.CURRENT_PIN}")

    def copy_host_url(self):
        url = f"http://{main.get_ip()}:{main.ACTUAL_PORT}"
        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo("Copied", f"Host URL copied to clipboard:\n{url}")

    def toggle_cloudflare_tunnel(self):
        status = getattr(main, 'TUNNEL_STATUS', 'idle')
        if status in ('starting', 'active', 'downloading'):
            main.stop_tunnel()
            self.btn_toggle_tunnel.configure(text="🌐 Enable Internet")
            self.tunnel_sub_lbl.configure(text="Same Wi-Fi / Hotspot")
            self.add_log_entry("Reverted to Local Wi-Fi Mode")
        else:
            main.start_tunnel()
            self.btn_toggle_tunnel.configure(text="⏳ Connecting...")
            self.tunnel_sub_lbl.configure(text="Connecting Cloudflare...")
            self.add_log_entry("Starting Public Internet Mode...")

    def broadcast_host_clipboard(self):
        text = self.hub_clip_input.get().strip()
        if text:
            with main.state_lock:
                main.SHARED_TEXT = text
                main.TEXT_TIMESTAMP = time.time()
            main.broadcast_sse("clipboard", {"text": text, "timestamp": main.TEXT_TIMESTAMP})
            self.add_log_entry(f"Clipboard broadcasted: {text[:25]}...")
            messagebox.showinfo("Broadcast", "Clipboard broadcasted to all connected peers!")

    def copy_current_host_clipboard(self):
        text = getattr(main, 'SHARED_TEXT', '')
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Current clipboard copied to your clipboard!")

    # =========================================================================
    # 9. CLIENT ENGINE (CONNECT, DISCOVER, UPLOAD, DOWNLOAD)
    # =========================================================================
    def toggle_client_connection(self):
        if self.client_connected:
            self.disconnect_client()
        else:
            self.connect_to_host()

    def connect_to_host(self):
        raw_host = self.client_host_entry.get().strip()
        pin = self.client_pin_entry.get().strip()

        if not raw_host:
            messagebox.showwarning("Input Required", "Please enter the Host Address (e.g. 192.168.1.5:8010)")
            return
        if not pin or len(pin) != 4:
            messagebox.showwarning("Input Required", "Please enter the 4-digit Room PIN shown on the Host")
            return

        if not raw_host.startswith("http://") and not raw_host.startswith("https://"):
            raw_host = "http://" + raw_host

        self.client_status_pill.configure(text="🟡 Connecting...", text_color="#f59e0b")
        self.client_connect_btn.configure(state="disabled")

        def _worker():
            try:
                login_url = f"{raw_host.rstrip('/')}/login"
                resp = self.client_session.post(login_url, data={"pin": pin}, timeout=6)
                if resp.status_code == 200:
                    self.after(0, lambda: self.on_client_connect_success(raw_host.rstrip('/')))
                elif resp.status_code == 429:
                    self.after(0, lambda: self.on_client_connect_error("Too many failed attempts. Locked out for 30 seconds."))
                elif resp.status_code == 401:
                    self.after(0, lambda: self.on_client_connect_error("Invalid PIN. Please check the 4-digit PIN on the host device."))
                else:
                    self.after(0, lambda: self.on_client_connect_error(f"Host responded with HTTP {resp.status_code}"))
            except Exception as e:
                self.after(0, lambda: self.on_client_connect_error(f"Could not connect to host:\n{e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def on_client_connect_success(self, base_url):
        self.client_connected = True
        self.client_host_url = base_url
        self.client_status_pill.configure(text=f"🟢 Connected ({base_url.replace('http://', '')})", text_color=self.colors["accent_green"])
        self.client_connect_btn.configure(text="Disconnect", state="normal", fg_color=self.colors["accent_red"], hover_color="#dc2626")
        self.client_host_entry.configure(state="disabled")
        self.client_pin_entry.configure(state="disabled")

        self.client_refresh_btn.configure(state="normal")
        self.client_dl_all_btn.configure(state="normal")
        self.client_select_files_btn.configure(state="normal")
        if self.client_selected_upload_files:
            self.client_send_btn.configure(state="normal")
        self.client_clip_send_btn.configure(state="normal")
        self.client_clip_copy_btn.configure(state="normal")

        self.status_dot.configure(text_color=self.colors["accent_green"])
        self.status_text_lbl.configure(text=f"Connected to Host ({base_url.replace('http://', '')})")

        self.fetch_client_host_files()
        self.fetch_client_host_clipboard()

    def on_client_connect_error(self, err_msg):
        self.client_status_pill.configure(text="⚪ Disconnected", text_color=self.colors["text_sub"])
        self.client_connect_btn.configure(state="normal")
        messagebox.showerror("Connection Failed", err_msg)

    def disconnect_client(self):
        self.client_connected = False
        self.client_host_url = ""
        self.client_session = requests.Session()
        self.client_status_pill.configure(text="⚪ Not Connected", text_color=self.colors["text_sub"])
        self.client_connect_btn.configure(text="⚡ Connect", state="normal", fg_color=self.colors["accent_blue"], hover_color="#2563eb")
        self.client_host_entry.configure(state="normal")
        self.client_pin_entry.configure(state="normal")

        self.client_refresh_btn.configure(state="disabled")
        self.client_dl_all_btn.configure(state="disabled")
        self.client_select_files_btn.configure(state="disabled")
        self.client_send_btn.configure(state="disabled")
        self.client_clip_send_btn.configure(state="disabled")
        self.client_clip_copy_btn.configure(state="disabled")

        self.status_dot.configure(text_color=self.colors["text_sub"])
        self.status_text_lbl.configure(text="Disconnected from Host")

        for widget in self.client_files_scroll.winfo_children():
            widget.destroy()

    def auto_discover_hosts_network(self):
        self.client_status_pill.configure(text="🔍 Scanning Wi-Fi...", text_color=self.colors["accent_cyan"])
        self.client_discover_btn.configure(state="disabled")

        def _scan():
            discovered = []
            try:
                zc = main.Zeroconf()
                class Listener:
                    def add_service(self, z, type_, name):
                        info = z.get_service_info(type_, name)
                        if info and info.addresses:
                            ip = socket.inet_ntoa(info.addresses[0])
                            port = info.port
                            server_name = info.server.replace(".local.", "")
                            discovered.append({"name": server_name, "addr": f"{ip}:{port}"})
                    def update_service(self, z, type_, name): pass
                    def remove_service(self, z, type_, name): pass

                browser = main.ServiceBrowser(zc, "_pyshare._tcp.local.", Listener())
                time.sleep(2.5)
                zc.close()
            except Exception as e:
                print(f"Discovery error: {e}")

            self.after(0, lambda: self.on_auto_discovery_done(discovered))

        threading.Thread(target=_scan, daemon=True).start()

    def on_auto_discovery_done(self, discovered):
        self.client_discover_btn.configure(state="normal")
        self.client_status_pill.configure(text="⚪ Not Connected" if not self.client_connected else "🟢 Connected", text_color=self.colors["text_sub"] if not self.client_connected else self.colors["accent_green"])
        if not discovered:
            messagebox.showinfo("Auto-Discovery", "No PyShare devices found on this Wi-Fi network.\n\nTip: Enter the host IP and PIN manually.")
            return

        first = discovered[0]
        self.client_host_entry.delete(0, "end")
        self.client_host_entry.insert(0, first["addr"])
        messagebox.showinfo("Device Found!", f"Discovered PyShare device:\n{first['name']} ({first['addr']})\n\nAddress filled! Enter the PIN and click Connect.")

    def fetch_client_host_files(self):
        if not self.client_connected or not self.client_host_url:
            return

        def _fetch():
            try:
                r = self.client_session.get(f"{self.client_host_url}/api/files", timeout=6)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict):
                        files = data.get("host") or data.get("pc") or []
                    elif isinstance(data, list):
                        files = data
                    else:
                        files = []
                    self.after(0, lambda: self.render_client_host_files_list(files))
            except Exception as e:
                print(f"Error fetching host files: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    def on_client_search(self, event=None):
        self.search_client_query = self.client_search_entry.get().strip().lower()
        self.render_client_host_files_list(self.client_files)

    def render_client_host_files_list(self, files):
        self.client_files = files or []
        for widget in self.client_files_scroll.winfo_children():
            widget.destroy()

        display_files = self.client_files
        if getattr(self, 'search_client_query', ''):
            display_files = [f for f in display_files if self.search_client_query in f.get('name', '').lower()]

        if not display_files:
            ctk.CTkLabel(
                self.client_files_scroll,
                text="Host has not shared any files yet." if not self.client_files else "No matching files found.",
                font=ctk.CTkFont(size=11),
                text_color=self.colors["text_sub"]
            ).pack(pady=20)
            return

        for f in display_files:
            fn = f.get("name", "Unknown")
            sz = f.get("size", 0)
            icon = get_file_icon(fn)

            row = ctk.CTkFrame(
                self.client_files_scroll,
                fg_color=self.colors["row_bg"],
                border_width=1,
                border_color=self.colors["row_border"],
                corner_radius=10
            )
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=15), width=28).pack(side="left", padx=(8, 4), pady=5)

            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="x", expand=True, padx=4)

            ctk.CTkLabel(info_col, text=fn, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.colors["text_main"], anchor="w").pack(fill="x")
            ctk.CTkLabel(info_col, text=format_size(sz), font=ctk.CTkFont(size=10), text_color=self.colors["text_sub"], anchor="w").pack(fill="x")

            # Circular Action Buttons (Matching client_dark.png: 👁️ Preview, ⬇️ Download)
            btn_col = ctk.CTkFrame(row, fg_color="transparent")
            btn_col.pack(side="right", padx=6, pady=4)

            ctk.CTkButton(
                btn_col,
                text="👁️",
                width=28,
                height=28,
                corner_radius=14,
                font=ctk.CTkFont(size=11),
                fg_color=self.colors["btn_pill_bg"],
                border_width=1,
                border_color=self.colors["btn_pill_border"],
                hover_color=self.colors["btn_pill_hover"],
                command=lambda filename=fn: os.startfile(f"{self.client_host_url}/download/{requests.utils.quote(filename)}")
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_col,
                text="⬇️",
                width=28,
                height=28,
                corner_radius=14,
                font=ctk.CTkFont(size=11),
                fg_color=self.colors["btn_pill_bg"],
                border_width=1,
                border_color=self.colors["btn_pill_border"],
                hover_color=self.colors["btn_pill_hover"],
                command=lambda filename=fn: self.client_download_file(filename)
            ).pack(side="left", padx=2)

    def client_download_file(self, filename):
        if not self.client_connected or self.is_client_downloading:
            return

        dest_dir = self.client_download_dir
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)

        self.is_client_downloading = True
        self.client_progress_lbl.configure(text=f"Downloading {filename}...")

        def _worker():
            try:
                url = f"{self.client_host_url}/download/{requests.utils.quote(filename)}"
                with self.client_session.get(url, stream=True, timeout=20) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = time.time()

                    with open(dest_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    pct = downloaded / total
                                    elapsed = max(0.1, time.time() - start_time)
                                    speed = downloaded / elapsed
                                    self.after(0, lambda p=pct, sp=speed: self.update_client_download_progress(p, sp))

                self.after(0, lambda: self.on_client_download_success(filename, dest_path))
            except Exception as e:
                self.after(0, lambda: self.on_client_download_error(filename, str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def update_client_download_progress(self, pct, speed):
        self.client_progress_bar.set(pct)
        self.client_progress_lbl.configure(text=f"Downloading ({int(pct * 100)}%) • {format_size(speed)}/s")

    def on_client_download_success(self, filename, path):
        self.is_client_downloading = False
        self.client_progress_bar.set(1.0)
        self.client_progress_lbl.configure(text=f"Saved to {os.path.basename(self.client_download_dir)}: {filename}")
        if messagebox.askyesno("Download Complete", f"File saved:\n{path}\n\nDo you want to open it now?"):
            os.startfile(path)

    def on_client_download_error(self, filename, err):
        self.is_client_downloading = False
        self.client_progress_bar.set(0)
        self.client_progress_lbl.configure(text="Download failed")
        messagebox.showerror("Download Error", f"Failed to download {filename}:\n{err}")

    def client_download_all_zip(self):
        if not self.client_connected or self.is_client_downloading:
            return
        dest_dir = self.client_download_dir
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, f"PyShare_Files_{int(time.time())}.zip")
        self.is_client_downloading = True
        self.client_progress_lbl.configure(text="Downloading ZIP archive...")

        def _worker():
            try:
                url = f"{self.client_host_url}/api/zip?folder=shared"
                with self.client_session.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = time.time()
                    with open(dest_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=128 * 1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    pct = downloaded / total
                                    elapsed = max(0.1, time.time() - start_time)
                                    speed = downloaded / elapsed
                                    self.after(0, lambda p=pct, sp=speed: self.update_client_download_progress(p, sp))
                self.after(0, lambda: self.on_client_download_success("PyShare_Archive.zip", dest_path))
            except Exception as e:
                self.after(0, lambda: self.on_client_download_error("Archive.zip", str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def client_select_files_for_upload(self):
        paths = filedialog.askopenfilenames(title="Select Files to Upload to Host")
        if not paths:
            return
        for p in paths:
            if p not in self.client_selected_upload_files:
                self.client_selected_upload_files.append(p)
        self.update_client_upload_queue_ui()

    def update_client_upload_queue_ui(self):
        self.client_upload_queue_box.configure(state="normal")
        self.client_upload_queue_box.delete("1.0", "end")
        if not self.client_selected_upload_files:
            self.client_upload_queue_box.insert("1.0", "No files queued. Drag & drop files here or click 'Browse Files'.")
            self.client_send_btn.configure(state="disabled")
            self.client_progress_lbl.configure(text="Ready")
        else:
            total_size = sum(os.path.getsize(p) for p in self.client_selected_upload_files if os.path.isfile(p))
            for p in self.client_selected_upload_files:
                sz = os.path.getsize(p) if os.path.isfile(p) else 0
                self.client_upload_queue_box.insert("end", f"• {os.path.basename(p)} ({format_size(sz)})\n")
            if self.client_connected and not self.is_client_uploading:
                self.client_send_btn.configure(state="normal")
            self.client_progress_lbl.configure(text=f"{len(self.client_selected_upload_files)} file(s) queued ({format_size(total_size)})")
        self.client_upload_queue_box.configure(state="disabled")

    def client_execute_upload(self):
        if not self.client_connected or not self.client_selected_upload_files:
            messagebox.showwarning("No Files", "Please select files to upload first.")
            return
        if self.is_client_uploading:
            return

        self.is_client_uploading = True
        self.client_send_btn.configure(state="disabled")
        self.client_select_files_btn.configure(state="disabled")
        files_to_send = list(self.client_selected_upload_files)

        def _worker():
            total_files = len(files_to_send)
            for idx, p in enumerate(files_to_send):
                if not os.path.isfile(p):
                    continue
                fn = os.path.basename(p)
                file_size = os.path.getsize(p)
                self.after(0, lambda i=idx+1, name=fn: self.client_progress_lbl.configure(text=f"Uploading {i}/{total_files}: {name}..."))
                try:
                    url = f"{self.client_host_url}/upload"
                    headers = {
                        'X-File-Name': requests.utils.quote(fn),
                        'Content-Type': 'application/octet-stream',
                        'Content-Length': str(file_size)
                    }
                    with open(p, 'rb') as f:
                        resp = self.client_session.post(url, data=f, headers=headers, timeout=120)
                        if resp.status_code != 200:
                            raise Exception(f"HTTP {resp.status_code}")
                    self.after(0, lambda p=(idx + 1) / total_files: self.client_progress_bar.set(p))
                except Exception as e:
                    self.after(0, lambda name=fn, err=str(e): messagebox.showerror("Upload Error", f"Failed to upload {name}:\n{err}"))
                    break

            self.after(0, self.on_client_upload_complete)

        threading.Thread(target=_worker, daemon=True).start()

    def on_client_upload_complete(self):
        self.is_client_uploading = False
        self.client_selected_upload_files = []
        self.client_select_files_btn.configure(state="normal")
        self.client_send_btn.configure(state="disabled")
        self.client_upload_queue_box.configure(state="normal")
        self.client_upload_queue_box.delete("1.0", "end")
        self.client_upload_queue_box.insert("1.0", "All files uploaded successfully!")
        self.client_upload_queue_box.configure(state="disabled")
        self.client_progress_bar.set(1.0)
        self.client_progress_lbl.configure(text="Upload Complete ✅")
        messagebox.showinfo("Upload Complete", "All files were uploaded to the Host successfully!")

    def fetch_client_host_clipboard(self):
        if not self.client_connected:
            return
        def _fetch():
            try:
                r = self.client_session.get(f"{self.client_host_url}/api/clipboard", timeout=4)
                if r.status_code == 200:
                    text = r.json().get("clipboard", "")
                    self.after(0, lambda: self.client_clipboard_entry.delete(0, "end"))
                    self.after(0, lambda: self.client_clipboard_entry.insert(0, text))
            except Exception: pass
        threading.Thread(target=_fetch, daemon=True).start()

    def client_send_clipboard_to_host(self):
        text = self.client_clipboard_entry.get().strip()
        if not text or not self.client_connected:
            return
        def _worker():
            try:
                self.client_session.post(f"{self.client_host_url}/api/clipboard", json={"text": text}, timeout=4)
                self.after(0, lambda: messagebox.showinfo("Clipboard", "Text sent to host clipboard!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to send text: {e}"))
        threading.Thread(target=_worker, daemon=True).start()

    def client_copy_host_clipboard(self):
        text = self.client_clipboard_entry.get().strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Host clipboard text copied to your clipboard!")

    # =========================================================================
    # 10. REAL-TIME REFRESH TICKER & LIST UPDATERS
    # =========================================================================
    def refresh_ticker(self):
        try:
            if self.current_mode == "host":
                self.refresh_host_ui()
            elif self.current_mode == "client" and self.client_connected:
                pass
        except Exception:
            pass
        self.after(1000, self.refresh_ticker)

    def refresh_host_ui(self):
        # Update PIN display & Timer
        pin = getattr(main, 'CURRENT_PIN', '----')
        if len(pin) == 4:
            self.live_pin_lbl.configure(text=f"{pin[0]}  {pin[1]}  {pin[2]}  {pin[3]}")
        else:
            self.live_pin_lbl.configure(text=pin)

        now = time.time()
        next_change = getattr(main, 'NEXT_CHANGE', now + 30)
        rem = max(0, int(next_change - now))
        self.pin_timer_lbl.configure(text=f"{rem}s")
        self.pin_timer_bar.set(rem / 30.0)

        # Update Local IP Label
        ip = main.get_ip()
        self.status_text_lbl.configure(text=f"Server IP: {ip}:{main.ACTUAL_PORT}")

        # Update Tunnel Status
        tunnel_url = getattr(main, 'TUNNEL_URL', None)
        tunnel_status = getattr(main, 'TUNNEL_STATUS', 'idle')
        if tunnel_status == "active" and tunnel_url:
            self.tunnel_sub_lbl.configure(text=truncate_path(tunnel_url, max_len=24))
            self.btn_toggle_tunnel.configure(text="🛑 Stop Internet")
        elif tunnel_status in ("starting", "downloading"):
            self.tunnel_sub_lbl.configure(text=f"{tunnel_status.capitalize()}...")
            self.btn_toggle_tunnel.configure(text="⏳ Connecting...")
        else:
            self.tunnel_sub_lbl.configure(text="Same Wi-Fi / Hotspot")
            self.btn_toggle_tunnel.configure(text="🌐 Enable Internet")

        # Update QR image if needed
        self.update_qr_image()

        # Update File Lists
        self.refresh_host_shared_files_list()
        self.refresh_host_received_files_list()

    def update_qr_image(self):
        qr_file = main.get_qr_path() if hasattr(main, 'get_qr_path') else (os.path.join(main.BASE_DIR, "qrcode.png") if getattr(main, 'BASE_DIR', '') else "")
        if not qr_file or not os.path.isfile(qr_file):
            qr_file = resource_path("qrcode.png")
        if os.path.isfile(qr_file):
            mtime = os.path.getmtime(qr_file)
            if mtime > self.last_qr_timestamp or self.qr_ctk_image is None:
                self.last_qr_timestamp = mtime
                try:
                    with open(qr_file, "rb") as f:
                        img_bytes = io.BytesIO(f.read())
                    with Image.open(img_bytes) as pil_raw:
                        pil_img = pil_raw.copy().resize((132, 132))
                    self.qr_ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(132, 132))
                    self.qr_wrapper.configure(image=self.qr_ctk_image, text="")
                except Exception:
                    pass

    # --- REFRESH SHARED FILES LIST ---
    def refresh_host_shared_files_list(self):
        staged = main.get_staged_files()
        total_size = sum(item.get("size", 0) for item in staged)
        count = len(staged)

        display_files = staged
        if count > 0:
            self.tx_count_lbl.configure(text=f"{count} staged ({format_size(total_size)})")
        else:
            self.tx_count_lbl.configure(text="0 files staged")

        # Apply search query if present
        if self.search_shared_query:
            display_files = [f for f in display_files if self.search_shared_query in f.get("name", "").lower()]

        for widget in self.shared_scroll.winfo_children():
            widget.destroy()

        if not display_files:
            empty_lbl = ctk.CTkLabel(
                self.shared_scroll,
                text="No files staged to share yet.\nDrag & drop files or click 'Select Files' to choose what to share.",
                font=ctk.CTkFont(size=11),
                text_color=self.colors["text_sub"],
                justify="center"
            )
            empty_lbl.pack(pady=20)
            return

        for f in display_files:
            fn = f.get("name", "Unknown")
            sz = f.get("size", 0)
            fp = f.get("path")
            self._render_shared_row(fn, sz, fp, is_staged=True)

    def _render_shared_row(self, fn, sz, fp, is_staged):
        row = ctk.CTkFrame(
            self.shared_scroll,
            fg_color=self.colors["row_bg"],
            border_width=1,
            border_color=self.colors["row_border"],
            corner_radius=10
        )
        row.pack(fill="x", pady=2, padx=2)

        icon = get_file_icon(fn)
        ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=15), width=28).pack(side="left", padx=(8, 4), pady=5)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkLabel(info, text=fn, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.colors["text_main"], anchor="w").pack(fill="x")
        path_hint = truncate_path(fp, max_len=36) if fp else ""
        sub_text = f"{format_size(sz)} • {path_hint}" if path_hint else format_size(sz)
        ctk.CTkLabel(info, text=sub_text, font=ctk.CTkFont(size=10), text_color=self.colors["text_sub"], anchor="w").pack(fill="x")

        # Action Buttons (Matching Web UI Action Circle Icons: 3 circles)
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right", padx=6, pady=4)

        if fp and os.path.exists(fp):
            ctk.CTkButton(
                btns,
                text="👁️",
                width=28,
                height=28,
                corner_radius=14,
                font=ctk.CTkFont(size=11),
                fg_color=self.colors["btn_pill_bg"],
                border_width=1,
                border_color=self.colors["btn_pill_border"],
                hover_color=self.colors["btn_pill_hover"],
                command=lambda path=fp: os.startfile(path)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                btns,
                text="📂",
                width=28,
                height=28,
                corner_radius=14,
                font=ctk.CTkFont(size=11),
                fg_color=self.colors["btn_pill_bg"],
                border_width=1,
                border_color=self.colors["btn_pill_border"],
                hover_color=self.colors["btn_pill_hover"],
                command=lambda path=fp: os.system(f'explorer /select,"{os.path.abspath(path)}"')
            ).pack(side="left", padx=2)

        if is_staged:
            ctk.CTkButton(
                btns,
                text="✕",
                width=28,
                height=28,
                corner_radius=14,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=self.colors["btn_pill_bg"],
                border_width=1,
                border_color=self.colors["btn_pill_border"],
                text_color=self.colors["accent_red"],
                hover_color=self.colors["btn_pill_hover"],
                command=lambda filename=fn: self.unstage_host_file(filename)
            ).pack(side="left", padx=2)
        else:
            ctk.CTkButton(
                btns,
                text="🗑️",
                width=28,
                height=28,
                corner_radius=14,
                font=ctk.CTkFont(size=11),
                fg_color=self.colors["btn_pill_bg"],
                border_width=1,
                border_color=self.colors["btn_pill_border"],
                text_color=self.colors["accent_red"],
                hover_color=self.colors["btn_pill_hover"],
                command=lambda path=fp: self.delete_shared_file(path)
            ).pack(side="left", padx=2)

    def delete_shared_file(self, path):
        if messagebox.askyesno("Confirm Delete", f"Remove this file from disk?\n{os.path.basename(path)}"):
            try:
                os.remove(path)
                self.refresh_host_shared_files_list()
                self.add_log_entry(f"Deleted file: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not remove file:\n{e}")

    # --- REFRESH RECEIVED FILES LIST ---
    def refresh_host_received_files_list(self):
        if not os.path.exists(main.UPLOAD_DIR):
            return
        files = []
        try:
            for fn in os.listdir(main.UPLOAD_DIR):
                if fn.endswith('.part') or fn.endswith('.tmp'):
                    continue
                fp = os.path.join(main.UPLOAD_DIR, fn)
                if os.path.isfile(fp):
                    files.append((fn, os.path.getsize(fp), fp))
        except Exception:
            return

        self.rx_count_lbl.configure(text=f"{len(files)} files")

        if self.search_received_query:
            files = [f for f in files if self.search_received_query in f[0].lower()]

        for widget in self.received_scroll.winfo_children():
            widget.destroy()

        if not files:
            ctk.CTkLabel(
                self.received_scroll,
                text="No client uploads yet",
                font=ctk.CTkFont(size=11),
                text_color=self.colors["text_sub"]
            ).pack(pady=16)
            return

        for fn, sz, fp in files:
            self._render_received_row(fn, sz, fp)

    def _render_received_row(self, fn, sz, fp):
        row = ctk.CTkFrame(
            self.received_scroll,
            fg_color=self.colors["row_bg"],
            border_width=1,
            border_color=self.colors["row_border"],
            corner_radius=10
        )
        row.pack(fill="x", pady=2, padx=2)

        icon = get_file_icon(fn)
        ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=15), width=28).pack(side="left", padx=(8, 4), pady=5)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkLabel(info, text=fn, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.colors["text_main"], anchor="w").pack(fill="x")
        ctk.CTkLabel(info, text=format_size(sz), font=ctk.CTkFont(size=10), text_color=self.colors["text_sub"], anchor="w").pack(fill="x")

        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right", padx=6, pady=4)

        ctk.CTkButton(
            btns,
            text="👁️",
            width=28,
            height=28,
            corner_radius=14,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda path=fp: os.startfile(path)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btns,
            text="📂",
            width=28,
            height=28,
            corner_radius=14,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda path=fp: os.system(f'explorer /select,"{os.path.abspath(path)}"')
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btns,
            text="🗑️",
            width=28,
            height=28,
            corner_radius=14,
            font=ctk.CTkFont(size=11),
            fg_color=self.colors["btn_pill_bg"],
            border_width=1,
            border_color=self.colors["btn_pill_border"],
            text_color=self.colors["accent_red"],
            hover_color=self.colors["btn_pill_hover"],
            command=lambda path=fp: self.delete_received_file(path)
        ).pack(side="left", padx=2)

    def delete_received_file(self, path):
        if messagebox.askyesno("Confirm Delete", f"Delete this received file from disk?\n{os.path.basename(path)}"):
            try:
                os.remove(path)
                self.refresh_host_received_files_list()
                self.add_log_entry(f"Deleted received file: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete file:\n{e}")

    def refresh_client_ui(self):
        if self.client_connected:
            self.fetch_client_host_files()

    def on_close(self):
        try:
            main.stop_tunnel()
            if main.zc:
                try:
                    main.zc.unregister_all_services()
                    main.zc.close()
                except Exception: pass
            if main.httpd:
                try:
                    main.httpd.shutdown()
                    main.httpd.server_close()
                except Exception: pass
        except Exception:
            pass
        self.destroy()
        sys.exit(0)


def start_native_app():
    app = PyShareApp()
    app.mainloop()

if __name__ == "__main__":
    start_native_app()
