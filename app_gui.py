"""
==========================================================================
PyShare v4.8.0 - Native Desktop Application GUI
Standalone Cross-Platform GUI • Host & Client Dual-Mode • Zero Browser
==========================================================================
"""

import os
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

import main

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

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class PyShareApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Appearance & Configuration
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("PyShare — Local & P2P File Transfer")
        self.geometry("1100x720")
        self.minsize(920, 600)

        # Set Window Icon
        icon_path = resource_path("app_icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # State Variables
        self.current_mode = "host"  # "host" or "client"
        self.client_session = requests.Session()
        self.client_connected = False
        self.client_host_url = ""
        self.client_files = []
        self.client_selected_upload_files = []
        self.is_client_uploading = False
        self.is_client_downloading = False

        # Host State Cache
        self.cached_qr_path = resource_path("qrcode.png")
        self.qr_ctk_image = None
        self.last_qr_timestamp = 0

        # Build GUI Layout
        self.build_top_navbar()
        self.build_content_container()

        # Initialize Host Server in Background
        self.start_host_server()

        # Start Periodic GUI Refresh Ticker
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(500, self.refresh_ticker)

    # =========================================================================
    # 1. TOP NAVBAR
    # =========================================================================
    def build_top_navbar(self):
        self.navbar = ctk.CTkFrame(self, height=58, corner_radius=0, fg_color=("#182234", "#0f172a"))
        self.navbar.pack(side="top", fill="x")

        # Brand Logo & Title
        logo_frame = ctk.CTkFrame(self.navbar, fg_color="transparent")
        logo_frame.pack(side="left", padx=16, pady=10)

        logo_img_path = resource_path("app_icon.png")
        if os.path.isfile(logo_img_path):
            try:
                pil_logo = Image.open(logo_img_path).resize((30, 30))
                ctk_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(30, 30))
                logo_lbl = ctk.CTkLabel(logo_frame, image=ctk_logo, text="")
                logo_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        brand_lbl = ctk.CTkLabel(
            logo_frame,
            text="PyShare",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("#0284c7", "#00f0ff")
        )
        brand_lbl.pack(side="left")

        version_pill = ctk.CTkLabel(
            logo_frame,
            text="v4.8.0",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8",
            fg_color=("#1e293b", "#1e293b"),
            corner_radius=8,
            padx=8,
            pady=2
        )
        version_pill.pack(side="left", padx=8)

        # Center Mode Switcher (Host Server vs Connect as Client)
        self.mode_switcher = ctk.CTkSegmentedButton(
            self.navbar,
            values=["📡 Host Mode", "📱 Client Mode"],
            command=self.on_mode_change,
            font=ctk.CTkFont(size=13, weight="bold"),
            selected_color="#0284c7",
            selected_hover_color="#0369a1",
            height=34
        )
        self.mode_switcher.set("📡 Host Mode")
        self.mode_switcher.pack(side="left", expand=True)

        # Right Action Buttons
        actions_frame = ctk.CTkFrame(self.navbar, fg_color="transparent")
        actions_frame.pack(side="right", padx=16)

        # Storage Folder Button
        self.storage_btn = ctk.CTkButton(
            actions_frame,
            text="📂 Storage Folder",
            width=110,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#334155", "#1e293b"),
            hover_color=("#475569", "#334155"),
            command=self.open_base_storage_dir
        )
        self.storage_btn.pack(side="left", padx=6)

        # Dark/Light Theme Toggle
        self.theme_btn = ctk.CTkButton(
            actions_frame,
            text="🌓",
            width=36,
            height=32,
            font=ctk.CTkFont(size=14),
            fg_color=("#334155", "#1e293b"),
            hover_color=("#475569", "#334155"),
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=4)

    # =========================================================================
    # 2. CONTENT CONTAINER (SWITCHES BETWEEN HOST & CLIENT FRAMES)
    # =========================================================================
    def build_content_container(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=14, pady=14)

        # Host View Frame
        self.host_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.build_host_view()

        # Client View Frame
        self.client_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.build_client_view()

        # Default Show Host
        self.host_frame.pack(fill="both", expand=True)

    def on_mode_change(self, selected_mode):
        if "Host" in selected_mode:
            self.current_mode = "host"
            self.client_frame.pack_forget()
            self.host_frame.pack(fill="both", expand=True)
            self.refresh_host_ui()
        else:
            self.current_mode = "client"
            self.host_frame.pack_forget()
            self.client_frame.pack(fill="both", expand=True)
            self.refresh_client_ui()

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_theme = "light" if current.lower() == "dark" else "dark"
        ctk.set_appearance_mode(new_theme)

    # =========================================================================
    # 3. HOST MODE VIEW (SERVER CONTROLS, PIN, QR CODE, SHARED/RECEIVED FILES)
    # =========================================================================
    def build_host_view(self):
        # 2-Column Studio Grid Layout
        self.host_left_col = ctk.CTkFrame(self.host_frame, width=340, corner_radius=14, fg_color=("#182234", "#0f172a"))
        self.host_left_col.pack(side="left", fill="y", padx=(0, 10))
        self.host_left_col.pack_propagate(False)

        self.host_right_col = ctk.CTkFrame(self.host_frame, corner_radius=14, fg_color=("#182234", "#0f172a"))
        self.host_right_col.pack(side="right", fill="both", expand=True)

        # --- LEFT PANEL: Status, PIN, QR Code, Tunnel, Folders ---
        left_scroll = ctk.CTkScrollableFrame(self.host_left_col, fg_color="transparent")
        left_scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # Server Live Status Card
        status_card = ctk.CTkFrame(left_scroll, corner_radius=10, fg_color=("#1e293b", "#1e293b"))
        status_card.pack(fill="x", pady=6, padx=4)

        status_top = ctk.CTkFrame(status_card, fg_color="transparent")
        status_top.pack(fill="x", padx=10, pady=(8, 2))
        
        self.host_status_dot = ctk.CTkLabel(status_top, text="●", text_color="#10b981", font=ctk.CTkFont(size=14))
        self.host_status_dot.pack(side="left")
        self.host_status_text = ctk.CTkLabel(status_top, text="Server Active", font=ctk.CTkFont(size=13, weight="bold"))
        self.host_status_text.pack(side="left", padx=6)

        self.host_url_lbl = ctk.CTkLabel(
            status_card,
            text=f"http://{main.get_ip()}:{main.ACTUAL_PORT}",
            font=ctk.CTkFont(family="monospace", size=12, weight="bold"),
            text_color=("#0284c7", "#38bdf8")
        )
        self.host_url_lbl.pack(fill="x", padx=10, pady=(0, 6))

        btn_copy_url = ctk.CTkButton(
            status_card,
            text="📋 Copy Local IP Link",
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.copy_host_url
        )
        btn_copy_url.pack(fill="x", padx=10, pady=(0, 8))

        # Room PIN Card
        pin_card = ctk.CTkFrame(left_scroll, corner_radius=10, fg_color=("#1e293b", "#1e293b"))
        pin_card.pack(fill="x", pady=6, padx=4)

        ctk.CTkLabel(pin_card, text="ROOM PIN", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(pady=(8, 0))

        self.host_pin_display = ctk.CTkLabel(
            pin_card,
            text="----",
            font=ctk.CTkFont(family="monospace", size=32, weight="bold"),
            text_color=("#0284c7", "#00f0ff")
        )
        self.host_pin_display.pack(pady=2)

        self.host_pin_timer = ctk.CTkLabel(pin_card, text="⏱️ Rotates in 30s", font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.host_pin_timer.pack(pady=(0, 6))

        pin_btns_row = ctk.CTkFrame(pin_card, fg_color="transparent")
        pin_btns_row.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkButton(
            pin_btns_row,
            text="🔄 Rotate PIN",
            width=110,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.force_rotate_host_pin
        ).pack(side="left", expand=True, padx=2)

        ctk.CTkButton(
            pin_btns_row,
            text="📋 Copy PIN",
            width=110,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.copy_host_pin
        ).pack(side="right", expand=True, padx=2)

        # QR Code Card
        qr_card = ctk.CTkFrame(left_scroll, corner_radius=10, fg_color=("#1e293b", "#1e293b"))
        qr_card.pack(fill="x", pady=6, padx=4)

        ctk.CTkLabel(qr_card, text="SCAN WITH PHONE TO CONNECT", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(pady=(8, 6))

        self.qr_wrapper = ctk.CTkLabel(qr_card, text="[QR Code Loading...]")
        self.qr_wrapper.pack(pady=4)

        # Cloudflare Tunnel Toggle Card
        tunnel_card = ctk.CTkFrame(left_scroll, corner_radius=10, fg_color=("#1e293b", "#1e293b"))
        tunnel_card.pack(fill="x", pady=6, padx=4)

        tunnel_top = ctk.CTkFrame(tunnel_card, fg_color="transparent")
        tunnel_top.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(tunnel_top, text="☁️ Cloudflare Public Link", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.tunnel_switch = ctk.CTkSwitch(tunnel_top, text="", command=self.toggle_cloudflare_tunnel, width=40)
        self.tunnel_switch.pack(side="right")

        self.tunnel_url_lbl = ctk.CTkLabel(
            tunnel_card,
            text="Disabled (Offline LAN Mode)",
            font=ctk.CTkFont(family="monospace", size=10),
            text_color="#94a3b8"
        )
        self.tunnel_url_lbl.pack(fill="x", padx=10, pady=(0, 8))

        # Folder Quick Buttons
        folders_card = ctk.CTkFrame(left_scroll, corner_radius=10, fg_color=("#1e293b", "#1e293b"))
        folders_card.pack(fill="x", pady=6, padx=4)

        ctk.CTkButton(
            folders_card,
            text="📤 Open Shared Files Folder",
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: os.startfile(main.DOWNLOAD_DIR)
        ).pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkButton(
            folders_card,
            text="📥 Open Received Files Folder",
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: os.startfile(main.UPLOAD_DIR)
        ).pack(fill="x", padx=10, pady=(4, 8))

        # --- RIGHT PANEL: Tabview (Shared Files, Received Files, Shared Clipboard) ---
        self.host_tabs = ctk.CTkTabview(self.host_right_col, fg_color="transparent")
        self.host_tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_shared = self.host_tabs.add("📤 Shared Files")
        self.tab_received = self.host_tabs.add("📥 Received Files")
        self.tab_clipboard = self.host_tabs.add("📋 Shared Clipboard")

        self.build_host_shared_tab()
        self.build_host_received_tab()
        self.build_host_clipboard_tab()

    # --- HOST TAB 1: Shared Files ---
    def build_host_shared_tab(self):
        # Action Bar
        action_bar = ctk.CTkFrame(self.tab_shared, height=44, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            action_bar,
            text="➕ Add Files to Share",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.add_files_to_host_share
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_bar,
            text="📁 Add Folder",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#334155", "#1e293b"),
            hover_color=("#475569", "#334155"),
            command=self.add_folder_to_host_share
        ).pack(side="left", padx=4)

        self.shared_count_lbl = ctk.CTkLabel(action_bar, text="0 files shared", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.shared_count_lbl.pack(side="right", padx=8)

        # Scrollable list for shared files
        self.shared_files_scroll = ctk.CTkScrollableFrame(self.tab_shared, fg_color=("#1e293b", "#090d16"), corner_radius=10)
        self.shared_files_scroll.pack(fill="both", expand=True)

    # --- HOST TAB 2: Received Files ---
    def build_host_received_tab(self):
        action_bar = ctk.CTkFrame(self.tab_received, height=44, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            action_bar,
            text="📂 Open Received Folder",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: os.startfile(main.UPLOAD_DIR)
        ).pack(side="left", padx=(0, 8))

        self.received_count_lbl = ctk.CTkLabel(action_bar, text="0 files received", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.received_count_lbl.pack(side="right", padx=8)

        self.received_files_scroll = ctk.CTkScrollableFrame(self.tab_received, fg_color=("#1e293b", "#090d16"), corner_radius=10)
        self.received_files_scroll.pack(fill="both", expand=True)

    # --- HOST TAB 3: Shared Clipboard ---
    def build_host_clipboard_tab(self):
        desc = ctk.CTkLabel(
            self.tab_clipboard,
            text="Universal clipboard synchronizes instantly across Host PC and connected peer devices.",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        desc.pack(anchor="w", pady=(0, 8))

        self.host_clipboard_textbox = ctk.CTkTextbox(self.tab_clipboard, height=180, font=ctk.CTkFont(size=13))
        self.host_clipboard_textbox.pack(fill="x", pady=4)

        btn_row = ctk.CTkFrame(self.tab_clipboard, fg_color="transparent")
        btn_row.pack(fill="x", pady=10)

        ctk.CTkButton(
            btn_row,
            text="🚀 Broadcast Text to Peers",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.broadcast_host_clipboard
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="📋 Copy Current Clipboard",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#334155", "#1e293b"),
            hover_color=("#475569", "#334155"),
            command=self.copy_current_host_clipboard
        ).pack(side="left")

    # =========================================================================
    # 4. CLIENT MODE VIEW (CONNECT TO ANY HOST, DOWNLOAD & UPLOAD FILES)
    # =========================================================================
    def build_client_view(self):
        # Header Connection Card
        conn_card = ctk.CTkFrame(self.client_frame, corner_radius=14, fg_color=("#182234", "#0f172a"))
        conn_card.pack(fill="x", pady=(0, 10))

        title_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            title_row,
            text="Connect to a PyShare Host (Phone, PC, or Mac)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#0284c7", "#38bdf8")
        ).pack(side="left")

        self.client_status_pill = ctk.CTkLabel(
            title_row,
            text="⚪ Not Connected",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#94a3b8",
            fg_color=("#1e293b", "#1e293b"),
            corner_radius=10,
            padx=10,
            pady=4
        )
        self.client_status_pill.pack(side="right")

        # Inputs Row (Host IP, PIN, Connect Button, Auto-Discover Button)
        inputs_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        inputs_row.pack(fill="x", padx=16, pady=(4, 14))

        ctk.CTkLabel(inputs_row, text="Host Address:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.client_host_entry = ctk.CTkEntry(inputs_row, placeholder_text="192.168.1.5:8010", width=180, font=ctk.CTkFont(size=12))
        self.client_host_entry.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(inputs_row, text="Room PIN:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.client_pin_entry = ctk.CTkEntry(inputs_row, placeholder_text="4-digit PIN", width=95, font=ctk.CTkFont(size=12))
        self.client_pin_entry.pack(side="left", padx=(0, 12))

        self.client_connect_btn = ctk.CTkButton(
            inputs_row,
            text="⚡ Connect",
            width=100,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_client_connection
        )
        self.client_connect_btn.pack(side="left", padx=(0, 8))

        self.client_discover_btn = ctk.CTkButton(
            inputs_row,
            text="🔍 Auto-Discover",
            width=120,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#334155", "#1e293b"),
            hover_color=("#475569", "#334155"),
            command=self.auto_discover_hosts_network
        )
        self.client_discover_btn.pack(side="left")

        # Body: 2-Column Split (Left: Download Host's Files, Right: Send Files to Host & Clipboard)
        client_body = ctk.CTkFrame(self.client_frame, fg_color="transparent")
        client_body.pack(fill="both", expand=True)

        self.client_download_col = ctk.CTkFrame(client_body, corner_radius=14, fg_color=("#182234", "#0f172a"))
        self.client_download_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.client_upload_col = ctk.CTkFrame(client_body, width=420, corner_radius=14, fg_color=("#182234", "#0f172a"))
        self.client_upload_col.pack(side="right", fill="both")
        self.client_upload_col.pack_propagate(False)

        # --- LEFT: Available Files on Host ---
        dl_header = ctk.CTkFrame(self.client_download_col, fg_color="transparent")
        dl_header.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(dl_header, text="📂 Files Shared by Host", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        self.client_dl_all_btn = ctk.CTkButton(
            dl_header,
            text="📦 Download All (ZIP)",
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#334155", "#1e293b"),
            hover_color=("#475569", "#334155"),
            command=self.client_download_all_zip,
            state="disabled"
        )
        self.client_dl_all_btn.pack(side="right", padx=4)

        self.client_refresh_btn = ctk.CTkButton(
            dl_header,
            text="🔄 Refresh",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.fetch_client_host_files,
            state="disabled"
        )
        self.client_refresh_btn.pack(side="right", padx=4)

        self.client_files_scroll = ctk.CTkScrollableFrame(self.client_download_col, fg_color=("#1e293b", "#090d16"), corner_radius=10)
        self.client_files_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # --- RIGHT: Send Files to Host & Host Clipboard ---
        ul_header = ctk.CTkFrame(self.client_upload_col, fg_color="transparent")
        ul_header.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(ul_header, text="📤 Send Files to Host", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        self.client_select_files_btn = ctk.CTkButton(
            self.client_upload_col,
            text="➕ Select Files to Upload...",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.client_select_files_for_upload,
            state="disabled"
        )
        self.client_select_files_btn.pack(fill="x", padx=14, pady=4)

        self.client_upload_queue_box = ctk.CTkTextbox(self.client_upload_col, height=130, font=ctk.CTkFont(size=12))
        self.client_upload_queue_box.pack(fill="x", padx=14, pady=4)
        self.client_upload_queue_box.insert("1.0", "No files queued for upload.")
        self.client_upload_queue_box.configure(state="disabled")

        self.client_send_btn = ctk.CTkButton(
            self.client_upload_col,
            text="🚀 Upload Queued Files to Host",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=self.client_execute_upload,
            state="disabled"
        )
        self.client_send_btn.pack(fill="x", padx=14, pady=4)

        # Client Progress Bar
        self.client_progress_bar = ctk.CTkProgressBar(self.client_upload_col, height=8)
        self.client_progress_bar.pack(fill="x", padx=14, pady=(8, 2))
        self.client_progress_bar.set(0)

        self.client_progress_lbl = ctk.CTkLabel(self.client_upload_col, text="Ready", font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.client_progress_lbl.pack(padx=14, pady=(0, 10))

        # Host Clipboard Sync Card
        clip_card = ctk.CTkFrame(self.client_upload_col, corner_radius=10, fg_color=("#1e293b", "#1e293b"))
        clip_card.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        ctk.CTkLabel(clip_card, text="📋 Host Clipboard", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))

        self.client_clipboard_entry = ctk.CTkEntry(clip_card, placeholder_text="Send text to host clipboard...", font=ctk.CTkFont(size=11))
        self.client_clipboard_entry.pack(fill="x", padx=10, pady=4)

        clip_btn_row = ctk.CTkFrame(clip_card, fg_color="transparent")
        clip_btn_row.pack(fill="x", padx=10, pady=(0, 8))

        self.client_clip_send_btn = ctk.CTkButton(
            clip_btn_row,
            text="Send Text",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.client_send_clipboard_to_host,
            state="disabled"
        )
        self.client_clip_send_btn.pack(side="left", padx=(0, 4))

        self.client_clip_copy_btn = ctk.CTkButton(
            clip_btn_row,
            text="Copy Host Text",
            width=110,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#334155", "#334155"),
            hover_color=("#475569", "#475569"),
            command=self.client_copy_host_clipboard,
            state="disabled"
        )
        self.client_clip_copy_btn.pack(side="left")

    # =========================================================================
    # 5. HOST SERVER ENGINE & CONTROLS
    # =========================================================================
    def start_host_server(self):
        def _run():
            try:
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                main.BASE_DIR = os.path.join(desktop, "PyShare_Files")
                main.UPLOAD_DIR = os.path.join(main.BASE_DIR, "Received_Files")
                main.DOWNLOAD_DIR = os.path.join(main.BASE_DIR, "Shared_Files")
                os.makedirs(main.UPLOAD_DIR, exist_ok=True)
                os.makedirs(main.DOWNLOAD_DIR, exist_ok=True)

                # Bind Port
                main.socketserver.TCPServer.allow_reuse_address = True
                for port in range(main.START_PORT, main.START_PORT + 10):
                    try:
                        server = main.socketserver.ThreadingTCPServer(("", port), main.FinalFileHandler)
                        main.ACTUAL_PORT = port
                        main.httpd = server
                        break
                    except OSError:
                        continue

                # Start PIN rotation ticker
                main.start_pin_rotator()

                ip = main.get_ip()
                url = f"http://{ip}:{main.ACTUAL_PORT}"
                main.generate_qr(url)

                # mDNS Service Broadcast
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

                # Start Server loop on daemon thread
                main.httpd.serve_forever()
            except Exception as e:
                print(f"[!] Server Startup Error: {e}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def force_rotate_host_pin(self):
        main.current_pin = str(main.random.randint(1000, 9999))
        main.pin_time_remaining = 30
        self.host_pin_display.configure(text=f"{main.current_pin[0]} {main.current_pin[1]} {main.current_pin[2]} {main.current_pin[3]}")
        self.update_qr_image()

    def copy_host_url(self):
        url = f"http://{main.get_ip()}:{main.ACTUAL_PORT}"
        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo("Copied", f"Host URL copied to clipboard:\n{url}")

    def copy_host_pin(self):
        self.clipboard_clear()
        self.clipboard_append(main.current_pin)
        messagebox.showinfo("Copied", f"PIN copied to clipboard:\n{main.current_pin}")

    def toggle_cloudflare_tunnel(self):
        if self.tunnel_switch.get():
            self.tunnel_url_lbl.configure(text="Starting tunnel...", text_color="#f59e0b")
            main.start_tunnel_async()
        else:
            main.stop_tunnel()
            self.tunnel_url_lbl.configure(text="Disabled (Offline LAN Mode)", text_color="#94a3b8")

    def open_base_storage_dir(self):
        if os.path.exists(main.BASE_DIR):
            os.startfile(main.BASE_DIR)

    def add_files_to_host_share(self):
        paths = filedialog.askopenfilenames(title="Select Files to Share with Peers")
        if not paths:
            return
        for p in paths:
            try:
                dest = os.path.join(main.DOWNLOAD_DIR, os.path.basename(p))
                if os.path.abspath(p) != os.path.abspath(dest):
                    shutil.copy2(p, dest)
            except Exception as e:
                messagebox.showerror("Error", f"Could not copy file:\n{e}")
        self.refresh_host_shared_files_list()

    def add_folder_to_host_share(self):
        folder = filedialog.askdirectory(title="Select Folder to Share with Peers")
        if not folder:
            return
        try:
            dest = os.path.join(main.DOWNLOAD_DIR, os.path.basename(folder))
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(folder, dest)
            self.refresh_host_shared_files_list()
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy folder:\n{e}")

    def broadcast_host_clipboard(self):
        text = self.host_clipboard_textbox.get("1.0", "end-1c").strip()
        if text:
            main.clipboard_data = text
            main.broadcast_sse("clipboard", text)
            messagebox.showinfo("Broadcast", "Clipboard broadcasted to all connected peers!")

    def copy_current_host_clipboard(self):
        text = main.clipboard_data or ""
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Current clipboard copied to your system clipboard!")

    # =========================================================================
    # 6. CLIENT MODE ENGINE (CONNECT, UPLOAD, DOWNLOAD, DISCOVER)
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
        self.client_status_pill.configure(text=f"🟢 Connected ({base_url.replace('http://', '')})", text_color="#10b981")
        self.client_connect_btn.configure(text="Disconnect", state="normal", fg_color="#ef4444", hover_color="#dc2626")
        self.client_host_entry.configure(state="disabled")
        self.client_pin_entry.configure(state="disabled")

        # Enable client action buttons
        self.client_refresh_btn.configure(state="normal")
        self.client_dl_all_btn.configure(state="normal")
        self.client_select_files_btn.configure(state="normal")
        self.client_send_btn.configure(state="normal")
        self.client_clip_send_btn.configure(state="normal")
        self.client_clip_copy_btn.configure(state="normal")

        # Fetch files from host
        self.fetch_client_host_files()
        self.fetch_client_host_clipboard()

    def on_client_connect_error(self, err_msg):
        self.client_status_pill.configure(text="⚪ Disconnected", text_color="#94a3b8")
        self.client_connect_btn.configure(state="normal")
        messagebox.showerror("Connection Failed", err_msg)

    def disconnect_client(self):
        self.client_connected = False
        self.client_host_url = ""
        self.client_session = requests.Session()
        self.client_status_pill.configure(text="⚪ Not Connected", text_color="#94a3b8")
        self.client_connect_btn.configure(text="⚡ Connect", state="normal", fg_color="#0284c7", hover_color="#0369a1")
        self.client_host_entry.configure(state="normal")
        self.client_pin_entry.configure(state="normal")

        # Disable client buttons
        self.client_refresh_btn.configure(state="disabled")
        self.client_dl_all_btn.configure(state="disabled")
        self.client_select_files_btn.configure(state="disabled")
        self.client_send_btn.configure(state="disabled")
        self.client_clip_send_btn.configure(state="disabled")
        self.client_clip_copy_btn.configure(state="disabled")

        # Clear file scroll
        for widget in self.client_files_scroll.winfo_children():
            widget.destroy()

    def auto_discover_hosts_network(self):
        self.client_status_pill.configure(text="🔍 Scanning Wi-Fi...", text_color="#38bdf8")
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
        self.client_status_pill.configure(text="⚪ Not Connected" if not self.client_connected else "🟢 Connected", text_color="#94a3b8" if not self.client_connected else "#10b981")
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
                    files = r.json()
                    self.after(0, lambda: self.render_client_host_files_list(files))
            except Exception as e:
                print(f"Error fetching host files: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    def render_client_host_files_list(self, files):
        self.client_files = files or []
        for widget in self.client_files_scroll.winfo_children():
            widget.destroy()

        if not files:
            ctk.CTkLabel(
                self.client_files_scroll,
                text="Host has not shared any files yet.",
                font=ctk.CTkFont(size=12),
                text_color="#94a3b8"
            ).pack(pady=20)
            return

        for f in files:
            fn = f.get("name", "Unknown")
            sz = f.get("size", 0)
            icon = get_file_icon(fn)

            row = ctk.CTkFrame(self.client_files_scroll, fg_color=("#182234", "#111827"), corner_radius=8)
            row.pack(fill="x", pady=3, padx=4)

            icon_lbl = ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=16), width=32)
            icon_lbl.pack(side="left", padx=(8, 4), pady=6)

            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="x", expand=True, padx=4)

            name_lbl = ctk.CTkLabel(info_col, text=fn, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
            name_lbl.pack(fill="x")

            size_lbl = ctk.CTkLabel(info_col, text=format_size(sz), font=ctk.CTkFont(size=10), text_color="#94a3b8", anchor="w")
            size_lbl.pack(fill="x")

            dl_btn = ctk.CTkButton(
                row,
                text="⬇️ Download",
                width=90,
                height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda filename=fn: self.client_download_file(filename)
            )
            dl_btn.pack(side="right", padx=8, pady=6)

    def client_download_file(self, filename):
        if not self.client_connected or self.is_client_downloading:
            return

        dest_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        dest_path = os.path.join(dest_dir, filename)

        self.is_client_downloading = True
        self.client_progress_lbl.configure(text=f"Downloading {filename}...")

        def _worker():
            try:
                url = f"{self.client_host_url}/download/{filename}"
                with self.client_session.get(url, stream=True, timeout=15) as r:
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
        self.client_progress_lbl.configure(text=f"Saved to Downloads: {filename}")
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
        dest_path = os.path.join(os.path.expanduser("~"), "Downloads", f"PyShare_Files_{int(time.time())}.zip")
        self.is_client_downloading = True
        self.client_progress_lbl.configure(text="Downloading ZIP archive...")

        def _worker():
            try:
                url = f"{self.client_host_url}/download-all"
                with self.client_session.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    with open(dest_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=128 * 1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    self.after(0, lambda p=(downloaded/total): self.client_progress_bar.set(p))
                self.after(0, lambda: self.on_client_download_success("PyShare_Archive.zip", dest_path))
            except Exception as e:
                self.after(0, lambda: self.on_client_download_error("Archive.zip", str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def client_select_files_for_upload(self):
        paths = filedialog.askopenfilenames(title="Select Files to Upload to Host")
        if not paths:
            return
        self.client_selected_upload_files = list(paths)
        self.client_upload_queue_box.configure(state="normal")
        self.client_upload_queue_box.delete("1.0", "end")
        for p in self.client_selected_upload_files:
            sz = os.path.getsize(p) if os.path.isfile(p) else 0
            self.client_upload_queue_box.insert("end", f"• {os.path.basename(p)} ({format_size(sz)})\n")
        self.client_upload_queue_box.configure(state="disabled")

    def client_execute_upload(self):
        if not self.client_connected or not self.client_selected_upload_files:
            messagebox.showwarning("No Files", "Please select files to upload first.")
            return
        if self.is_client_uploading:
            return

        self.is_client_uploading = True
        files_to_send = list(self.client_selected_upload_files)

        def _worker():
            total_files = len(files_to_send)
            for idx, p in enumerate(files_to_send):
                fn = os.path.basename(p)
                self.after(0, lambda i=idx+1, name=fn: self.client_progress_lbl.configure(text=f"Uploading {i}/{total_files}: {name}..."))
                try:
                    url = f"{self.client_host_url}/upload"
                    with open(p, 'rb') as f:
                        files = {'files': (fn, f)}
                        resp = self.client_session.post(url, files=files, timeout=30)
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
    # 7. REAL-TIME REFRESH TICKER & LIST UPDATERS
    # =========================================================================
    def refresh_ticker(self):
        try:
            if self.current_mode == "host":
                self.refresh_host_ui()
            elif self.current_mode == "client" and self.client_connected:
                # Periodic poll of host files & clipboard every 4 ticks
                pass
        except Exception:
            pass
        self.after(1000, self.refresh_ticker)

    def refresh_host_ui(self):
        # Update PIN display & Timer
        pin = main.current_pin or "----"
        if len(pin) == 4:
            self.host_pin_display.configure(text=f"{pin[0]}  {pin[1]}  {pin[2]}  {pin[3]}")
        else:
            self.host_pin_display.configure(text=pin)

        rem = max(0, getattr(main, 'pin_time_remaining', 30))
        self.host_pin_timer.configure(text=f"⏱️ Rotates in {rem}s")

        # Update Local IP Label
        ip = main.get_ip()
        self.host_url_lbl.configure(text=f"http://{ip}:{main.ACTUAL_PORT}")

        # Update Tunnel Status
        tunnel_url = getattr(main, 'active_tunnel_url', None)
        if tunnel_url:
            self.tunnel_url_lbl.configure(text=tunnel_url, text_color="#10b981")
            if not self.tunnel_switch.get():
                self.tunnel_switch.select()
        else:
            if self.tunnel_switch.get() and not getattr(main, 'tunnel_proc', None):
                self.tunnel_url_lbl.configure(text="Connecting tunnel...", text_color="#f59e0b")
            else:
                self.tunnel_url_lbl.configure(text="Disabled (Offline LAN Mode)", text_color="#94a3b8")

        # Update QR image if needed
        self.update_qr_image()

        # Update File Lists
        self.refresh_host_shared_files_list()
        self.refresh_host_received_files_list()

    def update_qr_image(self):
        qr_file = resource_path("qrcode.png")
        if os.path.isfile(qr_file):
            mtime = os.path.getmtime(qr_file)
            if mtime > self.last_qr_timestamp:
                self.last_qr_timestamp = mtime
                try:
                    pil_img = Image.open(qr_file).resize((150, 150))
                    self.qr_ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(150, 150))
                    self.qr_wrapper.configure(image=self.qr_ctk_image, text="")
                except Exception:
                    pass

    def refresh_host_shared_files_list(self):
        if not os.path.exists(main.DOWNLOAD_DIR):
            return
        files = []
        try:
            for fn in os.listdir(main.DOWNLOAD_DIR):
                fp = os.path.join(main.DOWNLOAD_DIR, fn)
                if os.path.isfile(fp):
                    files.append((fn, os.path.getsize(fp), fp))
        except Exception:
            return

        self.shared_count_lbl.configure(text=f"{len(files)} file{'s' if len(files) != 1 else ''} shared")

        # Clear existing
        for widget in self.shared_files_scroll.winfo_children():
            widget.destroy()

        if not files:
            ctk.CTkLabel(
                self.shared_files_scroll,
                text="No files shared yet. Click '+ Add Files to Share' above.",
                font=ctk.CTkFont(size=12),
                text_color="#94a3b8"
            ).pack(pady=20)
            return

        for fn, sz, fp in files:
            row = ctk.CTkFrame(self.shared_files_scroll, fg_color=("#182234", "#111827"), corner_radius=8)
            row.pack(fill="x", pady=3, padx=4)

            icon = get_file_icon(fn)
            ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=16), width=32).pack(side="left", padx=(8, 4), pady=6)

            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="x", expand=True, padx=4)

            ctk.CTkLabel(info_col, text=fn, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(info_col, text=format_size(sz), font=ctk.CTkFont(size=10), text_color="#94a3b8", anchor="w").pack(fill="x")

            btn_del = ctk.CTkButton(
                row,
                text="🗑️",
                width=32,
                height=26,
                fg_color=("#ef4444", "#dc2626"),
                hover_color="#b91c1c",
                command=lambda path=fp: self.delete_shared_file(path)
            )
            btn_del.pack(side="right", padx=(4, 8), pady=6)

            btn_open = ctk.CTkButton(
                row,
                text="👁️ Open",
                width=70,
                height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=("#334155", "#1e293b"),
                hover_color=("#475569", "#334155"),
                command=lambda path=fp: os.startfile(path)
            )
            btn_open.pack(side="right", padx=4, pady=6)

    def delete_shared_file(self, path):
        if messagebox.askyesno("Confirm Delete", f"Remove this file from shared list?\n{os.path.basename(path)}"):
            try:
                os.remove(path)
                self.refresh_host_shared_files_list()
            except Exception as e:
                messagebox.showerror("Error", f"Could not remove file:\n{e}")

    def refresh_host_received_files_list(self):
        if not os.path.exists(main.UPLOAD_DIR):
            return
        files = []
        try:
            for fn in os.listdir(main.UPLOAD_DIR):
                fp = os.path.join(main.UPLOAD_DIR, fn)
                if os.path.isfile(fp):
                    files.append((fn, os.path.getsize(fp), fp))
        except Exception:
            return

        self.received_count_lbl.configure(text=f"{len(files)} file{'s' if len(files) != 1 else ''} received")

        for widget in self.received_files_scroll.winfo_children():
            widget.destroy()

        if not files:
            ctk.CTkLabel(
                self.received_files_scroll,
                text="No files received yet. Files uploaded by peers will appear here automatically.",
                font=ctk.CTkFont(size=12),
                text_color="#94a3b8"
            ).pack(pady=20)
            return

        for fn, sz, fp in files:
            row = ctk.CTkFrame(self.received_files_scroll, fg_color=("#182234", "#111827"), corner_radius=8)
            row.pack(fill="x", pady=3, padx=4)

            icon = get_file_icon(fn)
            ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=16), width=32).pack(side="left", padx=(8, 4), pady=6)

            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="x", expand=True, padx=4)

            ctk.CTkLabel(info_col, text=fn, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(info_col, text=format_size(sz), font=ctk.CTkFont(size=10), text_color="#94a3b8", anchor="w").pack(fill="x")

            btn_open = ctk.CTkButton(
                row,
                text="👁️ Open",
                width=70,
                height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda path=fp: os.startfile(path)
            )
            btn_open.pack(side="right", padx=8, pady=6)

    def refresh_client_ui(self):
        if self.client_connected:
            self.fetch_client_host_files()

    def on_close(self):
        # Stop background host server and tunnel
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
