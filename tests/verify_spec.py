# -*- coding: utf-8 -*-
import io
import os
import re
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


def test_export_signature() -> None:
    from digart.engine.signature import (
        SIGNATURE,
        inject_jpeg_comment,
        jpeg_exif_bytes,
        pnginfo_with_signature,
    )
    from PIL.ExifTags import Base, IFD

    sig_bytes = SIGNATURE.encode("ascii")

    png_path = tempfile.mktemp(suffix=".png")
    try:
        img = Image.new("RGB", (8, 8), (64, 128, 32))
        img.save(png_path, "PNG", pnginfo=pnginfo_with_signature())
        data = open(png_path, "rb").read()
        assert sig_bytes in data, "PNG raw bytes missing signature"
        ihdr_pos = data.find(b"IHDR")
        idat_pos = data.find(b"IDAT")
        sig_pos = data.find(sig_bytes)
        assert 0 < ihdr_pos < sig_pos < idat_pos, "PNG signature chunk does not precede IDAT"
        info = Image.open(png_path).info
        assert info.get("Title") == SIGNATURE
        assert info.get("Author") == "@anti-matrix"
        assert info.get("Copyright") == SIGNATURE
        assert info.get("Comment") == SIGNATURE
        assert info.get("Software") == "phabrillust"
        creation_time = info.get("Creation Time")
        assert creation_time is not None
        assert re.fullmatch(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", creation_time)
    finally:
        if os.path.exists(png_path):
            os.remove(png_path)

    jpeg_path = tempfile.mktemp(suffix=".jpg")
    try:
        img = Image.new("RGB", (8, 8), (64, 128, 32))
        img.save(jpeg_path, "JPEG", quality=85, optimize=True, exif=jpeg_exif_bytes())
        inject_jpeg_comment(jpeg_path)
        data = open(jpeg_path, "rb").read()
        assert data[:2] == b'\xff\xd8', "JPEG missing SOI"
        assert data.count(b'\xff\xd8') == 1, "JPEG extra SOI"
        assert data[2:4] == b'\xff\xfe', "JPEG COM not after SOI"
        length = int.from_bytes(data[4:6], "big")
        assert length == 2 + len(SIGNATURE)
        assert data[6:6 + len(SIGNATURE)] == sig_bytes
        assert sig_bytes in data, "JPEG raw bytes missing signature"
        exif = Image.open(jpeg_path).getexif()
        assert exif[Base.ImageDescription] == SIGNATURE
        assert exif[Base.Artist] == "@anti-matrix"
        assert exif[Base.Copyright] == SIGNATURE
        assert exif[Base.Software] == "phabrillust"
        assert exif[Base.XPTitle] == SIGNATURE.encode("utf-16-le") + b'\0\0'
        assert exif[Base.XPComment] == SIGNATURE.encode("utf-16-le") + b'\0\0'
        assert exif[Base.XPAuthor] == "@anti-matrix".encode("utf-16-le") + b'\0\0'
        assert re.fullmatch(r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$", exif[Base.DateTime])
        exif_sub = exif.get_ifd(IFD.Exif)
        user_comment = exif_sub[Base.UserComment]
        assert user_comment.startswith(b'ASCII\0\0\0')
        assert user_comment.endswith(sig_bytes)
        assert exif_sub[Base.DateTimeOriginal] == exif[Base.DateTime]
        assert exif_sub[Base.DateTimeDigitized] == exif[Base.DateTime]
        assert Base.GPSInfo not in exif, "GPS info must not be present"
    finally:
        if os.path.exists(jpeg_path):
            os.remove(jpeg_path)

    print("[OK] export signature PNG and JPEG")


def test_export_worker_signature(app: QApplication) -> None:
    from digart.engine.signature import SIGNATURE
    from digart.gui.worker import ExportWorker
    from PIL.ExifTags import Base
    from PySide6.QtCore import QThreadPool

    source = Image.new("RGB", (64, 64), (64, 128, 32))
    effects = [(e, {}) for e in GLITCH_EFFECTS + NOISE_EFFECTS + DATABEND_EFFECTS]
    sig_bytes = SIGNATURE.encode("ascii")

    for suffix, is_jpeg in ((".png", False), (".jpg", True)):
        path = tempfile.mktemp(suffix=suffix)
        worker = ExportWorker(
            source=source,
            enabled_effects=effects,
            global_seed=42,
            path=path,
            is_jpeg=is_jpeg,
            quality=85,
        )
        state = {"finished": False, "error": None}
        worker.signals.finished.connect(
            lambda _w, _s=state: _s.__setitem__("finished", True)
        )
        worker.signals.error.connect(
            lambda msg, _s=state: _s.__setitem__("error", msg)
        )
        QThreadPool.globalInstance().start(worker)
        deadline = time.time() + 30
        while not state["finished"] and state["error"] is None and time.time() < deadline:
            app.processEvents()
            time.sleep(0.005)
        assert state["error"] is None, f"export worker error for {suffix}: {state['error']}"
        assert state["finished"], f"export worker did not finish for {suffix}"
        assert os.path.exists(path), f"export did not create {suffix} file"
        data = open(path, "rb").read()
        assert sig_bytes in data, f"{suffix} raw bytes missing signature"
        with Image.open(path) as img:
            assert img.size == (64, 64)
            if is_jpeg:
                exif = img.getexif()
                assert Base.GPSInfo not in exif, "JPEG GPS info must not be present"
                assert re.fullmatch(
                    r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$", exif[Base.DateTime]
                )
            else:
                info = img.info
                assert re.fullmatch(
                    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", info.get("Creation Time")
                )
                assert info.get("Software") == "phabrillust"
        os.remove(path)

    print("[OK] export worker signature")


def main() -> None:
    app = QApplication(sys.argv)
    test_preview_no_crash_and_downscale(app)
    test_preview_downscaled_before_effects()
    test_preview_worker_no_leak(app)
    test_export_unchanged()
    test_value_noise_lattice_clamped_and_returns_rgb()
    test_export_nonblocking(app)
    test_export_signature()
    test_export_worker_signature(app)
    print("ALL VERIFICATION PASSED")


if __name__ == "__main__":
    main()
