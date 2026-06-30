import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import os  # Added for file operations

# Added for the Graphing feature
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

BAUD_RATE   = 115200
FLASH_DELAY = 100
COL_SAFE      = "#22C55E"     # Modern green
COL_DANGER    = "#EF4444"     # Modern red
COL_FLASH_A   = "#DC2626"     # Flash red
COL_FLASH_B   = "#F59E0B"     # Amber warning
COL_IDLE      = "#6B7280"     # Neutral gray
COL_VAULT_DAY = "#2ecc71"
COL_BG        = "#0F172A"     # Main background
COL_PANEL     = "#1E293B"     # Panels
COL_BORDER    = "#334155"     # Borders
COL_TEXT      = "#F8FAFC"     # White text
COL_ACCENT    = "#C74242"     # Cashmere

# Day  = 09:00–17:00 (5:00 PM) → alert at VAULT
# Night= 17:01 (5:01 PM)–08:59 → alert at ENTRY
def mode_from_time(hour: int, minute: int) -> str:
    total_mins = hour * 60 + minute
    # 9:00 AM = 540 minutes, 17:00 (5:00 PM) = 1020 minutes
    return "day" if 540 <= total_mins <= 1020 else "night"

# ─────────────────────────────────────────────────────────────
#  SPINNER TIME PICKER  (▲ / ▼ arrows, HH : MM : SS, 24-hour)
# ─────────────────────────────────────────────────────────────
class SpinnerTimePicker(tk.Frame):
    """Compact inline spinner: Hour · Minute · Second (24-hour).
       .get() returns 'HH:MM:SS'."""
    def __init__(self, parent, default="09:00:00", on_change=None):
        super().__init__(parent, bg=COL_PANEL)
        self._cb = on_change
        # ── parse default ──
        parts = default.split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        self.vals   = {"h": h, "m": m, "s": s}
        self.ranges = {"h": (0, 23), "m": (0, 59), "s": (0, 59)}
        self.disps  = {}           # key → (Label widget, format_fn)
        # ── build columns ──
        self._add_spin("h", lambda v: f"{v:02d}", w=2)
        self._add_sep(":")
        self._add_spin("m", lambda v: f"{v:02d}", w=2)
        self._add_sep(":")
        self._add_spin("s", lambda v: f"{v:02d}", w=2)

    # ── one spinner column ──
    def _add_spin(self, key, fmt, w=2):
        col = tk.Frame(self, bg=COL_PANEL)
        col.pack(side=tk.LEFT, padx=1)
        up = tk.Label(col, text="▲", font=("Segoe UI", 7),
                      bg=COL_PANEL, fg="#2ecc71", cursor="hand2")
        up.pack()
        up.bind("<Button-1>", lambda _e, k=key: self._step(k, -1))
        val = tk.Label(col, text=fmt(self.vals[key]),
                       font=("Consolas", 10, "bold"),
                       bg="#0d1b2a", fg="#38BDF8", width=w,
                       anchor="center", relief=tk.FLAT, bd=1)
        val.pack(padx=1, pady=1)
        dn = tk.Label(col, text="▼", font=("Segoe UI", 7),
                      bg=COL_PANEL, fg="#2ecc71", cursor="hand2")
        dn.pack()
        dn.bind("<Button-1>", lambda _e, k=key: self._step(k, 1))
        self.disps[key] = (val, fmt)
        # mouse-wheel on any part of the column
        for widget in (up, val, dn, col):
            widget.bind("<MouseWheel>",
                        lambda e, k=key: self._step(k, -1 if e.delta > 0 else 1))

    def _add_sep(self, ch):
        tk.Label(self, text=ch, font=("Consolas", 10, "bold"),
                 bg=COL_PANEL, fg="#38BDF8").pack(side=tk.LEFT)

    # ── step value up / down with wrap ──
    def _step(self, key, direction):
        lo, hi = self.ranges[key]
        v = self.vals[key] + direction
        if   v > hi: v = lo
        elif v < lo: v = hi
        self.vals[key] = v
        lbl, fmt = self.disps[key]
        lbl.config(text=fmt(v))
        if self._cb:
            self._cb()

    # ── NEW: set time externally ──
    def set_time(self, h, m, s):
        self.vals['h'] = h
        self.vals['m'] = m
        self.vals['s'] = s
        for key in ('h', 'm', 's'):
            lbl, fmt = self.disps[key]
            lbl.config(text=fmt(self.vals[key]))
        if self._cb:
            self._cb()

    # ── public getter (24-hour HH:MM:SS) ──
    def get(self):
        return f"{self.vals['h']:02d}:{self.vals['m']:02d}:{self.vals['s']:02d}"

class BankSecurityGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bank Security System")
        self.root.geometry("1250x850")
        self.root.configure(bg=COL_BG)
        self.root.resizable(True, True)
        self.serial_port  = None
        self.is_connected = False
        self.detected     = False
        self.flash_state  = False
        self.flash_job    = None
        self.ripple_rings = []
        self.ripple_job   = None
        self.ripple_spawn_job = None
        self.alert_job    = None
        self.alert_state  = False
        self.current_mode = None   # "day" | "night" | None
        self.alert_zone   = "entry"
        self.last_known_sim_time = "09:00:00" # Added to track ticking UART time
        
        # Zone centroids for ripple (updated after canvas is drawn)
        self.zone_centers = {
            "entry": (750, 200),
            "vault": (122, 210),
        }
        self._build_ui()
        self._set_idle_colors()
        
        # Initialize default mode
        self._apply_mode_from_time(9, 0)

    # ─────────────────────────────────────────────────────────
    #  MODE ENGINE (driven by input time, not system clock)
    # ─────────────────────────────────────────────────────────
    def _apply_mode_from_time(self, hour: int, minute: int):
        new_mode = mode_from_time(hour, minute)
        self.current_mode = new_mode
        self.alert_zone   = "vault" if new_mode == "day" else "entry"
        if self.detected:
            return
            
        # Update colors based on the mode
        if new_mode == "day":
            self._set_day_colors()
            self.status_lbl.config(text="☀️ DAY MODE", fg="#f39c12")
            self.alert_lbl.config(text="")
            self.info_lbl.config(text="Vault & Cashier secured", fg="#f39c12")
        else:
            self._set_night_colors()
            self.status_lbl.config(text="🌙 NIGHT MODE", fg="#2ecc71")
            self.alert_lbl.config(text="")
            self.info_lbl.config(text="System ready", fg="#2ecc71")

    # Automatically trigger mode changes when the user scrolls the current-time picker
    def _on_time_entry_change(self, event=None):
        raw_text = self.e_current.get().replace(":", "").replace(" ", "").strip()
        
        # Update the base time whenever user manually adjusts the spinner
        self.last_known_sim_time = self.e_current.get()
        
        if len(raw_text) >= 4 and raw_text[:4].isdigit():
            try:
                hour = int(raw_text[:2])
                minute = int(raw_text[2:4])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    self._apply_mode_from_time(hour, minute)
            except ValueError:
                pass

    # ─────────────────────────────────────────────────────────
    #  ABOUT / INFO POPUP
    # ─────────────────────────────────────────────────────────
    def _show_about(self):
        """Show a styled 'About' popup with version, developer, and OS info."""
        popup = tk.Toplevel(self.root)
        popup.title("About")
        popup.configure(bg=COL_PANEL)
        popup.resizable(False, False)

        # Center the popup on the main window
        popup.update_idletasks()
        pw, ph = 350, 200
        x = self.root.winfo_x() + (self.root.winfo_width()  - pw) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - ph) // 2
        popup.geometry(f"{pw}x{ph}+{x}+{y}")

        # Header
        tk.Label(popup, text="ℹ️  Bank Security System",
                 font=("Segoe UI", 14, "bold"),
                 bg=COL_PANEL, fg=COL_TEXT).pack(pady=(16, 12))

        # Info lines
        info_frame = tk.Frame(popup, bg=COL_PANEL)
        info_frame.pack(fill=tk.X, padx=24)

        details = [
            ("Version:", "1.0"),
            ("Developers:", "Anirban Biswas, Riya Maheshwari"),
            ("OS:", "Windows_NT x64 10.0.26200"),
        ]
        for label, value in details:
            row = tk.Frame(info_frame, bg=COL_PANEL)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 10, "bold"),
                     bg=COL_PANEL, fg="#94A3B8", width=12,
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 10),
                     bg=COL_PANEL, fg=COL_TEXT,
                     anchor="w").pack(side=tk.LEFT)

        # Close button
        tk.Button(popup, text="Close", command=popup.destroy,
                  font=("Segoe UI", 9, "bold"),
                  bg=COL_ACCENT, fg="white", relief=tk.FLAT,
                  activebackground="#1d4ed8", cursor="hand2",
                  padx=20, pady=4).pack(pady=(16, 12))

        popup.transient(self.root)
        popup.grab_set()

    def _build_ui(self):
        title_bar = tk.Frame(self.root, bg=COL_ACCENT, height=48)
        title_bar.pack(fill=tk.X)
        # Try to load and resize the STMicroelectronics logo
        try:
            from PIL import Image, ImageTk
            pil_img = Image.open("st_logo.png")
            # Resize to height 32px to fit nicely in the 48px title bar
            aspect = pil_img.width / pil_img.height
            new_height = 32
            new_width = int(new_height * aspect)
            pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(pil_img)
            
            logo_lbl = tk.Label(title_bar, image=self.logo_img, bg=COL_ACCENT)
            logo_lbl.pack(side=tk.LEFT, padx=(16, 0), pady=8)
        except ImportError:
            # Fallback to tk.PhotoImage if PIL is not installed
            try:
                self.logo_img = tk.PhotoImage(file="st_logo.png")
                # Subsample to roughly scale it down (assuming a large original image)
                self.logo_img = self.logo_img.subsample(12, 12)
                logo_lbl = tk.Label(title_bar, image=self.logo_img, bg=COL_ACCENT)
                logo_lbl.pack(side=tk.LEFT, padx=(16, 0), pady=8)
            except Exception:
                pass  # Skip if image not found
        except Exception:
            pass  # Skip if image not found
        tk.Label(title_bar, text=" BANK SECURITY SYSTEM",
                 font=("Segoe UI", 16, "bold"),
                 bg=COL_ACCENT, fg="white").pack(side=tk.LEFT, padx=(8, 16), pady=8)

        # 👁 Eye button — top-right corner of title bar
        eye_btn = tk.Label(title_bar, text="👁", font=("Segoe UI", 14),
                           bg=COL_ACCENT, fg="white", cursor="hand2")
        eye_btn.pack(side=tk.RIGHT, padx=16, pady=8)
        eye_btn.bind("<Button-1>", lambda _e: self._show_about())

        content = tk.Frame(self.root, bg=COL_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        left = tk.Frame(content, bg=COL_PANEL, width=300)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)
        right = tk.Frame(content, bg=COL_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_controls(left)
        self._build_floorplan(right)
        self._build_log(right)

    def _build_controls(self, parent):
        def section(text):
            f = tk.Frame(parent, bg=COL_BORDER, pady=1)
            f.pack(fill=tk.X, padx=8, pady=(10, 2))
            tk.Label(f, text=text, font=("Segoe UI", 10, "bold"),
                     bg=COL_BORDER, fg=COL_TEXT).pack(anchor=tk.W, padx=6, pady=3)
        def row(lbl, default="", on_change=None):
            f = tk.Frame(parent, bg=COL_PANEL)
            f.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(f, text=lbl, width=14, anchor="w",
                     font=("Segoe UI", 9), bg=COL_PANEL, fg=COL_TEXT).pack(side=tk.LEFT)
            picker = SpinnerTimePicker(f, default=default, on_change=on_change)
            picker.pack(side=tk.LEFT, padx=4)
            return picker
        def btn(text, cmd, color="#2980b9"):
            b = tk.Button(parent, text=text, command=cmd,
                      font=("Segoe UI", 10, "bold"),
                      bg=color, fg="white", relief=tk.FLAT,
                      activebackground="#1a5276", activeforeground="white",
                      cursor="hand2", pady=5)
            b.pack(fill=tk.X, padx=12, pady=3)
            return b

        # ... (serial connection UI) ...
        section("📡  Serial Connection")
        ports = [p.device for p in serial.tools.list_ports.comports()] or ["COM3"]
        self.port_var = tk.StringVar(value=ports[0])
        pf = tk.Frame(parent, bg=COL_PANEL)
        pf.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(pf, text="COM Port:", width=10, anchor="w",
                 font=("Segoe UI", 9), bg=COL_PANEL, fg=COL_TEXT).pack(side=tk.LEFT)
        pm = tk.OptionMenu(pf, self.port_var, *ports)
        pm.config(bg="#0d1b2a", fg="#38BDF8", font=("Consolas", 9),
                  relief=tk.FLAT, bd=0, activebackground=COL_BORDER)
        pm["menu"].config(bg="#0d1b2a", fg="#38BDF8")
        pm.pack(side=tk.LEFT, padx=4)
        self.conn_btn = tk.Button(parent, text="⚡  CONNECT",
                                  command=self.toggle_connection,
                                  font=("Segoe UI", 10, "bold"),
                                  bg="#27ae60", fg="white", relief=tk.FLAT,
                                  activebackground="#1e8449", cursor="hand2", pady=6)
        self.conn_btn.pack(fill=tk.X, padx=12, pady=4)
        self.conn_status = tk.Label(parent, text="● DISCONNECTED",
                                    font=("Segoe UI", 9, "bold"),
                                    bg=COL_PANEL, fg="#e74c3c")
        self.conn_status.pack(pady=2)

        section("🕐  Time Settings  (HH:MM:SS)")
        # Spinner time pickers (▲/▼ arrows with mouse-wheel support)
        self.e_current = row("Current Time", "09:00:00",
                             on_change=self._on_time_entry_change)
                             
        self.e_enable  = row("Enable (Night)", "22:00:00")
        self.e_disable = row("Disable (Day)",  "07:00:00")
        self.btn_set = btn("✅  Set All Times", self.cmd_set_all_times, "#27ae60")
        
        section("🔧  Actions")
        #self.btn_auto = btn("🤖  Auto Arm (22:00–07:00)", self.cmd_auto_arm, "#16a085")
        self.btn_start = btn("▶️  Start Monitoring", self.cmd_start, "#e94560")
        
        self.btn_history = btn("📜  View History", self.cmd_view_history, "#8e44ad") 
        self.btn_graph = btn("📈  Intrusion Graph", self.cmd_show_graph, "#d35400")

        # CHANGED: Added PC Time sync button here
        self.btn_sync = btn("⏱️  Sync to PC Time", self.cmd_sync_pc_time, "#004b96")

        section("🚨  System Status")
        self.status_lbl = tk.Label(parent, text="IDLE",
                                   font=("Segoe UI", 16, "bold"),
                                   bg=COL_PANEL, fg=COL_IDLE)
        self.status_lbl.pack(pady=6)
        self.alert_lbl = tk.Label(parent, text="",
                                  font=("Segoe UI", 12, "bold"),
                                  bg=COL_PANEL, fg=COL_FLASH_A)
        self.alert_lbl.pack(pady=4)
        self.info_lbl = tk.Label(parent, text="System ready",
                                 font=("Segoe UI", 9),
                                 bg=COL_PANEL, fg="#888888")
        self.info_lbl.pack(pady=2)

    def _build_floorplan(self, parent):
        fp_frame = tk.Frame(parent, bg=COL_BG)
        fp_frame.pack(fill=tk.BOTH, expand=False, pady=(4, 0))
        tk.Label(fp_frame, text="BANK FLOOR PLAN",
                 font=("Segoe UI", 11, "bold"),
                 bg=COL_BG, fg=COL_TEXT).pack()
        map_container = tk.Frame(fp_frame, bg=COL_BG)
        map_container.pack(padx=4, pady=4)
        self.canvas = tk.Canvas(map_container, width=820, height=420,
                                bg="#111827", highlightthickness=2,
                                highlightbackground=COL_BORDER)
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))
        legend_frame = tk.Frame(map_container, bg="#111827",
                                highlightthickness=2,
                                highlightbackground=COL_BORDER,
                                width=150)
        legend_frame.pack(side=tk.LEFT, fill=tk.Y)
        legend_frame.pack_propagate(False)
        tk.Label(legend_frame, text="LEGEND",
                 font=("Segoe UI", 10, "bold"),
                 bg="#111827", fg=COL_TEXT).pack(pady=(15, 20))
        legend_items = [
            (COL_SAFE, "SECURE"),
            (COL_DANGER, "UNSECURED"),
            (COL_IDLE, "IDLE"),
            (COL_FLASH_A, "ALERT!")
        ]
        for color, text in legend_items:
            item_frame = tk.Frame(legend_frame, bg="#111827")
            item_frame.pack(fill=tk.X, padx=12, pady=12)
            color_box = tk.Canvas(item_frame, width=24, height=24,
                                  bg=color, highlightthickness=1,
                                  highlightbackground="black")
            color_box.pack(side=tk.LEFT)
            tk.Label(item_frame, text=text,
                     font=("Segoe UI", 9, "bold"),
                     bg="#0d0d0d", fg=COL_TEXT).pack(side=tk.LEFT, padx=(8, 0))
        self._draw_floorplan()

    def _draw_floorplan(self):
        c = self.canvas
        c.delete("all")
        BORDER = 3
        W = 820
        H = 420
        PAD = 15
        zones = {
            "vault":    (PAD, PAD, 230, H - PAD),
            "atm":      (240, PAD, 480, 195),
            "cashier":  (240, 205, 480, H - PAD),
            "customer": (490, PAD + 50, 640, H - PAD),
            "entry":    (650, PAD + 60, W - PAD, H - 60),
        }
        labels = {
            "vault": "VAULT",
            "atm": "ATM",
            "cashier": "CASHIER\nDESKS",
            "customer": "CUSTOMER\nAREA",
            "entry": "ENTRY"
        }
        self.zone_rects = {}
        self.zone_labels = {}
        for key, (x1, y1, x2, y2) in zones.items():
            rect = c.create_rectangle(x1, y1, x2, y2,
                                      fill=COL_IDLE,
                                      outline="#CBD5E1", width=BORDER)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            lbl = c.create_text(cx, cy, text=labels[key],
                                font=("Segoe UI", 14, "bold"),
                                fill="#0F172A", justify=tk.CENTER)
            self.zone_rects[key] = rect
            self.zone_labels[key] = lbl
        # Update zone centers for ripple
        for key, (x1, y1, x2, y2) in zones.items():
            self.zone_centers[key] = ((x1 + x2) // 2, (y1 + y2) // 2)
        entry_coords = zones["entry"]
        c.create_text((entry_coords[0] + entry_coords[2]) // 2,
                      entry_coords[1] - 20, text="← IN",
                      font=("Segoe UI", 11, "bold"), fill=COL_TEXT)

    def _color_zone(self, key, color):
        self.canvas.itemconfig(self.zone_rects[key], fill=color)

    def _build_log(self, parent):
        log_frame = tk.Frame(parent, bg=COL_BG)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 4))
        
        # New Header frame containing the Title and Clear Button
        header = tk.Frame(log_frame, bg=COL_BG)
        header.pack(fill=tk.X, padx=4)
        
        tk.Label(header, text="📋  UART Live Feed",
                 font=("Segoe UI", 9, "bold"),
                 bg=COL_BG, fg=COL_TEXT).pack(side=tk.LEFT)
                 
        tk.Button(header, text="Clear", command=self.clear_log_and_alert,
                  bg="#e74c3c", fg="white", relief=tk.FLAT,
                  font=("Segoe UI", 8, "bold"), cursor="hand2", padx=10).pack(side=tk.RIGHT)
                  
        self.log_text = tk.Text(log_frame, height=8,
                                font=("Consolas", 9),
                                bg="#0d0d0d", fg="#38BDF8",
                                insertbackground="white",
                                relief=tk.FLAT, bd=2)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        sb = tk.Scrollbar(log_frame, command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=sb.set)

    def clear_log_and_alert(self):
        self.log_text.delete("1.0", tk.END)
        self._trigger_clear()

    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_var.get()
            try:
                # Disable DTR/RTS to try and prevent reset, though Windows often toggles it anyway
                self.serial_port = serial.Serial()
                self.serial_port.port = port
                self.serial_port.baudrate = BAUD_RATE
                self.serial_port.timeout = 0.1
                self.serial_port.setDTR(False)
                self.serial_port.setRTS(False)
                self.serial_port.open()
                
                self.is_connected = True
                self.conn_btn.config(text="⛔  DISCONNECT", bg="#c0392b")
                self.conn_status.config(text=f"● CONNECTED  ({port})", fg="#2ecc71")
                self._log(f"--- Connected to {port} @ {BAUD_RATE} baud ---\n")
                
                # Lock action buttons to allow STM32 to finish boot (VL53L8CX init takes ~2.5s)
                self.btn_set.config(state=tk.DISABLED)
                #self.btn_auto.config(state=tk.DISABLED)
                self.btn_start.config(state=tk.DISABLED)
                self.conn_status.config(text="● BOOTING SENSOR...", fg="#f39c12")
                self._log("--- Waiting 3.5s for board to initialize... ---\n")
                self.root.after(3500, self._enable_actions)
                
                threading.Thread(target=self._read_loop, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not open {port}.\n{e}")
        else:
            self.is_connected = False
            try:
                self.serial_port.close()
            except:
                pass
            self.conn_btn.config(text="⚡  CONNECT", bg="#27ae60")
            self.conn_status.config(text="● DISCONNECTED", fg="#e74c3c")
            self.btn_set.config(state=tk.NORMAL)
            #self.btn_auto.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)
            self._log("\n--- Disconnected ---\n")
            self._set_idle_colors()
            self._stop_all_effects()

    def _enable_actions(self):
        if self.is_connected:
            self.conn_status.config(text=f"● CONNECTED  ({self.port_var.get()})", fg="#2ecc71")
            self.btn_set.config(state=tk.NORMAL)
            #self.btn_auto.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)
            self._log("--- Ready for commands ---\n")

    def _read_loop(self):
        buf = ""
        while self.is_connected and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    chunk = self.serial_port.read(self.serial_port.in_waiting).decode("utf-8", errors="ignore")
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            self.root.after(0, self._process_line, line)
            except:
                break
            time.sleep(0.02)

    def _raw_send(self, data: str):
        if self.serial_port and self.serial_port.is_open:
            # Send byte-by-byte with a small delay.
            # This prevents STM32 Overrun Errors (ORE) since the board uses
            # polling HAL_UART_Receive and echoes each byte back immediately.
            for char in data:
                self.serial_port.write(char.encode("utf-8"))
                self.serial_port.flush()
                time.sleep(0.01)

    # ─────────────────────────────────────────────────────────
    #  PARSER
    # ─────────────────────────────────────────────────────────
    def _process_line(self, line: str):
        self._log(line + "\n")
        upper = line.upper()
        clean = upper.replace(">>>", "").replace("<<<", "").replace("=", "").strip()
        
        # CHANGED: Listen to UART feed to capture exact progressing clock time (e.g. 09:00:10)
        if upper.startswith("TIME:") or clean.startswith("TIME:"):
            # System time updates via serial are ignored for GUI mode changes,
            # BUT we capture this hardware-ticking time here for accurate intrusion logging!
            extracted = clean.replace("TIME:", "").strip()
            if len(extracted) >= 8: # Format HH:MM:SS
                self.last_known_sim_time = extracted[:8]
            pass

        # Confirmation echoes
        if "CURRENT:" in upper:
            return
        if "ENABLE:" in upper:
            return
        if "DISABLE:" in upper:
            return
        if upper.startswith("TIME SAVED:") or upper.startswith("ENTER") or upper.startswith("RTC SET"):
            return
        if "INTRUSION" in clean or "INTRUDER" in clean or "DETECTED" in clean:
            self._trigger_intrusion()
            return
        if "CLEAR" in clean:
            self._trigger_clear()
            return
        if "MONITORING STARTED" in clean or "MONITORING START" in clean:
            if not self.detected:
                self._stop_all_effects()
                if self.current_mode == "day":
                    self._set_day_colors()
                    self.status_lbl.config(text="🔍 DAY MONITORING", fg="#3498db")
                else:
                    self._set_night_colors()
                    self.status_lbl.config(text="🔍 NIGHT MONITORING", fg="#3498db")
                self.alert_lbl.config(text="")
                self.info_lbl.config(text="Waiting for alarm...", fg="#888")
            return
        if "ALARM ACTIVE" in clean or "ALARM ENABLED" in clean or "ALARM ON" in clean:
            if not self.detected:
                self._stop_all_effects()
                if self.current_mode == "day":
                    self._set_day_colors()
                    self.status_lbl.config(text="☀️ DAY MODE", fg="#f39c12")
                    self.info_lbl.config(text="Vault & Cashier secured", fg="#f39c12")
                else:
                    self._set_night_colors()
                    self.status_lbl.config(text="🌙 NIGHT MODE", fg="#2ecc71")
                    self.info_lbl.config(text="All zones armed", fg="#2ecc71")
                self.alert_lbl.config(text="")
            return
        if "ALARM DISABLED" in clean or "ALARM OFF" in clean:
            if not self.detected:
                self._stop_all_effects()
                if self.current_mode == "day":
                    self._set_day_colors()
                    self.status_lbl.config(text="☀️ DAY MODE", fg="#f39c12")
                    self.info_lbl.config(text="Vault & Cashier secured", fg="#f39c12")
                else:
                    self._set_night_colors()
                    self.status_lbl.config(text="🌙 NIGHT MODE", fg="#2ecc71")
                    self.info_lbl.config(text="All zones armed", fg="#2ecc71")
                self.alert_lbl.config(text="")
            return
        if "MONITORING STOPPED" in clean or "MONITORING STOP" in clean:
            self.detected = False
            self._stop_all_effects()
            if self.current_mode == "day":
                self._set_day_colors()
            else:
                self._set_night_colors()
            self.status_lbl.config(text="☀️ SYSTEM STOPPED", fg="#f39c12")
            self.alert_lbl.config(text="")
            self.info_lbl.config(text="Monitoring stopped", fg="#f39c12")
            return
        if "SCANNING" in clean or "NO TARGET" in clean:
            if not self.detected:
                self.info_lbl.config(text="Sensor scanning...", fg="#3498db")
            return
            
        if "IDLE" in clean:
            return

    def _trigger_intrusion(self):
        # Determine the name of the breached zone
        if self.alert_zone == "vault":
            zone_name = "VAULT"
        else:
            zone_name = "ENTRY"
        self.status_lbl.config(text=f"⚠️ INTRUSION DETECTED", fg=COL_FLASH_A)
        self.info_lbl.config(text=f"SECURITY BREACH AT {zone_name}!", fg=COL_FLASH_A)
        
        # Logging call
        if not self.detected:
            self.detected = True
            self._log_intrusion_to_file()  
            self._start_flash()
            self._start_ripple()
            self._start_alert_flash()

    # ─────────────────────────────────────────────────────────
    #  NEW LOGGING, GRAPHING & PC TIME METHODS
    # ─────────────────────────────────────────────────────────
    def cmd_sync_pc_time(self):
        """Grabs the actual system (PC) time and sets it in the spinner picker."""
        now = datetime.now()
        self.e_current.set_time(now.hour, now.minute, now.second)
    
    def _get_log_filename(self):
        """Returns the file name based on the current date, fulfilling '1 file for 1 day' rule."""
        return f"intrusion_log_{datetime.now().strftime('%Y_%m_%d')}.txt"

    def _log_intrusion_to_file(self):
        """Writes the exact timing of the intrusion to the daily text file."""
        filename = self._get_log_filename()
        
        # CHANGED: Now using the hardware-ticking time pulled directly from the UART feed
        timestamp = self.last_known_sim_time
        
        zone_name = "VAULT" if self.alert_zone == "vault" else "ENTRY"
        
        # Mode "a" appends to the file if it exists, creates it if it doesn't
        with open(filename, "a") as f:
            f.write(f"{timestamp} - Intrusion detected at {zone_name}\n")

    def cmd_view_history(self):
        """Opens the daily text file using the system's default text editor."""
        filename = self._get_log_filename()
        if os.path.exists(filename):
            try:
                os.startfile(filename) # Windows Native
            except AttributeError:
                # Fallback for Linux/Mac just in case
                import subprocess
                import platform
                if platform.system() == 'Darwin':
                    subprocess.call(('open', filename))
                else:
                    subprocess.call(('xdg-open', filename))
        else:
            messagebox.showinfo("History", "No intrusions recorded today.")

    def cmd_show_graph(self):
        """Reads the daily text file and plots the timings of intrusions using matplotlib."""
        if not HAS_MATPLOTLIB:
            messagebox.showerror("Missing Module", "matplotlib is required for the graph.\nPlease open your terminal and run:\n\npip install matplotlib")
            return
            
        filename = self._get_log_filename()
        if not os.path.exists(filename):
            messagebox.showinfo("Graph", "No intrusions recorded today to plot.")
            return
            
        times = []
        zones = []
        try:
            with open(filename, "r") as f:
                for line in f:
                    parts = line.strip().split(" - ")
                    if len(parts) == 2:
                        t_str = parts[0]
                        # Clean up "Intrusion detected at VAULT" to just "VAULT"
                        z_str = parts[1].replace("Intrusion detected at ", "").strip()
                        
                        # Parse time string into datetime object for plotting
                        t_obj = datetime.strptime(t_str, "%H:%M:%S").time()
                        dt_obj = datetime.combine(datetime.today(), t_obj)
                        times.append(dt_obj)
                        zones.append(z_str)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read log file: {e}")
            return
            
        if not times:
            messagebox.showinfo("Graph", "No valid data found in today's log.")
            return
            
        # Map zones to Y-axis levels for a clean timeline scatter plot
        y_vals = [1 if z == "VAULT" else 2 for z in zones]
        
        plt.figure("Intrusion Timings", figsize=(8, 4))
        plt.title(f"Simulated Intrusions Log")
        
        # Plot markers
        plt.scatter(times, y_vals, c='red', marker='x', s=100)
        plt.yticks([1, 2], ["VAULT", "ENTRY"])
        
        # Format the X-axis specifically for time values
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xlabel("Simulated Time (Hardware Time from UART)")
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()
    # ─────────────────────────────────────────────────────────

    def _trigger_clear(self):
        self.detected = False
        self._stop_all_effects()
        self._color_zone(self.alert_zone, COL_SAFE)
        self.canvas.itemconfig(self.zone_labels[self.alert_zone],
                               text=self.alert_zone.upper(), fill="#0F172A")
        self.status_lbl.config(text="✅ CLEAR", fg="#2ecc71")
        self.alert_lbl.config(text="")
        
    def _set_idle_colors(self):
        for key in ("vault", "atm", "cashier", "customer", "entry"):
            self._color_zone(key, COL_IDLE)
        self.status_lbl.config(text="IDLE", fg=COL_IDLE)
        self.alert_lbl.config(text="")
        self.info_lbl.config(text="System ready", fg="#888")

    def _set_night_colors(self):
        for key in ("vault", "atm", "cashier", "customer", "entry"):
            self._color_zone(key, COL_SAFE)

    def _set_day_colors(self):
        self._color_zone("vault", COL_SAFE)
        self._color_zone("cashier", COL_SAFE)
        for key in ("atm", "customer", "entry"):
            self._color_zone(key, COL_DANGER)

    def _stop_all_effects(self):
        self._stop_flash()
        self._stop_ripple()
        self._stop_alert_flash()

    # ── FLASH — targets self.alert_zone ───────────────────────
    def _start_flash(self):
        self._stop_flash()
        self.flash_state = False
        self._flash_tick()

    def _flash_tick(self):
        if not self.detected:
            return
        self.flash_state = not self.flash_state
        color = COL_FLASH_A if self.flash_state else COL_FLASH_B
        self._color_zone(self.alert_zone, color)
        if self.flash_state:
            self.canvas.itemconfig(self.zone_labels[self.alert_zone],
                                   text="⚠️\nALERT!", fill="white")
        else:
            self.canvas.itemconfig(self.zone_labels[self.alert_zone],
                                   text="🚨\nBREACH!", fill="#0F172A")
        self.flash_job = self.root.after(FLASH_DELAY, self._flash_tick)

    def _stop_flash(self):
        if self.flash_job:
            self.root.after_cancel(self.flash_job)
            self.flash_job = None
        self.flash_state = False
        if hasattr(self, 'zone_labels'):
            for key in ("entry", "vault"):
                if key in self.zone_labels:
                    self.canvas.itemconfig(self.zone_labels[key],
                                           text=key.upper(), fill="#0F172A")

    def _start_alert_flash(self):
        self._stop_alert_flash()
        self.alert_state = False
        self._alert_tick()

    def _alert_tick(self):
        if not self.detected:
            return
        self.alert_state = not self.alert_state
        zone_name = "VAULT" if self.alert_zone == "vault" else "ENTRY"
        if self.alert_state:
            self.alert_lbl.config(
                text=f"🚨 ALERT! {zone_name} BREACH 🚨", fg=COL_FLASH_A)
        else:
            self.alert_lbl.config(
                text="⚠️ SECURITY VIOLATION ⚠️", fg=COL_FLASH_B)
        self.alert_job = self.root.after(250, self._alert_tick)

    def _stop_alert_flash(self):
        if self.alert_job:
            self.root.after_cancel(self.alert_job)
            self.alert_job = None
        self.alert_state = False
        self.alert_lbl.config(text="")

    # ── RIPPLE — centred on self.alert_zone ───────────────────
    def _start_ripple(self):
        self._stop_ripple()
        self._spawn_ring()
        self._ripple_tick()

    def _spawn_ring(self):
        if not self.detected:
            return
        cx, cy = self.zone_centers[self.alert_zone]
        ring_id = self.canvas.create_oval(
            cx - 5, cy - 5, cx + 5, cy + 5,
            outline=COL_FLASH_A, width=3, fill=""
        )
        self.ripple_rings.append({"id": ring_id, "radius": 5,
                                  "cx": cx, "cy": cy})
        self.ripple_spawn_job = self.root.after(400, self._spawn_ring)

    def _ripple_tick(self):
        if not self.detected:
            return
        MAX_RADIUS = 130
        STEP = 5
        alive = []
        for ring in self.ripple_rings:
            ring["radius"] += STEP
            r  = ring["radius"]
            cx = ring["cx"]
            cy = ring["cy"]
            if r >= MAX_RADIUS:
                self.canvas.delete(ring["id"])
            else:
                self.canvas.coords(
                    ring["id"],
                    cx - r, cy - r, cx + r, cy + r
                )
                frac = r / MAX_RADIUS
                intensity = int(255 * (1 - frac))
                color = f"#{intensity:02x}{intensity//4:02x}00"
                width = max(1, int(4 * (1 - frac)))
                self.canvas.itemconfig(ring["id"], outline=color, width=width)
                alive.append(ring)
        self.ripple_rings = alive
        self.ripple_job = self.root.after(40, self._ripple_tick)

    def _stop_ripple(self):
        if self.ripple_job:
            self.root.after_cancel(self.ripple_job)
            self.ripple_job = None
        if self.ripple_spawn_job:
            self.root.after_cancel(self.ripple_spawn_job)
            self.ripple_spawn_job = None
        for ring in self.ripple_rings:
            self.canvas.delete(ring["id"])
        self.ripple_rings = []

    def _log(self, msg: str):
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)

    @staticmethod
    def _parse_time(text: str) -> str:
        t = text.replace(":", "").replace(" ", "").strip()
        if len(t) != 6 or not t.isdigit():
            raise ValueError(f"Invalid time: '{text}'. Use HH:MM:SS")
        return t

    def cmd_set_all_times(self):
        if not (self.is_connected and self.serial_port and self.serial_port.is_open):
            messagebox.showwarning("Not Connected", "Connect first!")
            return
        try:
            tc = self._parse_time(self.e_current.get())
            te = self._parse_time(self.e_enable.get())
            td = self._parse_time(self.e_disable.get())
        except ValueError as e:
            messagebox.showerror("Time Error", str(e))
            return
        # Apply mode from the typed current time manually via button press
        hour = int(tc[:2])
        minute = int(tc[2:4])
        self._apply_mode_from_time(hour, minute)
        self._log("\n─── Setting all times ───────────────────────\n")
        self._log(f" 📤 Current → {tc[:2]}:{tc[2:4]}:{tc[4:]}\n")
        self._log(f" 📤 Enable  → {te[:2]}:{te[2:4]}:{te[4:]}\n")
        self._log(f" 📤 Disable → {td[:2]}:{td[2:4]}:{td[4:]}\n")
        self._log("─────────────────────────────────────────────\n")
        threading.Thread(target=self._set_all_worker, args=(tc, te, td), daemon=True).start()

    def _set_all_worker(self, tc, te, td):
        try:
            self._raw_send("1")
            time.sleep(0.4)
            self._raw_send(tc)
            time.sleep(0.8)
            self._raw_send("2")
            time.sleep(0.4)
            self._raw_send(te)
            time.sleep(0.8)
            self._raw_send("3")
            time.sleep(0.4)
            self._raw_send(td)
            time.sleep(0.8)
            self.root.after(0, self._log, "\n[✅] All times sent. Press Start Monitoring.\n")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def cmd_auto_arm(self):
        if not (self.is_connected and self.serial_port and self.serial_port.is_open):
            messagebox.showwarning("Not Connected", "Connect first!")
            return
        self._log(" 📤 Auto-Arm\n")
        threading.Thread(target=self._raw_send, args=("6",), daemon=True).start()

    def cmd_start(self):
        if not (self.is_connected and self.serial_port and self.serial_port.is_open):
            messagebox.showwarning("Not Connected", "Connect first!")
            return
        self._log(" 📤 Start Monitoring\n")
        threading.Thread(target=self._raw_send, args=("4",), daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = BankSecurityGUI(root)
    root.mainloop()