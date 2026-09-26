"""Small, explainable visual style matching; never claims font identification."""
from __future__ import annotations

from functools import lru_cache
from PySide6.QtGui import QImage


def visual_features(image: QImage) -> dict:
    image = image.convertToFormat(QImage.Format.Format_Grayscale8)
    if image.isNull():
        return {"ink_ratio": 0.0, "aspect": 1.0, "category": "sans"}
    step_x = max(1, image.width() // 80)
    step_y = max(1, image.height() // 80)
    dark = total = 0
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            dark += image.pixelColor(x, y).red() < 120
            total += 1
    ratio = dark / max(1, total)
    category = "display" if ratio > .33 else "sans"
    return {"ink_ratio": ratio, "aspect": image.width()/max(1, image.height()), "category": category}


@lru_cache(maxsize=128)
def _rank(feature_bucket: str, families: tuple[tuple[str, str, int, bool, bool], ...]) -> tuple[tuple[str, str], ...]:
    target = "display" if feature_bucket == "heavy" else "sans"
    scored = []
    for family, category, weight, italic, chinese in families:
        if not chinese:
            continue
        score = (3 if category == target else 1) + (2 if weight >= 600 and target == "display" else 0)
        scored.append((score, family))
    scored.sort(key=lambda item: (-item[0], item[1].casefold()))
    return tuple((family, "high" if score >= 5 else "medium" if score >= 3 else "low")
                 for score, family in scored[:5])


def recommend(image: QImage, font_records: list[dict]) -> list[dict]:
    features = visual_features(image)
    bucket = "heavy" if features["category"] == "display" else "normal"
    entries = tuple((r["family"], r["category"], int(r["weight"]), bool(r["italic"]),
                     "zh" in r["supported_languages"]) for r in font_records)
    return [{"family": family, "similarity": level} for family, level in _rank(bucket, entries)]
