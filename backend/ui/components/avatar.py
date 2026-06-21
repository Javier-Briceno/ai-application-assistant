"""Server-side avatar resizing. Mirrors the client-side logic in ProfileModal.js."""
import base64
import io

from PIL import Image


def process_avatar(image_bytes: bytes, max_width: int = 400, quality: int = 85) -> str:
    """
    Resize image to max_width, encode as JPEG at the given quality,
    and return a data URL string (data:image/jpeg;base64,...).
    Rejects images where the source exceeds ~500 KB.
    """
    if len(image_bytes) > 512_000:
        raise ValueError("Bild zu groß — bitte unter 500 KB hochladen.")

    img = Image.open(io.BytesIO(image_bytes))

    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

    if img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"
