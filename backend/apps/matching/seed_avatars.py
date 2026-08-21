"""Generated portrait-style avatars for seeded caregivers.

Demo data has no uploaded photos, so browse cards would render blank. These
avatars are drawn locally (no network) and are deterministic per caregiver, so
re-running a seed keeps the same face-plate for the same person.
"""

from __future__ import annotations

import hashlib
import io
from colorsys import hls_to_rgb

from django.core.files.base import ContentFile

from .models import CaregiverProfile

SIZE = 512
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)


def _seed_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def initials(name: str) -> str:
    parts = [p for p in (name or "").replace("-", " ").split() if p]
    if not parts:
        return "CP"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# Care Plus accent range: teal, cyan, indigo, violet, green, amber.
_BRAND_HUES = (172, 190, 205, 232, 262, 150, 38)


def _to_rgb255(channels) -> tuple[int, int, int]:
    r, g, b = (int(round(c * 255)) for c in channels)
    return r, g, b


def _palette(seed: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Two related brand hues for the gradient plate."""
    hue = _BRAND_HUES[seed % len(_BRAND_HUES)] / 360.0
    top = hls_to_rgb(hue, 0.46, 0.42)
    bottom = hls_to_rgb((hue + 0.03) % 1.0, 0.26, 0.48)
    return _to_rgb255(top), _to_rgb255(bottom)


def _font(px: int):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, px)
        except OSError:
            continue
    return ImageFont.load_default()


def avatar_png(name: str, *, salt: str = "") -> bytes:
    """Deterministic gradient plate with centred initials, as PNG bytes."""
    from PIL import Image, ImageDraw, ImageFilter

    seed = _seed_int(f"{name}|{salt}")
    top, bottom = _palette(seed)

    img = Image.new("RGB", (SIZE, SIZE), top)
    draw = ImageDraw.Draw(img)
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        draw.line(
            [(0, y), (SIZE, y)],
            fill=tuple(int(round(top[i] + (bottom[i] - top[i]) * ratio)) for i in range(3)),
        )

    glow = Image.new("L", (SIZE, SIZE), 0)
    gx = int(SIZE * 0.32) + (seed % 60)
    gy = int(SIZE * 0.24) + (seed // 7 % 50)
    ImageDraw.Draw(glow).ellipse([gx - 210, gy - 210, gx + 210, gy + 210], fill=60)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.composite(Image.new("RGB", (SIZE, SIZE), (255, 255, 255)), img, glow)

    draw = ImageDraw.Draw(img, "RGBA")
    inset = int(SIZE * 0.10)
    draw.ellipse(
        [inset, inset, SIZE - inset, SIZE - inset],
        outline=(255, 255, 255, 60),
        width=max(2, SIZE // 128),
    )

    text = initials(name)
    font = _font(int(SIZE * 0.34))
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (
            SIZE / 2 - (box[2] - box[0]) / 2 - box[0],
            SIZE / 2 - (box[3] - box[1]) / 2 - box[1],
        ),
        text,
        font=font,
        fill=(255, 255, 255, 235),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def ensure_caregiver_avatar(profile: CaregiverProfile, *, force: bool = False) -> bool:
    """Attach a generated avatar when the caregiver has no photo. True if saved."""
    if profile.photo and not force:
        return False
    data = avatar_png(profile.display_name, salt=str(profile.pk))
    profile.photo.save(f"seed-avatar-{profile.pk}.png", ContentFile(data), save=True)
    return True
