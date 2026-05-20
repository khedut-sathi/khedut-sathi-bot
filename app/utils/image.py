import io
from PIL import Image


def compress_image(image_bytes: bytes, max_size: int = 1024, quality: int = 80) -> bytes:
    """Compress image for storage and API calls."""
    img = Image.open(io.BytesIO(image_bytes))

    if img.mode == "RGBA":
        img = img.convert("RGB")

    width, height = img.size
    if max(width, height) > max_size:
        ratio = max_size / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
