import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime

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
COL_ACCENT    = "#2563EB"     # Royal blue


class BankSecurityGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🏦  Bank Security System  —  STM32 L476RG")
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
        self.ripple_cx = 750
        self.ripple_cy = 200

        self._build_ui()
        self._set_idle_colors()

    def _build_ui(self):
        title_bar = tk.Frame(self.root, bg=COL_ACCENT, height=48)
        title_bar.pack(fill=tk.X)
        tk.Label(title_bar, text="🏦  BANK SECURITY SYSTEM",
                 font=("Segoe UI", 16, "bold"),
                 bg=COL_ACCENT, fg="white").pack(side=tk.LEFT, padx=16, pady=8)

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

        def row(lbl, default=""):
            f = tk.Frame(parent, bg=COL_PANEL)
            f.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(f, text=lbl, width=14, anchor="w",
                     font=("Segoe UI", 9), bg=COL_PANEL, fg=COL_TEXT).pack(side=tk.LEFT)
            e = tk.Entry(f, width=10, font=("Consolas", 10),
                         bg="#0d1b2a", fg="#38BDF8",
                         insertbackground="white", relief=tk.FLAT, bd=2)
            e.insert(0, default)
            e.pack(side=tk.LEFT, padx=4)
            return e

        def btn(text, cmd, color="#2980b9"):
            tk.Button(parent, text=text, command=cmd,
                      font=("Segoe UI", 10, "bold"),
                      bg=color, fg="white", relief=tk.FLAT,
                      activebackground="#1a5276", activeforeground="white",
                      cursor="hand2", pady=5).pack(fill=tk.X, padx=12, pady=3)

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
        now = datetime.now().strftime("%H:%M:%S")
        self.e_current = row("Current Time", now)
        self.e_enable  = row("Enable (Night)", "22:00:00")
        self.e_disable = row("Disable (Day)",  "07:00:00")

        btn("✅  Set All Times", self.cmd_set_all_times, "#27ae60")

        section("🔧  Actions")
        btn("🤖  Auto Arm (22:00–07:00)", self.cmd_auto_arm, "#16a085")
        btn("▶️  Start Monitoring", self.cmd_start, "#e94560")

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

        # Main container for map and legend side by side
        map_container = tk.Frame(fp_frame, bg=COL_BG)
        map_container.pack(padx=4, pady=4)

        # Floor plan canvas - WIDER
        self.canvas = tk.Canvas(map_container, width=820, height=420,
                                bg="#111827", highlightthickness=2,
                                highlightbackground=COL_BORDER)
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))

        # Legend box (right)
        legend_frame = tk.Frame(map_container, bg="#111827", 
                                highlightthickness=2,
                                highlightbackground=COL_BORDER,
                                width=150)
        legend_frame.pack(side=tk.LEFT, fill=tk.Y)
        legend_frame.pack_propagate(False)

        tk.Label(legend_frame, text="LEGEND",
                 font=("Segoe UI", 10, "bold"),
                 bg="#111827", fg=COL_TEXT).pack(pady=(15, 20))

        # Legend items
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
        
        # Canvas dimensions
        W = 820
        H = 420
        PAD = 15
        
        # Zone dimensions - ENTRY is now much wider
        zones = {
            # VAULT - Large left section
            "vault":    (PAD, PAD, 230, H - PAD),
            
            # ATM - Top middle
            "atm":      (240, PAD, 480, 195),
            
            # CASHIER - Bottom middle
            "cashier":  (240, 205, 480, H - PAD),
            
            # CUSTOMER AREA - Right of middle
            "customer": (490, PAD + 50, 640, H - PAD),
            
            # ENTRY - Far right, WIDER (150px) and tall
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

        # Update ripple center to entry zone
        entry_coords = zones["entry"]
        self.ripple_cx = (entry_coords[0] + entry_coords[2]) // 2
        self.ripple_cy = (entry_coords[1] + entry_coords[3]) // 2

        # Entry arrow
        c.create_text(self.ripple_cx, entry_coords[1] - 20, text="← IN",
                      font=("Segoe UI", 11, "bold"), fill=COL_TEXT)

    def _color_zone(self, key, color):
        self.canvas.itemconfig(self.zone_rects[key], fill=color)

    def _build_log(self, parent):
        log_frame = tk.Frame(parent, bg=COL_BG)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

        tk.Label(log_frame, text="📋  UART Live Feed",
                 font=("Segoe UI", 9, "bold"),
                 bg=COL_BG, fg=COL_TEXT).pack(anchor=tk.W, padx=4)

        self.log_text = tk.Text(log_frame, height=8,
                                font=("Consolas", 9),
                                bg="#0d0d0d", fg="#38BDF8",
                                insertbackground="white",
                                relief=tk.FLAT, bd=2)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        sb = tk.Scrollbar(log_frame, command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=sb.set)

    def toggle_connection(self):
        if not self.is_connected:
            port = self.port_var.get()
            try:
                self.serial_port = serial.Serial(port, BAUD_RATE, timeout=0.1)
                self.is_connected = True
                self.conn_btn.config(text="⛔  DISCONNECT", bg="#c0392b")
                self.conn_status.config(text=f"● CONNECTED  ({port})", fg="#2ecc71")
                self._log(f"--- Connected to {port} @ {BAUD_RATE} baud ---\n")
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
            self._log("\n--- Disconnected ---\n")
            self._set_idle_colors()
            self._stop_all_effects()

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
            self.serial_port.write(data.encode("utf-8"))
            self.serial_port.flush()

    def _process_line(self, line: str):
        self._log(line + "\n")
        
        clean = line.upper().replace(">>>", "").replace("<<<", "").replace("=", "").strip()
        
        print(f"[DEBUG] Raw: '{line}' | Clean: '{clean}'")

        if "INTRUSION" in clean or "INTRUDER" in clean or "DETECTED" in clean:
            print("[DEBUG] >>> INTRUSION MATCHED <<<")
            self._trigger_intrusion()
            return

        if "CLEAR" in clean:
            print("[DEBUG] >>> CLEAR MATCHED <<<")
            self._trigger_clear()
            return

        if "CURRENT:" in line.upper():
            self._log_status(f"✅ Current time set")
            return
            
        if "ENABLE:" in line.upper():
            self._log_status(f"✅ Enable time set")
            return
            
        if "DISABLE:" in line.upper():
            self._log_status(f"✅ Disable time set")
            return

        if "MONITORING STARTED" in clean or "MONITORING START" in clean:
            self.detected = False
            self._stop_all_effects()
            self._set_night_colors()
            self.status_lbl.config(text="🔍 MONITORING", fg="#3498db")
            self.alert_lbl.config(text="")
            self.info_lbl.config(text="Waiting for alarm...", fg="#888")
            self._log_status("🟢 Monitoring started")
            return

        if "ALARM ACTIVE" in clean or "ALARM ENABLED" in clean or "ALARM ON" in clean:
            self.detected = False
            self._stop_all_effects()
            self._set_night_colors()
            self.status_lbl.config(text="🌙 ALARM ACTIVE", fg="#2ecc71")
            self.alert_lbl.config(text="All zones armed", fg="#2ecc71")
            self.info_lbl.config(text="Security system armed", fg="#2ecc71")
            self._log_status("🟢 Alarm ACTIVE")
            return

        if "ALARM DISABLED" in clean or "ALARM OFF" in clean:
            self.detected = False
            self._stop_all_effects()
            self._set_day_colors()
            self.status_lbl.config(text="☀️ DAY MODE", fg="#f39c12")
            self.alert_lbl.config(text="")
            self.info_lbl.config(text="Vault & Cashier secured", fg="#f39c12")
            self._log_status("🔴 Alarm disabled")
            return

        if "MONITORING STOPPED" in clean or "MONITORING STOP" in clean:
            self.detected = False
            self._stop_all_effects()
            self._set_day_colors()
            self.status_lbl.config(text="☀️ DAY MODE", fg="#f39c12")
            self.alert_lbl.config(text="")
            self.info_lbl.config(text="Vault & Cashier secured", fg="#f39c12")
            self._log_status("☀️ Switched to Day Mode")
            return

        if "SCANNING" in clean or "NO TARGET" in clean:
            if not self.detected:
                self.info_lbl.config(text="Sensor scanning...", fg="#3498db")
            return

    def _trigger_intrusion(self):
        print("[DEBUG] _trigger_intrusion() CALLED!")
        
        self.status_lbl.config(text="⚠️ INTRUSION DETECTED", fg=COL_FLASH_A)
        self.info_lbl.config(text="SECURITY BREACH AT ENTRY!", fg=COL_FLASH_A)
        
        if not self.detected:
            self.detected = True
            print("[DEBUG] Starting all effects...")
            self._start_flash()
            self._start_ripple()
            self._start_alert_flash()

    def _trigger_clear(self):
        print("[DEBUG] _trigger_clear() CALLED!")
        
        self.detected = False
        self._stop_all_effects()
        self._color_zone("entry", COL_SAFE)
        self.canvas.itemconfig(self.zone_labels["entry"], text="ENTRY", fill="#0F172A")
        
        self.status_lbl.config(text="✅ CLEAR", fg="#2ecc71")
        self.alert_lbl.config(text="")
        self.info_lbl.config(text="Entry zone clear", fg="#2ecc71")

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
        # Vault and Cashier stay green (secured)
        self._color_zone("vault", COL_SAFE)
        self._color_zone("cashier", COL_SAFE)
        # Others are red (unsecured)
        for key in ("atm", "customer", "entry"):
            self._color_zone(key, COL_DANGER)

    def _stop_all_effects(self):
        self._stop_flash()
        self._stop_ripple()
        self._stop_alert_flash()

    def _start_flash(self):
        self._stop_flash()
        self.flash_state = False
        self._flash_tick()

    def _flash_tick(self):
        if not self.detected:
            return
        
        self.flash_state = not self.flash_state
        color = COL_FLASH_A if self.flash_state else COL_FLASH_B
        self._color_zone("entry", color)
        
        if self.flash_state:
            self.canvas.itemconfig(self.zone_labels["entry"], text="⚠️\nALERT!", fill="white")
        else:
            self.canvas.itemconfig(self.zone_labels["entry"], text="🚨\nBREACH!", fill="#0F172A")
        
        self.flash_job = self.root.after(FLASH_DELAY, self._flash_tick)

    def _stop_flash(self):
        if self.flash_job:
            self.root.after_cancel(self.flash_job)
            self.flash_job = None
        self.flash_state = False
        if hasattr(self, 'zone_labels') and "entry" in self.zone_labels:
            self.canvas.itemconfig(self.zone_labels["entry"], text="ENTRY", fill="#0F172A")

    def _start_alert_flash(self):
        self._stop_alert_flash()
        self.alert_state = False
        self._alert_tick()

    def _alert_tick(self):
        if not self.detected:
            return
        
        self.alert_state = not self.alert_state
        
        if self.alert_state:
            self.alert_lbl.config(text="🚨 ALERT! ENTRY BREACH 🚨", fg=COL_FLASH_A)
        else:
            self.alert_lbl.config(text="⚠️ SECURITY VIOLATION ⚠️", fg=COL_FLASH_B)
        
        self.alert_job = self.root.after(250, self._alert_tick)

    def _stop_alert_flash(self):
        if self.alert_job:
            self.root.after_cancel(self.alert_job)
            self.alert_job = None
        self.alert_state = False
        self.alert_lbl.config(text="")

    def _start_ripple(self):
        self._stop_ripple()
        self._spawn_ring()
        self._ripple_tick()

    def _spawn_ring(self):
        if not self.detected:
            return
        
        ring_id = self.canvas.create_oval(
            self.ripple_cx - 5, self.ripple_cy - 5,
            self.ripple_cx + 5, self.ripple_cy + 5,
            outline=COL_FLASH_A, width=3, fill=""
        )
        self.ripple_rings.append({"id": ring_id, "radius": 5})
        self.ripple_spawn_job = self.root.after(400, self._spawn_ring)

    def _ripple_tick(self):
        if not self.detected:
            return
        
        MAX_RADIUS = 130
        STEP = 5
        
        alive = []
        for ring in self.ripple_rings:
            ring["radius"] += STEP
            r = ring["radius"]
            
            if r >= MAX_RADIUS:
                self.canvas.delete(ring["id"])
            else:
                self.canvas.coords(
                    ring["id"],
                    self.ripple_cx - r, self.ripple_cy - r,
                    self.ripple_cx + r, self.ripple_cy + r
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

    def _log_status(self, msg: str):
        self._log(f" {msg}\n")

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

        self._log("\n─── Setting all times ───────────────────────\n")
        self._log_status(f"📤 Current → {tc[:2]}:{tc[2:4]}:{tc[4:]}")
        self._log_status(f"📤 Enable  → {te[:2]}:{te[2:4]}:{te[4:]}")
        self._log_status(f"📤 Disable → {td[:2]}:{td[2:4]}:{td[4:]}")
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
        self._log_status("📤 Auto-Arm")
        threading.Thread(target=self._raw_send, args=("6",), daemon=True).start()

    def cmd_start(self):
        if not (self.is_connected and self.serial_port and self.serial_port.is_open):
            messagebox.showwarning("Not Connected", "Connect first!")
            return
        self._log_status("📤 Start Monitoring")
        threading.Thread(target=self._raw_send, args=("4",), daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = BankSecurityGUI(root)
    root.mainloop()