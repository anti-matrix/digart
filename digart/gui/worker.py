"""Background worker for live preview rendering."""

from typing import Any

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from digart.engine.pipeline import apply_pipeline
from digart.effects.base import Effect


class PreviewWorkerSignals(QObject):
    finished = Signal(int, object, list)


class PreviewWorker(QRunnable):
    """Run apply_pipeline in a background thread.

    Emits ``finished(counter, image, warnings)`` when done.
    """

    def __init__(
        self,
        counter: int,
        source: Image.Image,
        enabled_effects: list[tuple[Effect, dict[str, Any]]],
        global_seed: int,
        max_preview_side: int,
    ) -> None:
        super().__init__()
        self.counter = counter
        self.source = source
        self.enabled_effects = enabled_effects
        self.global_seed = global_seed
        self.max_preview_side = max_preview_side
        self.signals = PreviewWorkerSignals()

    def run(self) -> None:
        try:
            image, warnings = apply_pipeline(
                self.source,
                self.enabled_effects,
                self.global_seed,
                preview=True,
                max_preview_side=self.max_preview_side,
            )
            self.signals.finished.emit(self.counter, image, warnings)
        except Exception as exc:
            self.signals.finished.emit(self.counter, None, [str(exc)])


class ExportWorkerSignals(QObject):
    finished = Signal(list)  # warnings
    error = Signal(str)


class ExportWorker(QRunnable):
    """Run apply_pipeline + save on a background thread."""

    def __init__(
        self,
        source: Image.Image,
        enabled_effects: list[tuple[Effect, dict[str, Any]]],
        global_seed: int,
        path: str,
        is_jpeg: bool,
        quality: int,
    ) -> None:
        super().__init__()
        self.source = source
        self.enabled_effects = enabled_effects
        self.global_seed = global_seed
        self.path = path
        self.is_jpeg = is_jpeg
        self.quality = quality
        self.signals = ExportWorkerSignals()

    def run(self) -> None:
        try:
            image, warnings = apply_pipeline(
                self.source,
                self.enabled_effects,
                self.global_seed,
                preview=False,
            )
            if self.is_jpeg:
                image.convert("RGB").save(self.path, "JPEG", quality=self.quality, optimize=True)
            else:
                image.save(self.path, "PNG")
            self.signals.finished.emit(warnings)
        except Exception as exc:
            self.signals.error.emit(str(exc))
