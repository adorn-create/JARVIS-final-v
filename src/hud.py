import math
import os
import threading
import tkinter as tk
from tkinter import messagebox

import psutil


BG = "#050b14"
PANEL = "#091827"
PANEL_ALT = "#0c2032"
LINE = "#173c53"
CYAN = "#63e6ff"
CYAN_DIM = "#2c819f"
TEXT = "#d8f5ff"
MUTED = "#7ea8ba"
GREEN = "#55e6b2"
AMBER = "#ffd166"
RED = "#ff7585"


class HUD:
    """Movie-inspired JARVIS command interface, built with lightweight Tkinter."""

    def __init__(
        self,
        on_send,
        on_voice,
        on_vision,
        on_stop_speaking,
        on_toggle_wake,
        on_toggle_face,
        on_toggle_gestures,
    ):
        self._tk_thread = threading.current_thread()
        self.on_send = on_send
        self._phase = 0
        self._mic_level = 0.0
        self._wake_enabled = False
        self._face_enabled = False
        self._gestures_enabled = False
        self._monitor_enabled = True

        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S. | Tactical Interface")
        self.root.geometry("1280x820")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG)

        self._build_header()
        self._build_dashboard()
        self._build_activity()
        self._build_controls()
        self.add("JARVIS", "Interface online. All existing systems are standing by.")
        self._animate()
        self._refresh_metrics()

    def _panel(self, parent, title=None):
        outer = tk.Frame(parent, bg=LINE, bd=0, highlightthickness=0)
        inner = tk.Frame(outer, bg=PANEL, padx=12, pady=10)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        if title:
            tk.Label(
                inner, text=title.upper(), bg=PANEL, fg=CYAN_DIM,
                font=("Segoe UI", 8, "bold"), anchor="w"
            ).pack(fill="x", pady=(0, 8))
        return outer, inner

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(16, 10))
        self.reactor = tk.Canvas(
            header, width=58, height=58, bg=BG, highlightthickness=0
        )
        self.reactor.pack(side="left", padx=(0, 12))
        self.reactor.create_oval(5, 5, 53, 53, outline=LINE, width=2, tags="ring")
        self.reactor.create_oval(12, 12, 46, 46, outline=CYAN_DIM, width=1)
        self.reactor.create_arc(
            5, 5, 53, 53, start=0, extent=95, style="arc",
            outline=CYAN, width=3, tags="pulse"
        )
        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box, text="J.A.R.V.I.S.", bg=BG, fg=CYAN,
            font=("Segoe UI", 23, "bold")
        ).pack(anchor="w")
        tk.Label(
            title_box, text="PERSONAL ARTIFICIAL INTELLIGENCE  /  TACTICAL INTERFACE",
            bg=BG, fg=MUTED, font=("Consolas", 8)
        ).pack(anchor="w")
        right = tk.Frame(header, bg=BG)
        right.pack(side="right", anchor="e")
        self.status = tk.Label(
            right, text="● SYSTEM ONLINE", bg=BG, fg=GREEN,
            font=("Consolas", 10, "bold")
        )
        self.status.pack(anchor="e")
        self.metrics = tk.Label(
            right, text="CPU --%   RAM --%   DISK --%", bg=BG, fg=MUTED,
            font=("Consolas", 9)
        )
        self.metrics.pack(anchor="e", pady=(5, 0))

    def _build_dashboard(self):
        dashboard = tk.Frame(self.root, bg=BG)
        dashboard.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        dashboard.grid_columnconfigure(0, weight=1, uniform="dash")
        dashboard.grid_columnconfigure(1, weight=2, uniform="dash")
        dashboard.grid_columnconfigure(2, weight=1, uniform="dash")
        dashboard.grid_rowconfigure(0, weight=1)

        left_outer, left = self._panel(dashboard, "Subsystems")
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._subsystem_labels = {}
        for key, label, state in (
            ("core", "CORE INTELLIGENCE", "STANDBY"),
            ("voice", "VOICE INTERFACE", "READY"),
            ("vision", "SCREEN ANALYSIS", "ON DEMAND"),
            ("camera", "CAMERA / FACE", "OFF"),
            ("gesture", "GESTURE INPUT", "OFF"),
            ("memory", "LOCAL MEMORY", "READY"),
            ("defense", "SYSTEM SECURITY", "MONITORING"),
            ("ev", "E.V. SENSOR INTELLIGENCE", "ON DEMAND"),
            ("friday", "F.R.I.D.A.Y. ANALYSIS", "ON DEMAND"),
            ("morpheus", "MORPHEUS DEFENSE", "READY"),
            ("ultron", "ULTRON STRATEGIC CORE", "ON DEMAND"),
        ):
            row = tk.Frame(left, bg=PANEL)
            row.pack(fill="x", pady=5)
            dot = tk.Label(row, text="◆", bg=PANEL, fg=CYAN_DIM, font=("Segoe UI", 9))
            dot.pack(side="left")
            text_box = tk.Frame(row, bg=PANEL)
            text_box.pack(side="left", fill="x", expand=True, padx=(7, 0))
            tk.Label(
                text_box, text=label, bg=PANEL, fg=TEXT,
                font=("Segoe UI", 8, "bold"), anchor="w"
            ).pack(fill="x")
            value = tk.Label(
                text_box, text=state, bg=PANEL, fg=MUTED,
                font=("Consolas", 8), anchor="w"
            )
            value.pack(fill="x")
            self._subsystem_labels[key] = (dot, value)

        center_outer, center = self._panel(dashboard, "Arc reactor / activity core")
        center_outer.grid(row=0, column=1, sticky="nsew", padx=4)
        center.configure(padx=8, pady=8)
        self.core_canvas = tk.Canvas(
            center, bg=PANEL, highlightthickness=0, height=330
        )
        self.core_canvas.pack(fill="both", expand=True)
        self.core_canvas.bind("<Configure>", lambda _event: self._draw_core())
        self._draw_core()
        self.core_caption = tk.Label(
            center, text="AWAITING COMMAND", bg=PANEL, fg=CYAN,
            font=("Consolas", 10, "bold")
        )
        self.core_caption.pack(pady=(4, 2))
        tk.Label(
            center, text="LOCAL PROCESSING  •  USER-CONTROLLED SYSTEMS",
            bg=PANEL, fg=MUTED, font=("Consolas", 7)
        ).pack(pady=(0, 4))

        right_outer, right = self._panel(dashboard, "Live telemetry")
        right_outer.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self._metric_bars = {}
        for key, label in (("cpu", "CPU LOAD"), ("ram", "SYSTEM MEMORY"), ("disk", "SYSTEM DRIVE"), ("process", "JARVIS PROCESS RAM")):
            tk.Label(
                right, text=label, bg=PANEL, fg=TEXT,
                font=("Consolas", 8, "bold"), anchor="w"
            ).pack(fill="x", pady=(8, 3))
            bar = tk.Canvas(right, height=8, bg=PANEL_ALT, highlightthickness=0)
            bar.pack(fill="x")
            fill = bar.create_rectangle(0, 0, 0, 8, fill=CYAN, width=0)
            self._metric_bars[key] = (bar, fill)
        tk.Label(
            right, text="MICROPHONE INPUT", bg=PANEL, fg=TEXT,
            font=("Consolas", 8, "bold"), anchor="w"
        ).pack(fill="x", pady=(18, 4))
        self.mic_meter = tk.Canvas(right, height=10, bg=PANEL_ALT, highlightthickness=0)
        self.mic_meter.pack(fill="x")
        self._mic_bar = self.mic_meter.create_rectangle(0, 0, 0, 10, fill=GREEN, width=0)
        self.face_status = tk.Label(
            right, text="CAMERA OFF • FACE DETECTION ONLY", bg=PANEL,
            fg=MUTED, font=("Consolas", 8), wraplength=190, justify="left"
        )
        self.face_status.pack(fill="x", pady=(18, 4))
        self.gesture_status = tk.Label(
            right, text="HAND GESTURES OFF", bg=PANEL, fg=MUTED,
            font=("Consolas", 8), wraplength=190, justify="left"
        )
        self.gesture_status.pack(fill="x", pady=4)

    def _draw_core(self):
        """Render the reactor at 3x resolution and downsample for smooth edges."""
        if not hasattr(self, "core_canvas"):
            return
        from PIL import Image, ImageDraw, ImageFont, ImageTk

        canvas = self.core_canvas
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), 260)
        scale = 2
        image = Image.new("RGBA", (width * scale, height * scale), PANEL)
        draw = ImageDraw.Draw(image)
        cx, cy = width * scale / 2, height * scale / 2
        radius = min(width, height) * 0.34 * scale

        def box(r):
            return (cx-r, cy-r, cx+r, cy+r)

        for factor, color, stroke in (
            (1.34, LINE, 1), (1.12, CYAN_DIM, 1), (0.91, LINE, 2),
            (0.72, CYAN_DIM, 1), (0.48, CYAN, 2), (0.24, LINE, 1)
        ):
            r = radius * factor
            draw.ellipse(box(r), outline=color, width=max(1, stroke * scale))

        for i in range(48):
            angle = math.radians(i * 7.5)
            inner = radius * (1.18 if i % 4 == 0 else 1.23)
            outer = radius * (1.34 if i % 4 == 0 else 1.29)
            draw.line(
                (cx + math.cos(angle)*inner, cy + math.sin(angle)*inner,
                 cx + math.cos(angle)*outer, cy + math.sin(angle)*outer),
                fill=CYAN_DIM if i % 4 == 0 else LINE,
                width=2 * scale if i % 4 == 0 else scale
            )

        sweep_radius = radius * 1.12
        draw.arc(
            (cx-sweep_radius, cy-sweep_radius, cx+sweep_radius, cy+sweep_radius),
            start=self._phase, end=self._phase + 48,
            fill=CYAN, width=2 * scale
        )
        try:
            big_font = ImageFont.truetype("segoeuib.ttf", max(12, int(radius * 0.72)))
            small_font = ImageFont.truetype("consolab.ttf", max(10, int(9 * scale)))
        except OSError:
            big_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        draw.text((cx, cy - radius*0.08), "J", fill=CYAN, font=big_font, anchor="mm")
        draw.text((cx, cy + radius*0.56), "J.A.R.V.I.S.", fill=TEXT, font=small_font, anchor="mm")

        smooth = image.resize((width, height), Image.Resampling.LANCZOS)
        self._core_photo = ImageTk.PhotoImage(smooth)
        canvas.delete("all")
        canvas.create_image(width / 2, height / 2, image=self._core_photo, anchor="center")

    def _build_activity(self):
        outer, inner = self._panel(self.root, "System activity / conversation")
        outer.pack(fill="both", expand=False, padx=22, pady=(0, 10))
        self.log = tk.Text(
            inner, height=6, bg="#06111d", fg=TEXT, insertbackground=CYAN,
            wrap="word", font=("Consolas", 9), bd=0, padx=10, pady=8,
            selectbackground=CYAN_DIM
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("who", foreground=CYAN, font=("Consolas", 9, "bold"))
        self.log.tag_configure("body", foreground=TEXT)

    def _build_controls(self):
        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=22, pady=(0, 16))

        # Give text input its own full-width row so it remains easy to find/use.
        tk.Label(
            controls, text="MESSAGE INPUT", bg=BG, fg=CYAN_DIM,
            font=("Consolas", 8, "bold"), anchor="w"
        ).pack(fill="x", pady=(0, 5))
        input_row = tk.Frame(controls, bg=BG)
        input_row.pack(fill="x", pady=(0, 8))
        self._entry_placeholder = "Type a message here..."
        self.entry = tk.Entry(
            input_row, bg=PANEL_ALT, fg=MUTED, insertbackground=CYAN,
            font=("Segoe UI", 12), bd=0, relief="flat"
        )
        self.entry.insert(0, self._entry_placeholder)
        self.entry.pack(side="left", fill="x", expand=True, ipady=13, padx=(0, 8))
        self.entry.bind("<Return>", lambda _event: self.send())
        self.entry.bind("<FocusIn>", self._clear_entry_placeholder)
        self.entry.bind("<FocusOut>", self._restore_entry_placeholder)
        self._button(input_row, "SEND", self.send, primary=True)

        action_row = tk.Frame(controls, bg=BG)
        action_row.pack(fill="x")
        self._button(action_row, "VOICE / TALK", self._voice_action)
        self._button(action_row, "SCREEN", self._vision_action)
        self._button(action_row, "STOP AUDIO", self._stop_action)
        self._wake_button = self._button(
            action_row, "WAKE: OFF", lambda: self.on_toggle_wake(not self._wake_enabled)
        )
        self._face_button = self._button(
            action_row, "FACE: OFF", lambda: self.on_toggle_face(not self._face_enabled)
        )
        self._gesture_button = self._button(
            action_row, "GESTURES: OFF",
            lambda: self.on_toggle_gestures(not self._gestures_enabled)
        )

    def _clear_entry_placeholder(self, _event=None):
        if self.entry.get() == self._entry_placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=TEXT)

    def _restore_entry_placeholder(self, _event=None):
        if not self.entry.get().strip():
            self.entry.insert(0, self._entry_placeholder)
            self.entry.configure(fg=MUTED)

    def _voice_action(self):
        self.on_voice()

    def _vision_action(self):
        self.core_caption.configure(text="SCREEN ANALYSIS REQUESTED")
        self.on_vision()

    def _stop_action(self):
        self.on_stop_speaking()

    def _button(self, parent, label, command, primary=False):
        button = tk.Button(
            parent, text=label, command=command,
            bg=CYAN_DIM if primary else PANEL_ALT,
            fg=BG if primary else CYAN,
            activebackground=CYAN, activeforeground=BG,
            bd=0, relief="flat", padx=10, pady=9,
            font=("Segoe UI", 8, "bold"), cursor="hand2"
        )
        button.pack(side="left", padx=(0, 5))
        return button

    def add(self, who, text):
        self.log.configure(state="normal")
        self.log.insert("end", f"{who}  ", "who")
        self.log.insert("end", f"{text}\n", "body")
        self.log.see("end")
        self.log.configure(state="disabled")

    def send(self):
        text = self.entry.get().strip()
        if text and text != self._entry_placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=TEXT)
            self.add("YOU", text)
            self.core_caption.configure(text="PROCESSING REQUEST")
            self.on_send(text)

    def set_status(self, text):
        text = str(text)
        color = RED if "ERROR" in text else GREEN
        if any(word in text for word in ("LISTENING", "WAKE", "SPEAKING", "WORKING")):
            color = AMBER
        self.status.configure(text=f"● {text}", fg=color)
        if hasattr(self, "core_caption"):
            self.core_caption.configure(text=text.upper()[:42])

    def set_mic_level(self, level):
        self._mic_level = max(0.0, min(1.0, float(level)))
        width = max(1, self.mic_meter.winfo_width())
        self.mic_meter.coords(self._mic_bar, 0, 0, width * self._mic_level, 10)

    def set_wake_state(self, enabled):
        self._wake_enabled = bool(enabled)
        self._wake_button.configure(
            text="WAKE: ON" if enabled else "WAKE: OFF",
            fg=AMBER if enabled else CYAN
        )
        self._set_subsystem("voice", "WAKE LISTENER ACTIVE" if enabled else "READY")

    def set_face_state(self, enabled):
        self._face_enabled = bool(enabled)
        self._face_button.configure(
            text="FACE: ON" if enabled else "FACE: OFF",
            fg=AMBER if enabled else CYAN
        )
        self.set_face_status(
            "CAMERA STARTING • FACE DETECTION ONLY" if enabled
            else "CAMERA OFF • FACE DETECTION ONLY"
        )
        self._set_subsystem("camera", "STARTING" if enabled else "OFF")

    def set_face_count(self, count):
        if self._face_enabled:
            self.set_face_status(f"CAMERA ACTIVE • {int(count)} FACE(S) DETECTED")

    def set_face_status(self, text):
        text = str(text)
        color = RED if "ERROR" in text else (MUTED if "OFF" in text else AMBER)
        self.face_status.configure(text=text, fg=color)

    def set_gesture_state(self, enabled):
        self._gestures_enabled = bool(enabled)
        self._gesture_button.configure(
            text="GESTURES: ON" if enabled else "GESTURES: OFF",
            fg=AMBER if enabled else CYAN
        )
        self.set_gesture_status(
            "HAND GESTURES STARTING" if enabled else "HAND GESTURES OFF"
        )
        self._set_subsystem("gesture", "STARTING" if enabled else "OFF")

    def set_gesture_status(self, text):
        text = str(text)
        color = RED if "ERROR" in text else (MUTED if "OFF" in text else AMBER)
        self.gesture_status.configure(text=text, fg=color)

    def set_gesture(self, label):
        if self._gestures_enabled:
            self.set_gesture_status(f"GESTURE • {label}")

    def _set_subsystem(self, key, value):
        if key in getattr(self, "_subsystem_labels", {}):
            dot, label = self._subsystem_labels[key]
            label.configure(text=value, fg=AMBER if value not in ("OFF", "READY") else MUTED)
            dot.configure(fg=GREEN if value in ("READY", "MONITORING") else CYAN_DIM)

    def set_module_status(self, module, value):
        """Update one subsystem indicator from the central request router."""
        keys = {
            "JARVIS": "core",
            "E.V.": "ev",
            "F.R.I.D.A.Y.": "friday",
            "MORPHEUS": "morpheus",
            "ULTRON": "ultron",
        }
        key = keys.get(str(module).upper() if module != "E.V." else "E.V.")
        if key:
            state = str(value).upper()[:28]
            self._set_subsystem(key, state)

    def confirm_action(self, description):
        if threading.current_thread() is self._tk_thread:
            return messagebox.askyesno(
                "JARVIS action approval", str(description), parent=self.root
            )
        completed = threading.Event()
        outcome = {}

        def show_dialog():
            try:
                outcome["approved"] = messagebox.askyesno(
                    "JARVIS action approval", str(description), parent=self.root
                )
            except Exception as exc:
                outcome["error"] = exc
            finally:
                completed.set()

        self.root.after(0, show_dialog)
        if not completed.wait(timeout=120):
            return False
        if "error" in outcome:
            raise RuntimeError(f"Could not show action approval dialog: {outcome['error']}")
        return outcome["approved"]

    def dispatch(self, function, *args):
        self.root.after(0, function, *args)

    def _animate(self):
        self._phase = (self._phase + 5) % 360
        self.reactor.itemconfigure("pulse", start=self._phase)
        if hasattr(self, "core_canvas"):
            self._draw_core()
        # 10 FPS keeps the HUD smooth while reducing continuous CPU work.
        self.root.after(100, self._animate)

    def _set_bar(self, key, value):
        canvas, item = self._metric_bars[key]
        width = max(canvas.winfo_width(), 1)
        amount = max(0.0, min(100.0, float(value)))
        color = RED if amount >= 90 else (AMBER if amount >= 75 else CYAN)
        canvas.coords(item, 0, 0, width * amount / 100.0, 8)
        canvas.itemconfigure(item, fill=color)

    def _refresh_metrics(self):
        try:
            drive = os.environ.get("SystemDrive", "C:")
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage(drive).percent
            self.metrics.configure(
                text=f"CPU {cpu:.0f}%   RAM {ram:.0f}%   DISK {disk:.0f}%"
            )
            self._set_bar("cpu", cpu)
            self._set_bar("ram", ram)
            self._set_bar("disk", disk)
            process_gb = psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3)
            self._set_bar("process", min(100.0, process_gb / 2.0 * 100.0))
            self.metrics.configure(
                text=f"CPU {cpu:.0f}%   RAM {ram:.0f}%   DISK {disk:.0f}%   JARVIS {process_gb:.2f} GB"
            )
        except Exception as exc:
            self.metrics.configure(text=f"TELEMETRY ERROR: {exc}")
        self.root.after(2000, self._refresh_metrics)

    def run(self):
        self.root.mainloop()
