"""Tkinter dashboard for the Smarter Cities traffic demonstration."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from simulation import TrafficSimulation
from traffic_model import DIRECTIONS, load_or_create_training_data, train_model


PROJECT_DIR = Path(__file__).resolve().parent


class TrafficDashboard:
    BG = "#101820"
    PANEL = "#182631"
    PANEL_LIGHT = "#203442"
    TEXT = "#e6f1f5"
    MUTED = "#8ea8b2"
    ACCENT = "#42d6c5"
    GREEN = "#43e08d"
    YELLOW = "#f9c74f"
    RED = "#fa6477"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Smarter Cities | Smoother Traffic")
        self.root.geometry("1280x840")
        self.root.minsize(1050, 720)
        self.root.configure(bg=self.BG)

        training_data = load_or_create_training_data(PROJECT_DIR / "data" / "traffic_training_data.csv")
        self.model = train_model(training_data)
        self.simulation = TrafficSimulation(self.model)
        self.running = False
        self.refresh_job = None
        self.cards = {}
        self._configure_style()
        self._build_layout()
        self._refresh()
        self._schedule_refresh()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dashboard.TButton", font=("Helvetica", 11, "bold"), padding=(14, 9), background=self.PANEL_LIGHT, foreground=self.TEXT, borderwidth=0)
        style.map("Dashboard.TButton", background=[("active", self.ACCENT)], foreground=[("active", "#071316")])
        style.configure("Treeview", background=self.PANEL, fieldbackground=self.PANEL, foreground=self.TEXT, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=self.PANEL_LIGHT, foreground=self.ACCENT, font=("Helvetica", 10, "bold"), borderwidth=0)

    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg=self.BG)
        header.pack(fill="x", padx=28, pady=(22, 12))
        tk.Label(header, text="SMART TRAFFIC CONTROL", font=("Helvetica", 24, "bold"), fg=self.TEXT, bg=self.BG).pack(anchor="w")
        tk.Label(header, text="AI-powered intersection optimization  /  real-time simulation", font=("Helvetica", 11), fg=self.MUTED, bg=self.BG).pack(anchor="w", pady=(3, 0))

        self.cards_frame = tk.Frame(self.root, bg=self.BG)
        self.cards_frame.pack(fill="x", padx=28, pady=(0, 14))
        for direction in DIRECTIONS:
            card = tk.Frame(self.cards_frame, bg=self.PANEL, padx=16, pady=12, highlightthickness=1, highlightbackground="#29424d")
            card.pack(side="left", fill="both", expand=True, padx=(0, 10 if direction != "WEST" else 0))
            tk.Label(card, text=direction, font=("Helvetica", 10, "bold"), fg=self.ACCENT, bg=self.PANEL).pack(anchor="w")
            count_label = tk.Label(card, text="0", font=("Helvetica", 25, "bold"), fg=self.TEXT, bg=self.PANEL)
            count_label.pack(anchor="w")
            tk.Label(card, text="vehicles", font=("Helvetica", 9), fg=self.MUTED, bg=self.PANEL).pack(anchor="w")
            status_label = tk.Label(card, text="RED", font=("Helvetica", 10, "bold"), fg=self.RED, bg=self.PANEL)
            status_label.pack(anchor="w", pady=(8, 0))
            congestion_label = tk.Label(card, text="LOW", font=("Helvetica", 9, "bold"), fg=self.MUTED, bg=self.PANEL)
            congestion_label.pack(anchor="w")
            self.cards[direction] = {"count": count_label, "status": status_label, "congestion": congestion_label}

        content = tk.Frame(self.root, bg=self.BG)
        content.pack(fill="both", expand=True, padx=28)
        left = tk.Frame(content, bg=self.PANEL, padx=14, pady=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))
        tk.Label(left, text="LIVE JUNCTION", font=("Helvetica", 11, "bold"), fg=self.ACCENT, bg=self.PANEL).pack(anchor="w")
        self.intersection = tk.Canvas(left, bg="#10181e", highlightthickness=0)
        self.intersection.pack(fill="both", expand=True, pady=(8, 0))

        right = tk.Frame(content, bg=self.BG, width=390)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_recommendation(right)
        self._build_metrics(right)
        self._build_chart(right)

        controls = tk.Frame(self.root, bg=self.BG)
        controls.pack(fill="x", padx=28, pady=(14, 5))
        self.start_button = ttk.Button(controls, text="START SIMULATION", style="Dashboard.TButton", command=self.toggle_simulation)
        self.start_button.pack(side="left")
        ttk.Button(controls, text="ADD TRAFFIC", style="Dashboard.TButton", command=self.add_traffic).pack(side="left", padx=10)
        ttk.Button(controls, text="AI OPTIMIZE", style="Dashboard.TButton", command=self.optimize).pack(side="left")
        tk.Label(controls, text="SIM SPEED", font=("Helvetica", 9, "bold"), fg=self.MUTED, bg=self.BG).pack(side="left", padx=(14, 5))
        self.speed_multiplier = tk.DoubleVar(value=1.0)
        self.speed_selector = ttk.Combobox(
            controls,
            textvariable=self.speed_multiplier,
            values=("0.5", "1.0", "2.0", "4.0"),
            state="readonly",
            width=5,
        )
        self.speed_selector.pack(side="left")
        self.speed_selector.set("1.0")
        self.manual_button = ttk.Button(controls, text="ENABLE MANUAL", style="Dashboard.TButton", command=self.toggle_manual_control)
        self.manual_button.pack(side="left", padx=(10, 4))
        self.manual_direction_buttons = {}
        for direction in DIRECTIONS:
            button = ttk.Button(controls, text=direction, style="Dashboard.TButton", command=lambda selected=direction: self.set_manual_direction(selected))
            button.pack(side="left", padx=2)
            self.manual_direction_buttons[direction] = button
        ttk.Button(controls, text="RESET", style="Dashboard.TButton", command=self.reset).pack(side="right")

        advanced = tk.Frame(self.root, bg=self.BG)
        advanced.pack(fill="x", padx=28, pady=(0, 14))
        self.auto_ai_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced, text="AUTO AI MODE", variable=self.auto_ai_var, command=self.toggle_auto_ai).pack(side="left")
        tk.Label(advanced, text="WEATHER", font=("Helvetica", 9, "bold"), fg=self.MUTED, bg=self.BG).pack(side="left", padx=(18, 5))
        self.weather_selector = ttk.Combobox(advanced, values=("CLEAR", "RAIN", "FOG"), state="readonly", width=8)
        self.weather_selector.set("CLEAR")
        self.weather_selector.pack(side="left")
        self.weather_selector.bind("<<ComboboxSelected>>", lambda _event: self.set_weather())
        tk.Label(advanced, text="DEMO SCENARIO", font=("Helvetica", 9, "bold"), fg=self.MUTED, bg=self.BG).pack(side="left", padx=(18, 5))
        self.scenario_selector = ttk.Combobox(advanced, values=("Normal Traffic", "Rush Hour", "Emergency Vehicle", "Road Incident", "Heavy Rain"), state="readonly", width=18)
        self.scenario_selector.set("Normal Traffic")
        self.scenario_selector.pack(side="left")
        self.scenario_selector.bind("<<ComboboxSelected>>", lambda _event: self.apply_scenario())
        tk.Label(advanced, text="EMERGENCY", font=("Helvetica", 9, "bold"), fg=self.MUTED, bg=self.BG).pack(side="left", padx=(18, 5))
        for direction in DIRECTIONS:
            ttk.Button(advanced, text=direction[0], width=3, command=lambda selected=direction: self.trigger_emergency(selected)).pack(side="left", padx=1)
        ttk.Button(advanced, text="CLEAR INCIDENT", style="Dashboard.TButton", command=self.clear_incident).pack(side="right")

    def _build_recommendation(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=self.PANEL, padx=16, pady=14)
        panel.pack(fill="x", pady=(0, 12))
        tk.Label(panel, text="AI RECOMMENDATION", font=("Helvetica", 11, "bold"), fg=self.ACCENT, bg=self.PANEL).pack(anchor="w")
        self.recommendation = tk.Label(panel, text="Analyzing traffic...", font=("Helvetica", 13, "bold"), fg=self.TEXT, bg=self.PANEL, justify="left", wraplength=350)
        self.recommendation.pack(anchor="w", pady=(9, 3))
        tk.Label(
            panel,
            text="AI analyzes traffic demand and waiting time, then gives busier directions longer green time.",
            font=("Helvetica", 9),
            fg=self.MUTED,
            bg=self.PANEL,
            justify="left",
            wraplength=350,
        ).pack(anchor="w", pady=(0, 8))
        self.mode_label = tk.Label(panel, text="FIXED SIGNAL MODE", font=("Helvetica", 9, "bold"), fg=self.YELLOW, bg=self.PANEL)
        self.mode_label.pack(anchor="w")
        self.engine_label = tk.Label(panel, text="AI ENGINE: READY", font=("Helvetica", 9, "bold"), fg=self.GREEN, bg=self.PANEL)
        self.engine_label.pack(anchor="w", pady=(8, 0))
        self.explain_label = tk.Label(panel, text="", font=("Courier", 9), fg=self.TEXT, bg=self.PANEL, justify="left", anchor="w")
        self.explain_label.pack(anchor="w", pady=(8, 0))
        self.forecast_label = tk.Label(panel, text="TRAFFIC FORECAST\n--", font=("Courier", 9), fg=self.TEXT, bg=self.PANEL, justify="left", anchor="w")
        self.forecast_label.pack(anchor="w", pady=(8, 0))
        tk.Label(panel, text="AI WORKFLOW  DATA > PREDICT > PRIORITIZE > OPTIMIZE > RESPOND", font=("Helvetica", 8, "bold"), fg=self.MUTED, bg=self.PANEL, wraplength=350, justify="left").pack(anchor="w", pady=(8, 0))
        tk.Label(panel, text="AI DECISION LOG", font=("Helvetica", 9, "bold"), fg=self.ACCENT, bg=self.PANEL).pack(anchor="w", pady=(10, 3))
        self.log_text = tk.Text(panel, height=4, width=42, bg=self.PANEL_LIGHT, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", font=("Courier", 8), state="disabled")
        self.log_text.pack(fill="x")

    def _build_metrics(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=self.PANEL, padx=16, pady=14)
        panel.pack(fill="x", pady=(0, 12))
        tk.Label(panel, text="LIVE METRICS", font=("Helvetica", 11, "bold"), fg=self.ACCENT, bg=self.PANEL).pack(anchor="w")
        self.metrics = {}
        for name in ("Congestion", "Waiting time", "Queue length", "Total vehicles", "Vehicles cleared", "Estimated emission reduction"):
            row = tk.Frame(panel, bg=self.PANEL)
            row.pack(fill="x", pady=(10, 0))
            tk.Label(row, text=name, font=("Helvetica", 9), fg=self.MUTED, bg=self.PANEL).pack(side="left")
            value = tk.Label(row, text="--", font=("Helvetica", 10, "bold"), fg=self.TEXT, bg=self.PANEL)
            value.pack(side="right")
            self.metrics[name] = value

        compare = tk.Frame(panel, bg=self.PANEL_LIGHT, padx=10, pady=8)
        compare.pack(fill="x", pady=(14, 0))
        tk.Label(compare, text="MODE COMPARISON", font=("Helvetica", 9, "bold"), fg=self.ACCENT, bg=self.PANEL_LIGHT).pack(anchor="w")
        self.comparison_label = tk.Label(compare, text="", font=("Courier", 9), fg=self.TEXT, bg=self.PANEL_LIGHT, justify="left", anchor="w")
        self.comparison_label.pack(anchor="w", pady=(5, 0))
        self.performance_label = tk.Label(compare, text="AI PERFORMANCE\nWaiting improvement: --\nIdle reduction: --", font=("Courier", 8), fg=self.TEXT, bg=self.PANEL_LIGHT, justify="left", anchor="w")
        self.performance_label.pack(anchor="w", pady=(8, 0))

    def _build_chart(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=self.PANEL, padx=10, pady=10)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="TRAFFIC / CONGESTION TREND", font=("Helvetica", 10, "bold"), fg=self.ACCENT, bg=self.PANEL).pack(anchor="w")
        self.figure = Figure(figsize=(4.0, 2.1), dpi=100, facecolor=self.PANEL)
        self.axis = self.figure.add_subplot(111)
        self.chart = FigureCanvasTkAgg(self.figure, master=panel)
        self.chart.get_tk_widget().pack(fill="both", expand=True, pady=(6, 0))

    def toggle_simulation(self) -> None:
        self.running = not self.running
        self.start_button.configure(text="PAUSE SIMULATION" if self.running else "START SIMULATION")

    def add_traffic(self) -> None:
        self.simulation.add_traffic()
        self._refresh()

    def optimize(self) -> None:
        self.simulation.optimize()
        self.manual_button.configure(text="ENABLE MANUAL")
        self._refresh()

    def toggle_auto_ai(self) -> None:
        self.simulation.set_auto_ai(self.auto_ai_var.get())
        self._refresh()

    def set_weather(self) -> None:
        self.simulation.set_weather(self.weather_selector.get())
        self._refresh()

    def apply_scenario(self) -> None:
        self.simulation.apply_scenario(self.scenario_selector.get())
        self.auto_ai_var.set(self.simulation.auto_ai)
        self.weather_selector.set(self.simulation.weather)
        self._refresh()

    def trigger_emergency(self, direction: str) -> None:
        self.simulation.trigger_emergency(direction)
        self._refresh()

    def clear_incident(self) -> None:
        self.simulation.clear_incident()
        self.simulation.update_predictions()
        self._refresh()

    def toggle_manual_control(self) -> None:
        enabled = not self.simulation.manual_control
        self.simulation.set_manual_control(enabled)
        self.manual_button.configure(text="DISABLE MANUAL" if enabled else "ENABLE MANUAL")
        self._refresh()

    def set_manual_direction(self, direction: str) -> None:
        self.simulation.set_manual_direction(direction)
        self.manual_button.configure(text="DISABLE MANUAL")
        self._refresh()

    def reset(self) -> None:
        self.running = False
        self.start_button.configure(text="START SIMULATION")
        self.simulation.reset()
        self.auto_ai_var.set(False)
        self.weather_selector.set("CLEAR")
        self.scenario_selector.set("Normal Traffic")
        self.manual_button.configure(text="ENABLE MANUAL")
        self._refresh()

    def _schedule_refresh(self) -> None:
        if self.refresh_job is None:
            self.refresh_job = self.root.after(500, self._run_refresh)

    def _run_refresh(self) -> None:
        self.refresh_job = None
        self._refresh()
        self._schedule_refresh()

    def _refresh(self) -> None:
        if self.running:
            self.simulation.update(seconds=0.5 * self.speed_multiplier.get())
        self._refresh_cards()
        self._refresh_intersection()
        self._refresh_metrics()
        self._refresh_chart()

    def _refresh_cards(self) -> None:
        for direction, state in self.simulation.states.items():
            card = self.cards[direction]
            card["count"].configure(text=str(state.vehicle_count))
            status = self.simulation.signal_status(direction)
            status_color = {"GREEN": self.GREEN, "YELLOW": self.YELLOW, "RED": self.RED}[status]
            card["status"].configure(text=status, fg=status_color)
            congestion_color = {"LOW": self.GREEN, "MEDIUM": self.YELLOW, "HIGH": self.RED}[state.congestion]
            card["congestion"].configure(text=state.congestion + " congestion", fg=congestion_color)

    def _refresh_intersection(self) -> None:
        canvas = self.intersection
        canvas.delete("all")
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 360)
        center_x, center_y = width / 2, height / 2
        road_width = min(width, height) * 0.31
        canvas.create_rectangle(0, center_y - road_width / 2, width, center_y + road_width / 2, fill="#26343a", outline="")
        canvas.create_rectangle(center_x - road_width / 2, 0, center_x + road_width / 2, height, fill="#26343a", outline="")
        for offset in (-road_width / 6, road_width / 6):
            canvas.create_line(0, center_y + offset, width, center_y + offset, fill="#68777c", dash=(12, 13), width=2)
            canvas.create_line(center_x + offset, 0, center_x + offset, height, fill="#68777c", dash=(12, 13), width=2)
        canvas.create_rectangle(center_x - road_width / 2, center_y - road_width / 2, center_x + road_width / 2, center_y + road_width / 2, fill="#202c31", outline="#46616a")
        canvas.create_text(center_x, center_y, text="4-WAY\nJUNCTION", fill="#8da9b1", font=("Helvetica", 10, "bold"))
        stop_line_gap = 14
        north_stop_y = center_y - road_width / 2 - stop_line_gap
        south_stop_y = center_y + road_width / 2 + stop_line_gap
        east_stop_x = center_x + road_width / 2 + stop_line_gap
        west_stop_x = center_x - road_width / 2 - stop_line_gap
        # Tell the simulation where each approach's stop line sits (0..1 along the
        # approach) so waiting vehicles queue behind it instead of in the junction.
        self.simulation.stop_fraction = {
            "NORTH": 1 - south_stop_y / height,
            "SOUTH": north_stop_y / height,
            "EAST": west_stop_x / width,
            "WEST": 1 - east_stop_x / width,
        }
        canvas.create_line(
            center_x - road_width / 2,
            north_stop_y,
            center_x + road_width / 2,
            north_stop_y,
            fill="#f4f7f8",
            width=3,
        )
        canvas.create_line(
            center_x - road_width / 2,
            south_stop_y,
            center_x + road_width / 2,
            south_stop_y,
            fill="#f4f7f8",
            width=3,
        )
        canvas.create_line(
            east_stop_x,
            center_y - road_width / 2,
            east_stop_x,
            center_y + road_width / 2,
            fill="#f4f7f8",
            width=3,
        )
        canvas.create_line(
            west_stop_x,
            center_y - road_width / 2,
            west_stop_x,
            center_y + road_width / 2,
            fill="#f4f7f8",
            width=3,
        )

        positions = {
            "NORTH": (center_x - 40, center_y - road_width / 2 - 25),
            "SOUTH": (center_x + 40, center_y + road_width / 2 + 25),
            "EAST": (center_x + road_width / 2 + 25, center_y - 40),
            "WEST": (center_x - road_width / 2 - 25, center_y + 40),
        }
        for direction, (signal_x, signal_y) in positions.items():
            status = self.simulation.signal_status(direction)
            color = {"GREEN": self.GREEN, "YELLOW": self.YELLOW, "RED": self.RED}[status]
            canvas.create_oval(signal_x - 10, signal_y - 10, signal_x + 10, signal_y + 10, fill=color, outline="#d8edf0", width=2)
            canvas.create_text(signal_x, signal_y + (23 if direction in ("NORTH", "SOUTH") else 0), text=direction, fill=self.TEXT, font=("Helvetica", 8, "bold"))

        for direction, state in self.simulation.states.items():
            for vehicle in state.vehicles:
                self._draw_vehicle(canvas, direction, vehicle, center_x, center_y, road_width, width, height)

    @staticmethod
    def _draw_vehicle(canvas, direction, vehicle, center_x, center_y, road_width, width, height) -> None:
        # The simulation already holds waiting vehicles behind the stop line, so
        # the drawing just maps the approach position (0..1) onto the canvas.
        lane_shift = -road_width * 0.18 if vehicle.lane == 0 else road_width * 0.18
        position = min(max(vehicle.position, 0.0), 1.05)
        if direction == "NORTH":
            x, y = center_x + lane_shift, height * (1 - position)
            box = (x - 5, y - 10, x + 5, y + 10)
        elif direction == "SOUTH":
            x, y = center_x + lane_shift, height * position
            box = (x - 5, y - 10, x + 5, y + 10)
        elif direction == "EAST":
            x, y = width * position, center_y + lane_shift
            box = (x - 10, y - 5, x + 10, y + 5)
        else:
            x, y = width * (1 - position), center_y + lane_shift
            box = (x - 10, y - 5, x + 10, y + 5)
        canvas.create_rectangle(*box, fill=vehicle.color, outline="")

    def _refresh_metrics(self) -> None:
        simulation = self.simulation
        congestion_text = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}.get(round(simulation.average_congestion), "MEDIUM")
        self.metrics["Congestion"].configure(text=congestion_text)
        self.metrics["Waiting time"].configure(text=f"{simulation.average_waiting_time:.1f} s")
        self.metrics["Queue length"].configure(text=f"{sum(state.queue_length for state in simulation.states.values()):.0f}")
        self.metrics["Total vehicles"].configure(text=str(simulation.total_vehicles))
        self.metrics["Vehicles cleared"].configure(text=str(simulation.vehicles_cleared))
        self.metrics["Estimated emission reduction"].configure(text=f"{simulation.emission_reduction:.1f}%")
        self.recommendation.configure(text=f"{simulation.priority} -> PRIORITY\nRecommended green: {simulation.green_durations[simulation.priority]} seconds")
        self.mode_label.configure(text=simulation.mode, fg=self.ACCENT if simulation.mode.startswith("AI") else self.YELLOW)
        if simulation.emergency_direction:
            self.engine_label.configure(text=f"EMERGENCY PRIORITY: {simulation.emergency_direction}", fg=self.RED)
        else:
            self.engine_label.configure(text=f"AI ENGINE: ACTIVE  |  {simulation.predictions[simulation.priority]} ({simulation.confidences[simulation.priority] * 100:.0f}%)", fg=self.GREEN)
        chosen = simulation.states[simulation.priority]
        self.explain_label.configure(text=(f"WHY {simulation.priority}?\nVehicles: {chosen.vehicle_count}   Waiting: {chosen.waiting_time:.1f}s\n"
                                           f"Density: {chosen.traffic_density:.2f}   Queue: {chosen.queue_length:.0f}\n"
                                           f"Prediction: {simulation.predictions[simulation.priority]}   Confidence: {simulation.confidences[simulation.priority] * 100:.0f}%\n"
                                           f"Decision: {'Emergency passage' if chosen.emergency else 'Extend green time'}"))
        self.forecast_label.configure(text="TRAFFIC FORECAST\n" + "\n".join(f"Next {seconds} sec: {label}" for seconds, label in zip((30, 60, 90), simulation.forecast)))
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "\n".join(simulation.decision_log[-5:]))
        self.log_text.configure(state="disabled")
        comparison = simulation.comparison()
        self.comparison_label.configure(
            text=(
                f"                 FIXED       AI\n"
                f"Wait total     {comparison['fixed']['wait']:5.1f}s    {comparison['optimized']['wait']:5.1f}s\n"
                f"Avg congestion  {comparison['fixed']['congestion']:5.1f}       {comparison['optimized']['congestion']:5.1f}\n"
                f"Idle time       {comparison['fixed']['idle']:5.0f}       {comparison['optimized']['idle']:5.0f}\n"
                f"Cleared         {comparison['fixed']['cleared']:5.0f}       {comparison['optimized']['cleared']:5.0f}"
            )
        )
        fixed_wait = comparison["fixed"]["wait"]
        ai_wait = comparison["optimized"]["wait"]
        fixed_idle = comparison["fixed"]["idle"]
        ai_idle = comparison["optimized"]["idle"]
        wait_improvement = max(0.0, (fixed_wait - ai_wait) / max(1.0, fixed_wait) * 100)
        idle_improvement = max(0.0, (fixed_idle - ai_idle) / max(1.0, fixed_idle) * 100)
        self.performance_label.configure(text=f"AI PERFORMANCE\nWaiting improvement: {wait_improvement:.1f}%\nIdle reduction: {idle_improvement:.1f}%\nVehicles cleared: +{max(0, simulation.ai_cleared - simulation.fixed_cleared)}")

    def _refresh_chart(self) -> None:
        self.axis.clear()
        history = self.simulation.history
        if history:
            times = [point[0] for point in history]
            waits = [point[1] for point in history]
            congestion = [point[2] for point in history]
            queue = [point[3] for point in history]
            self.axis.plot(times, waits, color=self.ACCENT, linewidth=2, label="wait s")
            self.axis.plot(times, congestion, color=self.YELLOW, linewidth=1.8, label="congestion")
            self.axis.plot(times, queue, color=self.RED, linewidth=1.4, label="queue")
        self.axis.set_facecolor(self.PANEL)
        self.axis.tick_params(colors=self.MUTED, labelsize=8)
        for spine in self.axis.spines.values():
            spine.set_color("#35505b")
        self.axis.grid(color="#28404a", alpha=0.7)
        if history:
            self.axis.legend(facecolor=self.PANEL, labelcolor=self.TEXT, fontsize=7, loc="upper left")
        self.figure.tight_layout(pad=1)
        self.chart.draw_idle()


def main() -> None:
    try:
        root = tk.Tk()
        TrafficDashboard(root)
        root.mainloop()
    except tk.TclError as error:
        messagebox.showerror("Traffic Dashboard", f"Unable to open the Tkinter window:\n{error}")


if __name__ == "__main__":
    main()
