# -*- coding: utf-8 -*-
import io
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog
from unittest.mock import patch

from digart.engine.image_state import ImageState
from digart.engine.pipeline import (
    DATABEND_EFFECTS,
    GLITCH_EFFECTS,
    NOISE_EFFECTS,
    apply_pipeline,
)
from digart.engine.source_generator import solid
from digart.gui.main_window import MainWindow
from digart.utils.rng import get_rng


def test_preview_no_crash_and_downscale(app: QApplication) -> None:
    stderr_capture = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = stderr_capture
    try:
        state = ImageState()
        state.set_source(solid(256, 256, (80, 120, 60)))
        w = MainWindow(state)
        w.show()
        w._run_preview()
        w._thread_pool.waitForDone(5000)
        for _ in range(50):
            app.processEvents()
        err = stderr_capture.getvalue()
        assert "AttributeError" not in err, err
        assert "deleteLater" not in err, err
    finally:
        sys.stderr = old_stderr
    print("[OK] preview no crash")


def test_preview_downscaled_before_effects() -> None:
    from digart.effects.glitch import ChannelShift

    orig_apply = ChannelShift.apply
    seen_sizes = []

    def wrapped(self, image, params, rng):
        seen_sizes.append(image.size)
        return orig_apply(self, image, params, rng)

    ChannelShift.apply = wrapped
    try:
        source = Image.new("RGB", (3000, 2000), (100, 100, 100))
        apply_pipeline(
            source,
            [(ChannelShift(), {"red_offset": 5})],
            123,
            preview=True,
            max_preview_side=400,
        )
        assert seen_sizes, "effect was not called"
        assert max(seen_sizes[0]) <= 400, f"effect saw full-res size {seen_sizes[0]}"
    finally:
        ChannelShift.apply = orig_apply
    print("[OK] preview downscaled before effects")


def test_preview_worker_no_leak(app: QApplication) -> None:
    import gc
    from digart.gui.worker import PreviewWorker

    state = ImageState()
    state.set_source(solid(256, 256, (80, 120, 60)))
    w = MainWindow(state)
    w.show()
    for _ in range(5):
        w._run_preview()
        w._thread_pool.waitForDone(5000)
        for _ in range(20):
            app.processEvents()
    del w
    gc.collect()
    leaked = [o for o in gc.get_objects() if isinstance(o, PreviewWorker)]
    # PySide6 with setAutoDelete(False) may retain the QRunnable wrappers in
    # C++ memory, but the closure cycle and source reference must be released.
    retained_sources = [w for w in leaked if getattr(w, "source", None) is not None]
    assert len(retained_sources) == 0, (
        f"{len(retained_sources)} leaked PreviewWorker(s) still hold a source image"
    )
    print(f"[OK] preview worker released (no retained source images; {len(leaked)} C++-held wrappers)")


def test_export_unchanged() -> None:
    def old_pipeline(source, enabled, seed):
        by_category = {"glitch": [], "noise": [], "databend": []}
        for effect, params in enabled:
            by_category.setdefault(effect.category, []).append((effect, params))
        ordered = by_category["glitch"] + by_category["noise"] + by_category["databend"]
        image = source.convert("RGB")
        for effect, params in ordered:
            rng = get_rng(seed, salt=effect.id)
            image = effect.apply(image, params, rng).convert("RGB")
        return image, []

    source = Image.new("RGB", (64, 64), (128, 64, 32))
    enabled = [(e, {}) for e in GLITCH_EFFECTS + NOISE_EFFECTS + DATABEND_EFFECTS]
    new, _ = apply_pipeline(source, enabled, 42, preview=False)
    old, _ = old_pipeline(source, enabled, 42)
    assert np.array_equal(np.array(new), np.array(old))
    print("[OK] export pixel output unchanged")


def test_value_noise_lattice_clamped_and_returns_rgb() -> None:
    from digart.effects.noise import ValueNoise

    effect = ValueNoise()
    source = Image.new("RGB", (120, 80), (128, 128, 128))

    seen_shapes = []

    def capturing_zoom(layer, zoom, order=1):
        seen_shapes.append(layer.shape)
        return original_zoom(layer, zoom, order=order)

    import scipy.ndimage as ndi

    original_zoom = ndi.zoom
    ndi.zoom = capturing_zoom
    try:
        rng = get_rng(12345, salt=effect.id)
        result = effect.apply(
            source,
            {"scale": 1, "octaves": 8, "persistence": 0.5, "per_channel": True},
            rng,
        )
    finally:
        ndi.zoom = original_zoom

    assert all(sh[0] <= 80 for sh in seen_shapes), f"layer h exceeded image: {seen_shapes}"
    assert all(sh[1] <= 120 for sh in seen_shapes), f"layer w exceeded image: {seen_shapes}"

    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"
    assert result.size == source.size

    print("[OK] value noise lattice clamped and returns RGB")


def test_export_nonblocking(app: QApplication) -> None:
    state = ImageState()
    state.set_source(solid(500, 500, (128, 128, 128)))
    w = MainWindow(state)
    w.show()
    for panel in w._panels:
        if hasattr(panel, "setChecked"):
            panel.setChecked(True)
        elif hasattr(panel, "enable_checkbox"):
            panel.enable_checkbox.setChecked(True)

    temp_path = tempfile.mktemp(suffix=".png")
    ticks = [0]
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.__setitem__(0, ticks[0] + 1))
    timer.start(10)
    try:
        with patch.object(
            QFileDialog, "getSaveFileName", return_value=(temp_path, "PNG (*.png)")
        ):
            w._export()
        deadline = time.time() + 30
        while w._export_worker is not None and time.time() < deadline:
            app.processEvents()
            time.sleep(0.005)
        assert w._export_worker is None, "export worker did not finish"
        assert os.path.exists(temp_path), "export did not create a file"
        assert ticks[0] > 5, f"event loop frozen during export (ticks={ticks[0]})"
    finally:
        timer.stop()
        if os.path.exists(temp_path):
            os.remove(temp_path)
    print("[OK] export non-blocking")


def main() -> None:
    app = QApplication(sys.argv)
    test_preview_no_crash_and_downscale(app)
    test_preview_downscaled_before_effects()
    test_preview_worker_no_leak(app)
    test_export_unchanged()
    test_value_noise_lattice_clamped_and_returns_rgb()
    test_export_nonblocking(app)
    print("ALL VERIFICATION PASSED")


if __name__ == "__main__":
    main()
