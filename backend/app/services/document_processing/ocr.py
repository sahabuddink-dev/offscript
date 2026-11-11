from functools import lru_cache
from tempfile import NamedTemporaryFile

from app.services.document_processing.base import ProcessingError


def _plain_bounding_box(points):
    if hasattr(points, "tolist"):
        points = points.tolist()
    return [[float(coordinate) for coordinate in point] for point in points]


@lru_cache(maxsize=1)
def _get_ocr_engine():
    try:
        from paddleocr import PaddleOCR
    except ImportError as error:
        raise ProcessingError(
            "This scanned page requires OCR. Install PaddleOCR and PaddlePaddle "
            "to process scanned PDFs."
        ) from error
    try:
        return PaddleOCR(use_angle_cls=True, lang="en")
    except TypeError:
        return PaddleOCR(use_textline_orientation=True, lang="en")


def recognize_page(image_bytes: bytes) -> list[dict]:
    try:
        with NamedTemporaryFile(prefix="offscript-ocr-", suffix=".png") as image_file:
            image_file.write(image_bytes)
            image_file.flush()
            engine = _get_ocr_engine()
            if hasattr(engine, "predict"):
                result = engine.predict(image_file.name)
            else:
                result = engine.ocr(image_file.name, cls=True)
    except ProcessingError:
        raise
    except Exception as error:
        raise ProcessingError("OCR could not read a scanned document page.") from error

    recognized: list[dict] = []
    if not result:
        return recognized

    page_result = result[0] or []
    if isinstance(page_result, dict):
        texts = page_result.get("rec_texts", [])
        scores = page_result.get("rec_scores", [0.0] * len(texts))
        polygons = page_result.get("dt_polys", page_result.get("rec_polys", []))
        return [
            {
                "text": text.strip(),
                "confidence": float(confidence),
                "bounding_box": _plain_bounding_box(polygon),
            }
            for text, confidence, polygon in zip(
                texts,
                scores,
                polygons,
            )
            if text.strip()
        ]

    for line in page_result:
        try:
            points, (text, confidence) = line
            if text.strip():
                recognized.append(
                    {
                        "text": text.strip(),
                        "confidence": float(confidence),
                        "bounding_box": _plain_bounding_box(points),
                    }
                )
        except (TypeError, ValueError):
            continue
    return recognized
