import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────
BAUD_RATE    = 115200
FLASH_DELAY  = 200   # ms between flashes when DETECTED

# Colours
COL_SAFE      = "#2ecc71"   # bright green  – all clear / night mode
COL_DANGER    = "#e74c3c"   # red           – day mode (disarmed area)
COL_FLASH_A   = "#ff4500"   # orange-red    – flash colour A
COL_FLASH_B   = "#ffff00"   # yellow        – flash colour B
COL_IDLE      = "#95a5a6"   # grey          – before connection / idle
COL_VAULT_DAY = "#2ecc71"   # vault stays green even during day
COL_BG        = "#1a1a2e"   # dark navy background
COL_PANEL     = "#16213e"   # slightly lighter panel
COL_BORDER    = "#0f3460"   # border/accent
COL_TEXT      = "#e0e0e0"   # light text
COL_ACCENT    = "#e94560"   # accent red


# ─────────────────────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────────────────────
class BankSecurityGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🏦  Bank Security System  —  STM32 L476RG")
        self.root.geometry("1100x750")
        self.root.configure(bg=COL_BG)
        self.root.resizable(False, False)

        # State
        self.serial_port   = None
        self.is_connected  = False
        self.alarm_active  = False
        self.detected      = False
        self.flash_state   = False
        self.flash_job     = None
        self._board_ready  = True       # True when board is sitting at the menu prompt
        self._prompt_seen  = False      # set when "Enter choice" arrives

        self._build_ui()
        self._set_idle_colors()

    # ─────────────────────────────────────────────────────────
    #  UI BUILD
    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Title bar ──────────────────────────────────────────
        title_bar = tk.Frame(self.root, bg=COL_ACCENT, height=48)
        title_bar.pack(fill=tk.X)
        tk.Label(title_bar, text="🏦  BANK SECURITY SYSTEM",
                 font=("Segoe UI", 16, "bold"),
                 bg=COL_ACCENT, fg="white").pack(side=tk.LEFT, padx=16, pady=8)
        self.clock_lbl = tk.Label(title_bar, text="",
                                  font=("Segoe UI", 13), bg=COL_ACCENT, fg="white")
        self.clock_lbl.pack(side=tk.RIGHT, padx=16)
        self._tick_clock()

        # ── Main content (left = controls, right = floor plan) ─
        content = tk.Frame(self.root, bg=COL_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        left  = tk.Frame(content, bg=COL_PANEL, width=300)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        right = tk.Frame(content, bg=COL_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_controls(left)
        self._build_floorplan(right)
        self._build_log(right)

    # ── LEFT PANEL ─────────────────────────────────────────────
    def _build_controls(self, parent):
        def section(text):
            f = tk.Frame(parent, bg=COL_BORDER, pady=1)
            f.pack(fill=tk.X, padx=8, pady=(10, 2))
            tk.Label(f, text=text, font=("Segoe UI", 10, "bold"),
                     bg=COL_BORDER, fg=COL_TEXT).pack(anchor=tk.W, padx=6, pady=3)
            return f

        def row(parent, label, default=""):
            f = tk.Frame(parent, bg=COL_PANEL)
            f.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(f, text=label, width=14, anchor="w",
                     font=("Segoe UI", 9), bg=COL_PANEL, fg=COL_TEXT).pack(side=tk.LEFT)
            e = tk.Entry(f, width=10, font=("Consolas", 10),
                         bg="#0d1b2a", fg="#00ff88", insertbackground="white",
                         relief=tk.FLAT, bd=2)
            e.insert(0, default)
            e.pack(side=tk.LEFT, padx=4)
            return e

        def btn(parent, text, cmd, color="#2980b9"):
            tk.Button(parent, text=text, command=cmd,
                      font=("Segoe UI", 10, "bold"),
                      bg=color, fg="white", relief=tk.FLAT,
                      activebackground="#1a5276", activeforeground="white",
                      cursor="hand2", pady=5).pack(fill=tk.X, padx=12, pady=3)

        # ── Serial connection ──────────────────────────────────
        section("📡  Serial Connection")
        ports = [p.device for p in serial.tools.list_ports.comports()] or ["COM3"]
        self.port_var = tk.StringVar(value=ports[0])
        port_frame = tk.Frame(parent, bg=COL_PANEL)
        port_frame.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(port_frame, text="COM Port:", width=10, anchor="w",
                 font=("Segoe UI", 9), bg=COL_PANEL, fg=COL_TEXT).pack(side=tk.LEFT)
        port_menu = tk.OptionMenu(port_frame, self.port_var, *ports)
        port_menu.config(bg="#0d1b2a", fg="#00ff88", font=("Consolas", 9),
                         relief=tk.FLAT, bd=0, activebackground=COL_BORDER)
        port_menu["menu"].config(bg="#0d1b2a", fg="#00ff88")
        port_menu.pack(side=tk.LEFT, padx=4)
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

        # ── Time settings ──────────────────────────────────────
        section("🕐  Time Settings  (HH:MM:SS)")
        now = datetime.now().strftime("%H:%M:%S")
        self.e_current = row(parent, "Current Time", now)
        self.e_enable  = row(parent, "Enable (Night)", "22:00:00")
        self.e_disable = row(parent, "Disable (Day)",  "07:00:00")

        btn(parent, "✅  Set Current Time", self.cmd_set_current, "#2980b9")
        btn(parent, "🌙  Set Enable Time",  self.cmd_set_enable,  "#8e44ad")
        btn(parent, "☀️  Set Disable Time", self.cmd_set_disable, "#d35400")

        # ── Actions ────────────────────────────────────────────
        section("🔧  Actions")
        btn(parent, "🤖  Auto Arm (22:00–07:00)", self.cmd_auto_arm, "#16a085")
        btn(parent, "▶️  Start Monitoring",        self.cmd_start,    "#27ae60")

        # ── Alarm status ───────────────────────────────────────
        section("🚨  System Status")
        self.status_lbl = tk.Label(parent, text="IDLE",
                                   font=("Segoe UI", 13, "bold"),
                                   bg=COL_PANEL, fg=COL_IDLE)
        self.status_lbl.pack(pady=6)

    # ── FLOOR PLAN ─────────────────────────────────────────────
    def _build_floorplan(self, parent):
        fp_frame = tk.Frame(parent, bg=COL_BG)
        fp_frame.pack(fill=tk.BOTH, expand=False, pady=(4, 0))

        tk.Label(fp_frame, text="BANK FLOOR PLAN",
                 font=("Segoe UI", 11, "bold"),
                 bg=COL_BG, fg=COL_TEXT).pack()

        self.canvas = tk.Canvas(fp_frame, width=760, height=360,
                                bg="#0d0d0d", highlightthickness=2,
                                highlightbackground=COL_BORDER)
        self.canvas.pack(padx=4, pady=4)
        self._draw_floorplan()

    def _draw_floorplan(self):
        c = self.canvas
        c.delete("all")

        W, H = 760, 360
        BORDER = 3

        # Zone coordinates  (x1, y1, x2, y2)
        zones = {
            "vault":    (10,  10,  250, 350),
            "atm":      (255, 10,  500, 175),
            "cashier":  (255, 180, 500, 350),
            "customer": (505, 60,  690, 350),
            "entry":    (695, 100, 755, 250),
        }

        labels = {
            "vault":    "VAULT",
            "atm":      "ATM",
            "cashier":  "CASHIER\nDESKS",
            "customer": "CUSTOMER\nAREA",
            "entry":    "ENTRY",
        }

        self.zone_rects  = {}
        self.zone_labels = {}

        for key, (x1, y1, x2, y2) in zones.items():
            rect = c.create_rectangle(x1, y1, x2, y2,
                                      fill=COL_IDLE,
                                      outline="black", width=BORDER)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            lbl = c.create_text(cx, cy,
                                text=labels[key],
                                font=("Segoe UI", 12, "bold"),
                                fill="black", justify=tk.CENTER)
            self.zone_rects[key]  = rect
            self.zone_labels[key] = lbl

        # Arrow from entry
        c.create_text(725, 80, text="← IN", font=("Segoe UI", 8, "bold"),
                      fill=COL_TEXT)

        # Legend (single row)
        lx = 10
        for color, text in [(COL_SAFE, "SECURE"), (COL_DANGER, "UNSECURED"),
                            (COL_IDLE, "IDLE"), (COL_FLASH_A, "ALERT!")]:
            c.create_rectangle(lx, H - 18, lx + 14, H - 4,
                               fill=color, outline="black")
            c.create_text(lx + 18, H - 11, text=text, anchor="w",
                          font=("Segoe UI", 7), fill=COL_TEXT)
            lx += 90

    def _color_zone(self, key, color):
        self.canvas.itemconfig(self.zone_rects[key], fill=color)
        # Dark text reads well on all our zone colours.
        self.canvas.itemconfig(self.zone_labels[key], fill="black")

    # ── LOG CONSOLE ────────────────────────────────────────────
    def _build_log(self, parent):
        log_frame = tk.Frame(parent, bg=COL_BG)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

        tk.Label(log_frame, text="📋  UART Live Feed",
                 font=("Segoe UI", 9, "bold"),
                 bg=COL_BG, fg=COL_TEXT).pack(anchor=tk.W, padx=4)

        self.log_text = tk.Text(log_frame, height=8,
                                font=("Consolas", 9),
                                bg="#0d0d0d", fg="#00ff88",
                                insertbackground="white",
                                relief=tk.FLAT, bd=2)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        sb = tk.Scrollbar(log_frame, command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=sb.set)

    # ─────────────────────────────────────────────────────────
    #  CLOCK
    # ─────────────────────────────────────────────────────────
    def _tick_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("  🕐  %H:%M:%S  |  %d %b %Y  "))
        self.root.after(1000, self._tick_clock)

    # ─────────────────────────────────────────────────────────
    #  SERIAL
    # ─────────────────────────────────────────────────────────
    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_var.get()
            try:
                self.serial_port = serial.Serial(port, BAUD_RATE, timeout=0.1)
                self.is_connected = True
                self._board_ready = True        # assume board is at the menu on connect
                self._prompt_seen = False
                self.conn_btn.config(text="⛔  DISCONNECT", bg="#c0392b")
                self.conn_status.config(text=f"● CONNECTED  ({port})", fg="#2ecc71")
                self._log(f"--- Connected to {port} @ {BAUD_RATE} baud ---\n")
                threading.Thread(target=self._read_loop, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Connection Error",
                    f"Could not open {port}.\n"
                    "Close TeraTerm / CubeIDE monitor first!\n\n"
                    f"{e}")
        else:
            self.is_connected = False
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.conn_btn.config(text="⚡  CONNECT", bg="#27ae60")
            self.conn_status.config(text="● DISCONNECTED", fg="#e74c3c")
            self._log("\n--- Disconnected ---\n")
            self._set_idle_colors()

    def _read_loop(self):
        buf = ""
        while self.is_connected and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    ch = self.serial_port.read(self.serial_port.in_waiting).decode("utf-8", errors="ignore")
                    buf += ch
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            self.root.after(0, self._process_line, line)
            except Exception:
                break
            time.sleep(0.02)

    def _send_safe(self, cmd: str, data: str = None):
        """
        Send a menu command. The STM32 menu is stateful, so we flush any stale
        bytes first and give the board time to reach ReadTimeFromUART() before
        sending the time payload. This lets the sequence run many times without
        reconnecting.
        """
        if not (self.is_connected and self.serial_port and self.serial_port.is_open):
            messagebox.showwarning("Not Connected", "Please connect to the board first!")
            return
        if not self._board_ready:
            self._log("\n⚠️  Board not at menu yet. Wait for the prompt, then retry.\n")
            return
        try:
            # Clear any leftover bytes so old menu output can't desync parsing.
            self.serial_port.reset_input_buffer()
            self.serial_port.write(cmd.encode("utf-8"))
            self.serial_port.flush()
            if data:
                time.sleep(0.25)            # let firmware reach ReadTimeFromUART()
                self.serial_port.write(data.encode("utf-8"))
                self.serial_port.flush()
            # We just left the menu; force a fresh prompt before next command.
            self._board_ready = False
        except Exception as e:
            messagebox.showerror("Send Error", str(e))

    # ─────────────────────────────────────────────────────────
    #  SERIAL LINE PARSER  →  update floor plan
    # ─────────────────────────────────────────────────────────
    def _process_line(self, line: str):
        self._log(line + "\n")

        upper = line.upper()

        # The board re-prints its menu prompt whenever it is ready for a new
        # command. Use THIS, not a fixed timer, to know we can send again.
        # >>> Change "ENTER CHOICE" to match your firmware's actual prompt. <<<
        # Your firmware re-prints this header every time it returns to the menu
        # and is ready for the next command. Detect it to re-enable sending.
        if "RTC ALARM SYSTEM SETUP" in upper or "AUTO ARM SYSTEM" in upper:
            self._board_ready = True
            self._prompt_seen = True
            self.status_lbl.config(text="✅  Ready — send commands", fg="#2ecc71")

        if "ALARM ENABLED" in upper or "MONITORING STARTED" in upper or "ALARM ACTIVE" in upper:
            self.alarm_active = True
            self.detected = False
            self._stop_flash()
            self._set_night_colors()
            self.status_lbl.config(text="🌙  ALARM ACTIVE", fg="#2ecc71")

        elif "MONITORING STOPPED" in upper:
            self.alarm_active = False
            self.detected = False
            self._stop_flash()
            self._set_day_colors()
            # Do NOT guess with a timer. Wait for the real menu prompt instead.
            self._board_ready = False
            self.status_lbl.config(text="⏳  Waiting for menu prompt...", fg="#e67e22")

        elif "ALARM DISABLED" in upper:
            self.alarm_active = False
            self._stop_flash()
            self._set_day_colors()
            self.status_lbl.config(text="☀️  ALARM DISABLED", fg="#f39c12")

        elif "*** DETECTED! ***" in upper or "INTRUSION" in upper:
            if not self.detected:
                self.detected = True
                self._start_flash()
            self.status_lbl.config(text="🚨  INTRUDER DETECTED!", fg=COL_ACCENT)

        elif "| CLEAR" in upper or upper == "CLEAR":
            if self.detected:
                self.detected = False
                self._stop_flash()
                self._color_zone("entry", COL_SAFE)
            self.status_lbl.config(text="✅  CLEAR", fg="#2ecc71")

        elif "| IDLE" in upper:
            self.status_lbl.config(text="💤  IDLE", fg=COL_IDLE)

    # ─────────────────────────────────────────────────────────
    #  ZONE COLOUR HELPERS
    # ─────────────────────────────────────────────────────────
    def _set_idle_colors(self):
        for key in ("vault", "atm", "cashier", "customer", "entry"):
            self._color_zone(key, COL_IDLE)

    def _set_night_colors(self):
        """All zones GREEN — alarm window active."""
        for key in ("vault", "atm", "cashier", "customer", "entry"):
            self._color_zone(key, COL_SAFE)

    def _set_day_colors(self):
        """Vault GREEN, everything else RED — daytime / disarmed."""
        self._color_zone("vault", COL_VAULT_DAY)
        for key in ("atm", "cashier", "customer", "entry"):
            self._color_zone(key, COL_DANGER)

    # ─────────────────────────────────────────────────────────
    #  FLASH ANIMATION  (entry zone only)
    # ─────────────────────────────────────────────────────────
    def _start_flash(self):
        self._stop_flash()
        self._flash_tick()

    def _flash_tick(self):
        if not self.detected:
            return
        color = COL_FLASH_A if self.flash_state else COL_FLASH_B
        self._color_zone("entry", color)
        self.flash_state = not self.flash_state
        self.flash_job = self.root.after(FLASH_DELAY, self._flash_tick)

    def _stop_flash(self):
        if self.flash_job:
            self.root.after_cancel(self.flash_job)
            self.flash_job = None
        self.flash_state = False

    # ─────────────────────────────────────────────────────────
    #  LOG HELPER
    # ─────────────────────────────────────────────────────────
    def _log(self, msg: str):
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)

    # ─────────────────────────────────────────────────────────
    #  COMMAND HELPERS
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _parse_time(text: str) -> str:
        """Convert HH:MM:SS or HHMMSS → HHMMSS."""
        t = text.replace(":", "").replace(" ", "").strip()
        if len(t) != 6 or not t.isdigit():
            raise ValueError(f"Invalid time format: '{text}'. Use HH:MM:SS")
        return t

    def cmd_set_current(self):
        try:
            t = self._parse_time(self.e_current.get())
            self._send_safe("1", t)
            self._log(f"\n>>> [GUI] Set Current Time → {t[:2]}:{t[2:4]}:{t[4:]} <<<\n")
        except ValueError as e:
            messagebox.showerror("Time Error", str(e))

    def cmd_set_enable(self):
        try:
            t = self._parse_time(self.e_enable.get())
            self._send_safe("2", t)
            self._log(f"\n>>> [GUI] Set Enable Time → {t[:2]}:{t[2:4]}:{t[4:]} <<<\n")
        except ValueError as e:
            messagebox.showerror("Time Error", str(e))

    def cmd_set_disable(self):
        try:
            t = self._parse_time(self.e_disable.get())
            self._send_safe("3", t)
            self._log(f"\n>>> [GUI] Set Disable Time → {t[:2]}:{t[2:4]}:{t[4:]} <<<\n")
        except ValueError as e:
            messagebox.showerror("Time Error", str(e))

    def cmd_auto_arm(self):
        self._send_safe("6")
        self._log("\n>>> [GUI] Auto-Arm command sent (22:00 → 07:00) <<<\n")

    def cmd_start(self):
        self._send_safe("4")
        self._log("\n>>> [GUI] Start Monitoring command sent <<<\n")


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = BankSecurityGUI(root)
    root.mainloop()