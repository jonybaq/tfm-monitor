"""Pasos de inicialización en la consola."""

import threading


class ConsoleStep:
    def __init__(self, label: str, interactive: bool) -> None:
        self.label = label
        self.interactive = interactive
        self.stopped = threading.Event()
        self.thread = None
        self.visible = False

    def _write(self, text: str, *, end: str = "") -> None:
        print(f"\r{text}\033[K", end=end, flush=True)

    def start(self, *, animate: bool = True) -> None:
        if not self.interactive:
            return
        self._write(f"{self.label}.")
        self.visible = True
        if animate:
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()

    def _animate(self) -> None:
        dots = 1
        while not self.stopped.wait(0.3):
            dots = dots % 5 + 1
            self._write(self.label + "." * dots)

    def stop_animation(self) -> None:
        self.stopped.set()
        if self.thread is not None:
            self.thread.join()

    def pause(self) -> None:
        """Deja espacio para un menú o para introducir datos."""
        self.stop_animation()
        if self.visible:
            self._write("")
            self.visible = False

    def finish(self, success: bool) -> None:
        self.stop_animation()
        mark, color = ("✓", "32") if success else ("✗", "31")
        text = f"{mark} {self.label}"
        if self.interactive:
            self._write(f"\033[{color}m{text}\033[0m", end="\n")
        else:
            print(text, flush=True)


def finish_group(label: str, success: bool, interactive: bool, lines: int) -> None:
    step = ConsoleStep(label, interactive)
    if interactive and lines:
        print(f"\033[{lines}A", end="")
    step.finish(success)
    if interactive and lines > 1:
        print(f"\033[{lines - 1}B", end="", flush=True)
