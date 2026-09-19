"""Pipeline that orders and applies effects."""

from typing import Any

from PIL import Image

from digart.effects.base import Effect
from digart.effects.glitch import (
    BlockDisplace,
    ChannelShift,
    GlitchSlice,
    PixelSort,
    ScanlineTear,
)
from digart.effects.noise import (
    FilmGrain,
    GaussianNoise,
    SaltPepper,
    ValueNoise,
)
from digart.engine.databend import DATABEND_EFFECTS
from digart.utils.rng import get_rng

GLITCH_EFFECTS: list[Effect] = [
    ChannelShift(),
    ScanlineTear(),
    PixelSort(),
    BlockDisplace(),
    GlitchSlice(),
]

NOISE_EFFECTS: list[Effect] = [
    GaussianNoise(),
    SaltPepper(),
    ValueNoise(),
    FilmGrain(),
]


def apply_pipeline(
    source: Image.Image,
    enabled_effects: list[tuple[Effect, dict[str, Any]]],
    global_seed: int,
    preview: bool = True,
    max_preview_side: int = 1200,
) -> tuple[Image.Image, list[str]]:
    """Apply enabled effects in fixed order: glitch -> noise -> databend.

    Each effect receives a per-effect RNG derived from ``global_seed`` and
    ``effect.id``. Exceptions are caught, a warning is recorded, and the
    previous image is carried forward.

    If ``preview`` is True the returned image is down-scaled to
    ``max_preview_side`` using LANCZOS.
    """
    warnings: list[str] = []

    # Reorder by category.
    by_category: dict[str, list[tuple[Effect, dict[str, Any]]]] = {
        "glitch": [],
        "noise": [],
        "databend": [],
    }
    for effect, params in enabled_effects:
        by_category.setdefault(effect.category, []).append((effect, params))

    ordered = by_category["glitch"] + by_category["noise"] + by_category["databend"]
    image = source.convert("RGB")

    for effect, params in ordered:
        try:
            rng = get_rng(global_seed, salt=effect.id)
            image = effect.apply(image, params, rng)
            image = image.convert("RGB")
        except Exception as exc:
            warnings.append(f"{effect.name} failed: {exc}")

    if preview:
        from digart.engine.renderer import make_preview

        image = make_preview(image, max_preview_side)

    return image, warnings
