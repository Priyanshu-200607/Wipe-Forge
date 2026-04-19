from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, Center, Middle
from textual.widgets import Header, Footer, Button, DataTable, Input, Log, ProgressBar, Label, Static
from textual.screen import Screen
from textual.binding import Binding
from textual.worker import Worker, WorkerState
import multiprocessing as mp
import time
import os
import signal
from typing import Optional, List

from wipeforge.core.models import DeviceInfo
from wipeforge.core.detection import scan_devices
from wipeforge.engine.decision import decide_strategy, WipeStrategy
from wipeforge.worker.process import wipe_worker
from wipeforge.utils.logger import setup_logger, log_wipe_start, log_wipe_result, log_event

class ResultScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]
    
    def __init__(self, success: bool, message: str, **kwargs):
        super().__init__(**kwargs)
        self.success = success
        self.message = message
        
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Middle():
                color = "green" if self.success else "red"
                yield Label(f"[{color}]WIPE {'SUCCESSFUL' if self.success else 'FAILED'}[/]", id="result-title")
                yield Label(self.message, id="result-message")
                yield Button("Return to Dashboard", id="btn-return", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-return":
            self.app.switch_screen("dashboard")


class ProgressScreen(Screen):
    def __init__(self, device: DeviceInfo, strategy: WipeStrategy, dry_run: bool, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.strategy = strategy
        self.dry_run = dry_run
        self.queue = mp.Queue()
        self.worker_process: Optional[mp.Process] = None
        self.aborted = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="progress-container"):
            yield Label(f"Wiping: {self.device.stable_id}", id="prog-target")
            yield Label("Initializing...", id="prog-status")
            yield ProgressBar(total=100, show_eta=False, id="prog-bar")
            yield Log(id="prog-log")
            yield Button("EMERGENCY ABORT (Ctrl+C)", id="btn-abort", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        log_wipe_start(self.device.stable_id, self.device.serial, self.strategy.method)
        self.worker_process = mp.Process(
            target=wipe_worker,
            args=(self.device, self.strategy, self.dry_run, self.queue)
        )
        self.worker_process.start()
        self.set_interval(0.1, self.poll_queue)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-abort":
            self.abort_wipe()

    def abort_wipe(self):
        if self.worker_process and self.worker_process.is_alive():
            self.worker_process.terminate()
            self.worker_process.join(timeout=1)
        self.aborted = True
        log_wipe_result(self.device.stable_id, False, "Aborted by user")
        self.app.push_screen(ResultScreen(False, "Wipe forcefully aborted. Data state is unknown!"))

    def poll_queue(self):
        if self.aborted:
            return
            
        while not self.queue.empty():
            msg = self.queue.get_nowait()
            mtype = msg.get("type")
            log_widget = self.query_one("#prog-log", Log)
            
            if mtype == "status":
                self.query_one("#prog-status", Label).update(msg["message"])
                log_widget.write_line(f"[cyan]{msg['message']}[/]")
            elif mtype == "progress":
                self.query_one("#prog-bar", ProgressBar).update(progress=msg["pct"])
                log_widget.write_line(msg["message"])
            elif mtype == "error":
                log_widget.write_line(f"[red]ERROR: {msg['message']}[/]")
                log_wipe_result(self.device.stable_id, False, msg["message"])
                self.app.push_screen(ResultScreen(False, f"Error: {msg['message']}"))
                return
            elif mtype == "complete":
                self.query_one("#prog-bar", ProgressBar).update(progress=100)
                log_wipe_result(self.device.stable_id, True, "Wipe and verification complete.")
                self.app.push_screen(ResultScreen(True, msg.get("message", "Success")))
                return


class FinalValidationScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, device: DeviceInfo, strategy: WipeStrategy, dry_run: bool, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.strategy = strategy
        self.dry_run = dry_run
        self.countdown = 5

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="final-validation-box"):
                yield Label("[red]!!! FINAL WARNING !!![/]", classes="warning-title")
                yield Label(f"Target: [bold]{self.device.stable_id}[/]")
                yield Label(f"Model: {self.device.model}")
                yield Label(f"Serial: {self.device.serial}")
                yield Label(f"Command to execute:\n[yellow]{self.strategy.command_preview}[/]")
                if self.dry_run:
                    yield Label("[green]DRY RUN MODE ENABLED - No data will be written[/]")
                
                yield Label("Waiting 5 seconds before unlock...", id="countdown-label")
                with Horizontal():
                    yield Button("EXECUTE WIPE", id="btn-execute", variant="error", disabled=True)
                    yield Button("Cancel", id="btn-cancel", variant="primary")
        yield Footer()

    def on_mount(self):
        self.set_interval(1, self.tick_countdown)

    def tick_countdown(self):
        if self.countdown > 0:
            self.countdown -= 1
            lbl = self.query_one("#countdown-label", Label)
            if self.countdown > 0:
                lbl.update(f"Waiting {self.countdown} seconds before unlock...")
            else:
                lbl.update("READY TO EXECUTE.")
                btn = self.query_one("#btn-execute", Button)
                btn.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.app.pop_screen()
        elif event.button.id == "btn-execute":
            self.app.push_screen(ProgressScreen(self.device, self.strategy, self.dry_run))


class ConfirmationScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, device: DeviceInfo, strategy: WipeStrategy, dry_run: bool, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.strategy = strategy
        self.dry_run = dry_run
        self.expected_text = f"WIPE {self.device.stable_id}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="confirmation-box"):
                yield Label("Type the following text exactly to confirm:")
                yield Label(f"[bold red]{self.expected_text}[/]")
                yield Input(placeholder="Type here...", id="confirm-input")
                yield Button("Proceed", id="btn-proceed", disabled=True)
                yield Button("Cancel", id="btn-cancel")
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        btn = self.query_one("#btn-proceed", Button)
        btn.disabled = event.value != self.expected_text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-proceed":
            self.app.push_screen(FinalValidationScreen(self.device, self.strategy, self.dry_run))
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()


class StrategyScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, device: DeviceInfo, dry_run: bool, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.strategy = decide_strategy(device)
        self.dry_run = dry_run

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="strategy-box"):
                yield Label(f"Target: [bold]{self.device.stable_id}[/]")
                yield Label(f"Size: {self.device.size_bytes / (1024**3):.2f} GB")
                yield Label(f"Selected Method: [yellow]{self.strategy.method}[/]")
                yield Label(f"Reason: {self.strategy.reason}")
                yield Label(f"Estimated Time: {self.strategy.estimated_time}")
                yield Label(f"Risk Level: [red]{self.strategy.risk_level}[/]")
                
                with Horizontal():
                    yield Button("Continue", id="btn-continue", variant="error")
                    yield Button("Cancel", id="btn-cancel", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-continue":
            self.app.push_screen(ConfirmationScreen(self.device, self.strategy, self.dry_run))
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()


class DashboardScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("r", "refresh_devices", "Refresh"),
        ("d", "toggle_dry_run", "Toggle Dry Run")
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.safe_devices: List[DeviceInfo] = []
        self.blocked_devices: List[DeviceInfo] = []
        self.dry_run = True

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            mode_color = "green" if self.dry_run else "red"
            mode_text = "DRY RUN MODE" if self.dry_run else "LIVE DESTRUCTIVE MODE"
            yield Label(f"Current Mode: [{mode_color} bold]{mode_text}[/]", id="mode-label")
            yield Label("Select a SAFE device to wipe (Blocked devices are shown for info only):")
            yield DataTable(id="device-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Status", "Stable ID", "Dev Path", "Model", "Size (GB)", "Transport", "Mounted/Sys")
        self.action_refresh_devices()

    def action_refresh_devices(self):
        log_event("SCAN", "Scanning devices...")
        self.safe_devices, self.blocked_devices = scan_devices()
        table = self.query_one(DataTable)
        table.clear()
        
        for dev in self.safe_devices:
            gb = dev.size_bytes / (1024**3)
            table.add_row(
                "[green]SAFE[/]", 
                dev.stable_id, 
                dev.dev_path,
                dev.model, 
                f"{gb:.2f}", 
                dev.transport,
                "No",
                key=dev.stable_id
            )
            
        for dev in self.blocked_devices:
            gb = dev.size_bytes / (1024**3)
            reasons = []
            if dev.mounted: reasons.append("Mounted")
            if dev.is_system_disk: reasons.append("System")
            table.add_row(
                "[red]BLOCKED[/]", 
                dev.stable_id, 
                dev.dev_path,
                dev.model, 
                f"{gb:.2f}", 
                dev.transport,
                ",".join(reasons),
                key=dev.stable_id
            )

    def action_toggle_dry_run(self):
        self.dry_run = not self.dry_run
        mode_color = "green" if self.dry_run else "red"
        mode_text = "DRY RUN MODE" if self.dry_run else "LIVE DESTRUCTIVE MODE"
        lbl = self.query_one("#mode-label", Label)
        lbl.update(f"Current Mode: [{mode_color} bold]{mode_text}[/]")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        
        selected_dev = next((d for d in self.safe_devices if d.stable_id == row_key), None)
        if selected_dev:
            self.app.push_screen(StrategyScreen(selected_dev, self.dry_run))
        else:
            self.app.notify("Cannot select blocked device.", severity="error")


class WipeForgeApp(App):
    CSS = """
    Screen {
        align: center middle;
    }
    #confirmation-box, #strategy-box, #final-validation-box {
        width: 80%;
        height: auto;
        border: solid red;
        padding: 1 2;
        background: $surface;
    }
    .warning-title {
        text-align: center;
        text-style: bold;
    }
    DataTable {
        height: 1fr;
    }
    """

    def on_mount(self) -> None:
        setup_logger()
        log_event("APP", "WipeForge started.")
        self.install_screen(DashboardScreen(), name="dashboard")
        self.push_screen("dashboard")

    def on_unmount(self) -> None:
        log_event("APP", "WipeForge exited.")

if __name__ == "__main__":
    app = WipeForgeApp()
    app.run()
