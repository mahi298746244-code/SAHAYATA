"""Image analysis: honest, offline-first.

What we actually compute:
- decode/validation via Pillow
- brightness + sharpness quality metrics
- dhash perceptual hash for near-duplicate photo detection

Optional external labels: if AI_VISION_PROVIDER=openai and OPENAI_API_KEY are
configured, the image is sent for structured labelling; results are stored as
AI-assisted evidence only – never as proof a problem exists or is solved.
"""
import base64
import io

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("sahayata.ai.vision")


def load_image(data: bytes):
    """Returns PIL.Image or raises ValueError."""
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return img
    except UnidentifiedImageError as exc:
        raise ValueError("not a valid image") from exc


def dhash(img, size: int = 8) -> str:
    import PIL.ImageFilter as _f  # noqa: F401

    g = img.convert("L").resize((size + 1, size))
    px = list(g.getdata())
    bits = []
    for row in range(size):
        for col in range(size):
            bits.append(1 if px[row * (size + 1) + col] > px[row * (size + 1) + col + 1] else 0)
    return "".join(str(b) for b in bits)


def hamming(a: str | None, b: str | None) -> int:
    if not a or not b or len(a) != len(b):
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)


def analyze_image(data: bytes) -> dict:
    """Local analysis. Never throws beyond ValueError for invalid images."""
    img = load_image(data)
    from PIL import ImageFilter, ImageStat

    grey = img.convert("L")
    stat = ImageStat.Stat(grey)
    brightness = round(stat.mean[0], 1)
    edges = grey.filter(ImageFilter.FIND_EDGES)
    sharpness = round(ImageStat.Stat(edges).stddev[0], 1)

    return {
        "provider": "local-rules",
        "width": img.width,
        "height": img.height,
        "quality": {
            "brightness": brightness,
            "sharpness": sharpness,
            "note": (
                "low-light photo" if brightness < 60 else
                "blurry photo" if sharpness < 12 else
                "acceptable"
            ),
        },
        "phash": dhash(img),
        "labels": [],  # local mode performs NO object detection by design
    }


def external_labels(data: bytes) -> list[dict] | None:
    """Optional OpenAI-compatible vision call. Returns None when disabled/unavailable."""
    if settings.AI_VISION_PROVIDER != "openai" or not settings.OPENAI_API_KEY:
        return None
    try:
        import httpx

        b64 = base64.b64encode(data).decode()
        prompt = (
            'Analyse this civic complaint photo. Reply ONLY JSON: '
            '{"labels":[{"name":"...","confidence":0..1}],'
            '"visible_problem":true|false,"summary":"one sentence"}'
        )
        resp = httpx.post(
            f"{settings.OPENAI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": settings.OPENAI_VISION_MODEL,
                "messages": [
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ]}
                ],
                "max_tokens": 300,
            },
            timeout=20,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        import json

        start, end = content.find("{"), content.rfind("}")
        parsed = json.loads(content[start : end + 1])
        return {
            "provider": f"openai:{settings.OPENAI_VISION_MODEL}",
            "labels": parsed.get("labels", []),
            "visible_problem": parsed.get("visible_problem"),
            "summary": parsed.get("summary"),
        }
    except Exception:
        log.exception("external vision failed; continuing without labels")
        return None
