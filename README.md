# digart

A dark, minimal PySide6 desktop app for real digital glitch art and noise.

Generate, corrupt, databend, and export RGB glitch compositions from a clean, keyboard-friendly interface.

---

## Features

- Clean custom dark greyscale UI (no stock Qt look)
- Live preview with 120 ms debounce
- Source generators: blank, solid, linear gradient, radial gradient
- 5 algorithmic glitch effects
- 4 noise effects
- 6 byte-level databend effects
- Deterministic output via a single global seed
- Undo / reset history
- Export PNG or JPEG at full resolution

---

## Requirements

- Python 3.14
- PySide6 6.11.2
- NumPy, Pillow, OpenCV, scikit-image, SciPy (already installed in the target environment)

---

## Install

```bash
python -m pip install -r requirements.txt
```

(`numpy`, `Pillow`, `opencv-python`, `scikit-image`, `scipy` are commented out because they are already present; uncomment only if you need to pin them.)

---

## Run

```bash
python main.py
python main.py path/to/image.png
python main.py path/to/image.png --seed 42
```

Module execution is also supported:

```bash
python -m digart
```

---

## Built-in generators

| Generator | Description |
|-----------|-------------|
| Blank | Solid black canvas |
| Solid | Single color fill |
| Linear gradient | Angle-driven two-color linear blend |
| Radial gradient | Two-color radial blend from center |

---

## Effect guide

### Glitch

| Effect | What it does |
|--------|--------------|
| channel_shift | Offset individual RGB channels horizontally or vertically |
| scanline_tear | Shift random horizontal scanline slices |
| pixel_sort | Sort contiguous runs of pixels above a threshold |
| block_displace | Copy or move axis-aligned blocks with wraparound |
| glitch_slice | Divide the image into strips and shift each |

### Noise

| Effect | What it does |
|--------|--------------|
| gaussian_noise | Additive Gaussian noise per channel or monochrome |
| salt_pepper | Random salt & pepper pixels |
| value_noise | Multi-octave interpolated value noise |
| film_grain | High-frequency grain with slight blur |

### Databend

| Effect | What it does |
|--------|--------------|
| databend_bitflip | Flip bits in a PNG byte stream |
| databend_drop | Drop bytes from a PNG byte stream |
| databend_duplicate | Duplicate bytes in a PNG byte stream |
| databend_shuffle | Shuffle chunks of a PNG byte stream |
| databend_png_idat | Corrupt PNG IDAT payload specifically |
| databend_jpeg_body | Re-encode as JPEG, then corrupt the body |

All databend effects decode the corrupted bytes and fall back to the previous image if decoding fails.

---

## Controls / workflow

1. **Open or generate** a source image.
2. **Enable effects** on the right panels and tune their parameters.
3. Watch the **live preview** update in the center.
4. Use **Undo** or **Reset** to roll back changes.
5. **Export** as PNG or JPEG at full resolution.

---

## Fonts

The app bundles two open-source fonts:

- **Space Grotesk** — UI typeface  
  `assets/fonts/SpaceGrotesk-VariableFont_wght.ttf`
- **JetBrains Mono** — numeric / status typeface  
  `assets/fonts/JetBrainsMono-VariableFont_wght.ttf`

Both are licensed under the SIL Open Font License. See `assets/fonts/SpaceGrotesk-OFL.txt` and `assets/fonts/JetBrainsMono-OFL.txt`.

---

## Git

The repository is initialized and the remote is set:

```
origin  https://github.com/anti-matrix/digart.git (fetch)
origin  https://github.com/anti-matrix/digart.git (push)
```

No commits or pushes have been made yet.

---

## License

Code is released under the MIT License.

Bundled fonts are licensed under the SIL Open Font License 1.1.
