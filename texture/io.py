"""Safe image loading for files and browser uploads, including EXIF orientation."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import warnings
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 20*1024*1024
MAX_PIXELS = 24_000_000
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

def load_image(source: str | Path | bytes) -> np.ndarray:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise ValueError(f"Image file not found: {path}")
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Image file exceeds the 20 MiB upload limit.")
        data = path.read_bytes()
    elif isinstance(source, bytes):
        data = source
    else:
        raise TypeError("source must be a path or bytes.")
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Empty image or image exceeds the 20 MiB limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as raw:
                if raw.width*raw.height > MAX_PIXELS:
                    raise ValueError("Image exceeds 24 million pixels; crop before loading.")
                if getattr(raw, "n_frames", 1) > 1:
                    raise ValueError("Multi-frame files are not supported; export a single image first.")
                im = ImageOps.exif_transpose(raw)
                if im.mode in ("1", "L", "I", "F") or im.mode.startswith("I;16"):
                    return np.asarray(im).copy()
                if "A" in im.getbands() or "transparency" in im.info:
                    rgba = im.convert("RGBA")
                    white = Image.new("RGBA", rgba.size, (255,255,255,255))
                    im = Image.alpha_composite(white, rgba).convert("RGB")
                else:
                    im = im.convert("RGB")
                return np.asarray(im).copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("Invalid, corrupt, unsupported or excessively large image.") from exc

def png_bytes(arr: np.ndarray) -> bytes:
    image = np.asarray(arr)
    if image.dtype != np.uint8:
        image = np.clip(np.rint(image*255), 0, 255).astype(np.uint8)
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()
