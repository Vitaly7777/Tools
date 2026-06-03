from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_HEADER_SCAN_ROWS = 50
DEFAULT_PREVIEW_PAGE_SIZE = 50
HEADER_LOOKAHEAD_ROWS = 6
HEADER_AUTO_ACCEPT_THRESHOLD = 0.58
HEADER_MIN_SCORE = 6.0
SERVICE_WORD_PATTERNS = (
    "содержание",
    "описание",
    "итого",
    "раздел",
    "лист",
    "комментар",
    "summary",
    "description",
    "total",
    "section",
)


@dataclass
class PreviewPage:
    columns: list[str]
    rows: list[list[str]]
    total_rows: int
    offset: int
    limit: int


def read_sheet_names(file_path: str) -> list[str]:
    normalized_path = _normalize_file_path(file_path)
    if normalized_path.suffix.lower() == ".csv":
        return [normalized_path.name]
    workbook = pd.ExcelFile(normalized_path)
    return list(workbook.sheet_names)


def detect_header_for_sheet(
    file_path: str,
    sheet_name: str,
    *,
    scan_rows: int = DEFAULT_HEADER_SCAN_ROWS,
) -> dict[str, Any]:
    raw_frame = _read_raw_frame(
        file_path=file_path,
        sheet_name=sheet_name,
        nrows=max(10, int(scan_rows)),
    )
    result = detect_header_row(raw_frame)
    result["sheet_name"] = str(sheet_name or "").strip()
    result["file_path"] = str(file_path or "").strip()
    return result


def build_source_schema_preview(
    file_path: str,
    *,
    scan_rows: int,
    header_row: int | None = None,
    sheet_name: str = "",
    selected_columns: list[str] | None = None,
    column_types: dict[str, str] | None = None,
) -> dict[str, Any]:
    normalized_path = _normalize_file_path(file_path)
    preview_rows = max(10, int(scan_rows))
    raw_frame = _read_raw_frame(
        file_path=str(normalized_path),
        sheet_name=sheet_name,
        nrows=preview_rows,
    )

    if header_row is None:
        detection = detect_header_row(raw_frame)
        detected_header = int(detection["header_row"])
        header_confidence = float(detection["confidence"])
        header_confirmed = bool(detection["auto_accept"])
        header_explanation = str(detection["explanation"])
        header_debug = list(detection["candidates"])
    else:
        detected_header = max(0, int(header_row))
        header_confidence = 1.0
        header_confirmed = True
        header_explanation = "Шапка выбрана вручную."
        header_debug = []

    sample_frame = _read_dataframe(
        file_path=str(normalized_path),
        sheet_name=sheet_name,
        header_row=detected_header,
        nrows=50,
    )

    raw_rows = [
        [
            "" if pd.isna(value) else str(value)
            for value in raw_frame.iloc[row_index].tolist()
        ]
        for row_index in range(len(raw_frame.index))
    ]

    selected = set(selected_columns or [])
    normalized_column_types = dict(column_types or {})
    rows: list[dict[str, Any]] = []
    for column_name in sample_frame.columns:
        normalized_name = str(column_name).strip()
        if not normalized_name:
            continue
        rows.append(
            {
                "name": normalized_name,
                "detected_type": _detect_type(sample_frame[column_name]),
                "enabled": True if not selected else normalized_name in selected,
                "read_as": normalized_column_types.get(normalized_name, "auto"),
            }
        )

    return {
        "sample_file": str(normalized_path),
        "sheet_name": str(sheet_name or "").strip(),
        "header_row": detected_header,
        "header_confidence": header_confidence,
        "header_confirmed": header_confirmed,
        "header_explanation": header_explanation,
        "header_debug_scores": header_debug,
        "raw_rows": raw_rows,
        "rows": rows,
    }


def load_total_rows(file_path: str, sheet_name: str, header_row: int) -> int:
    frame = _read_dataframe(
        file_path=file_path,
        sheet_name=sheet_name,
        header_row=header_row,
        nrows=None,
    )
    return int(len(frame.index))


def load_preview_page(
    file_path: str,
    sheet_name: str,
    header_row: int,
    *,
    offset: int = 0,
    limit: int = DEFAULT_PREVIEW_PAGE_SIZE,
) -> PreviewPage:
    frame = _read_dataframe(
        file_path=file_path,
        sheet_name=sheet_name,
        header_row=header_row,
        nrows=None,
    )
    start = max(0, int(offset))
    page_size = max(1, int(limit))
    end = start + page_size
    page_frame = frame.iloc[start:end]
    columns = [str(column) for column in page_frame.columns]
    rows = [
        ["" if pd.isna(value) else str(value) for value in row]
        for row in page_frame.itertuples(index=False, name=None)
    ]
    return PreviewPage(
        columns=columns,
        rows=rows,
        total_rows=int(len(frame.index)),
        offset=start,
        limit=page_size,
    )


def detect_header_row(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "header_row": 0,
            "confidence": 0.0,
            "auto_accept": False,
            "explanation": "Нет строк для анализа.",
            "candidates": [],
        }

    candidates: list[dict[str, Any]] = []
    for row_index in range(len(frame.index)):
        features = _extract_row_features(frame, row_index)
        header_score, header_reasons = _score_header_likeness(features)
        data_score, metrics, data_reasons = _score_data_below(
            frame, row_index, features
        )
        penalty, anti_reasons = _score_anti_patterns(features)
        final_score = header_score + data_score - penalty
        candidates.append(
            {
                "row_index": row_index,
                "header_likeness": round(header_score, 3),
                "data_below_score": round(data_score, 3),
                "anti_pattern_penalty": round(penalty, 3),
                "final_score": round(final_score, 3),
                "features": features,
                "metrics": metrics,
                "header_reasons": header_reasons,
                "data_reasons": data_reasons,
                "anti_reasons": anti_reasons,
            }
        )

    for candidate in candidates:
        if candidate["metrics"]["stable_rows"] >= 2:
            continue
        next_candidates = [
            item
            for item in candidates
            if candidate["row_index"] < item["row_index"] <= candidate["row_index"] + 3
        ]
        if not next_candidates:
            continue
        if (
            max(item["header_likeness"] for item in next_candidates)
            > candidate["header_likeness"] + 1.5
        ):
            candidate["final_score"] = round(candidate["final_score"] - 2.0, 3)
            candidate["anti_reasons"].append("ниже есть более правдоподобная шапка")

    ordered = sorted(
        candidates,
        key=lambda item: (item["final_score"], -item["row_index"]),
        reverse=True,
    )
    best = ordered[0]
    second_score = (
        ordered[1]["final_score"] if len(ordered) > 1 else best["final_score"] - 5.0
    )
    score_gap = float(best["final_score"] - second_score)
    strength = max(0.0, min(1.0, best["final_score"] / 18.0))
    separation = max(0.0, min(1.0, score_gap / 6.0))
    confidence = round((strength * 0.6) + (separation * 0.4), 3)
    auto_accept = (
        best["final_score"] >= HEADER_MIN_SCORE
        and confidence >= HEADER_AUTO_ACCEPT_THRESHOLD
        and (
            best["metrics"]["stable_rows"] >= 2
            or (
                best["metrics"]["stable_rows"] >= 1
                and best["metrics"]["typed_value_hits"] >= 2
            )
        )
    )
    if not auto_accept:
        confidence = min(confidence, HEADER_AUTO_ACCEPT_THRESHOLD - 0.05)
    explanation = _build_explanation(
        best["header_reasons"],
        best["data_reasons"],
        best["anti_reasons"],
        low_confidence=not auto_accept,
    )
    return {
        "header_row": int(best["row_index"]),
        "confidence": confidence,
        "auto_accept": auto_accept,
        "explanation": explanation,
        "candidates": ordered[:5],
    }


def _read_raw_frame(file_path: str, sheet_name: str, *, nrows: int) -> pd.DataFrame:
    normalized_path = _normalize_file_path(file_path)
    suffix = normalized_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(normalized_path, header=None, nrows=nrows, dtype=object)
    return pd.read_excel(
        normalized_path,
        header=None,
        nrows=nrows,
        dtype=object,
        sheet_name=str(sheet_name or "").strip() or 0,
    )


def _read_dataframe(
    file_path: str,
    sheet_name: str,
    *,
    header_row: int,
    nrows: int | None,
) -> pd.DataFrame:
    normalized_path = _normalize_file_path(file_path)
    suffix = normalized_path.suffix.lower()
    header_index = max(0, int(header_row))
    if suffix == ".csv":
        return pd.read_csv(
            normalized_path, header=header_index, dtype=object, nrows=nrows
        )
    return pd.read_excel(
        normalized_path,
        header=header_index,
        dtype=object,
        sheet_name=str(sheet_name or "").strip() or 0,
        nrows=nrows,
    )


def _normalize_file_path(file_path: str) -> Path:
    path = Path(str(file_path or "").strip())
    if not str(path):
        raise FileNotFoundError("Не выбран Excel-файл.")
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    return path


def _normalize_cell_text(value: Any) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    return "" if text.lower() == "nan" else text


def _looks_numeric(text: str) -> bool:
    return bool(re.fullmatch(r"-?\d+([.,]\d+)?", text))


def _looks_date(text: str) -> bool:
    normalized = text.replace("\\", "/").replace("-", "/").replace(".", "/")
    return bool(re.fullmatch(r"\d{1,4}/\d{1,2}/\d{1,4}", normalized))


def _looks_code(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-zА-Яа-я]{0,3}\d{2,}[A-Za-zА-Яа-я]{0,3}", text))


def _service_word_hits(text: str) -> int:
    lowered = text.casefold()
    return sum(pattern in lowered for pattern in SERVICE_WORD_PATTERNS)


def _extract_row_features(frame: pd.DataFrame, row_index: int) -> dict[str, Any]:
    row = frame.iloc[row_index].tolist()
    positions: list[int] = []
    labels: list[str] = []
    short_label_count = 0
    long_phrase_count = 0
    text_like_count = 0
    numeric_like_count = 0
    service_word_hits = 0

    for column_index, value in enumerate(row):
        text = _normalize_cell_text(value)
        if not text:
            continue
        positions.append(column_index)
        labels.append(text)
        if any(char.isalpha() for char in text):
            text_like_count += 1
        if _looks_numeric(text):
            numeric_like_count += 1
        if len(text) <= 32 and len(text.split()) <= 5:
            short_label_count += 1
        if len(text) >= 45 or len(text.split()) >= 6:
            long_phrase_count += 1
        service_word_hits += _service_word_hits(text)

    unique_count = len({label.casefold() for label in labels})
    duplicate_count = len(labels) - unique_count
    span = positions[-1] - positions[0] + 1 if positions else 0
    gap_count = max(0, span - len(positions))
    return {
        "row_index": row_index,
        "positions": positions,
        "labels": labels,
        "filled_count": len(labels),
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "text_like_count": text_like_count,
        "numeric_like_count": numeric_like_count,
        "short_label_count": short_label_count,
        "long_phrase_count": long_phrase_count,
        "service_word_hits": service_word_hits,
        "gap_count": gap_count,
    }


def _score_header_likeness(features: dict[str, Any]) -> tuple[float, list[str]]:
    if features["filled_count"] == 0:
        return -10.0, ["пустая строка"]

    score = 0.0
    reasons: list[str] = []
    filled_count = int(features["filled_count"])
    text_like_count = int(features["text_like_count"])
    short_label_count = int(features["short_label_count"])
    duplicate_count = int(features["duplicate_count"])
    numeric_like_count = int(features["numeric_like_count"])
    service_word_hits = int(features["service_word_hits"])
    long_phrase_count = int(features["long_phrase_count"])
    gap_count = int(features["gap_count"])

    score += filled_count * 1.4
    if filled_count >= 3:
        reasons.append("много заполненных ячеек")
    score += text_like_count * 1.2
    if text_like_count >= max(1, filled_count // 2):
        reasons.append("заголовки выглядят текстовыми")
    score += short_label_count * 0.8
    if short_label_count >= max(1, filled_count // 2):
        reasons.append("короткие названия колонок")

    if duplicate_count:
        score -= duplicate_count * 3.5
    if numeric_like_count >= max(2, filled_count - 1):
        score -= numeric_like_count * 1.8
    if long_phrase_count:
        score -= long_phrase_count * 2.5
    if service_word_hits:
        score -= service_word_hits * 2.8
    if gap_count:
        score -= gap_count * 0.7

    return score, reasons


def _score_data_below(
    frame: pd.DataFrame,
    row_index: int,
    features: dict[str, Any],
) -> tuple[float, dict[str, Any], list[str]]:
    positions = list(features["positions"])
    if not positions:
        return -2.0, {"stable_rows": 0, "filled_rows": 0}, ["нет колонок-кандидатов"]

    lookahead = min(len(frame.index), row_index + 1 + HEADER_LOOKAHEAD_ROWS)
    stable_rows = 0
    filled_rows = 0
    rectangular_sum = 0.0
    typed_value_hits = 0
    text_noise_rows = 0

    for next_row_index in range(row_index + 1, lookahead):
        row = frame.iloc[next_row_index].tolist()
        values = [
            _normalize_cell_text(row[position]) if position < len(row) else ""
            for position in positions
        ]
        non_empty = [value for value in values if value]
        if not non_empty:
            continue
        filled_rows += 1
        fill_ratio = len(non_empty) / max(1, len(positions))
        rectangular_sum += fill_ratio

        numeric_hits = sum(_looks_numeric(value) for value in non_empty)
        date_hits = sum(_looks_date(value) for value in non_empty)
        code_hits = sum(_looks_code(value) for value in non_empty)
        long_phrase_hits = sum(
            len(value) >= 45 or len(value.split()) >= 6 for value in non_empty
        )
        if numeric_hits or date_hits or code_hits:
            typed_value_hits += numeric_hits + date_hits + code_hits
        if long_phrase_hits >= max(1, len(non_empty) - 1):
            text_noise_rows += 1
        if fill_ratio >= 0.6 or len(non_empty) >= min(3, len(positions)):
            stable_rows += 1

    score = 0.0
    reasons: list[str] = []
    if filled_rows == 0:
        score -= 5.0
        reasons.append("ниже нет данных")
    else:
        shape_score = rectangular_sum / filled_rows
        score += stable_rows * 2.2
        score += shape_score * 4.0
        score += min(4.0, typed_value_hits * 0.4)
        if stable_rows >= 2:
            reasons.append("ниже найден табличный блок")
        if typed_value_hits:
            reasons.append("ниже видны числа/коды/даты")
        if text_noise_rows and text_noise_rows >= filled_rows:
            score -= 3.0

    metrics = {
        "stable_rows": stable_rows,
        "filled_rows": filled_rows,
        "typed_value_hits": typed_value_hits,
        "text_noise_rows": text_noise_rows,
    }
    return score, metrics, reasons


def _score_anti_patterns(features: dict[str, Any]) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons: list[str] = []
    if features["service_word_hits"]:
        penalty += features["service_word_hits"] * 1.6
        reasons.append("служебные слова")
    if features["long_phrase_count"]:
        penalty += features["long_phrase_count"] * 1.4
        reasons.append("длинные описательные фразы")
    if features["duplicate_count"]:
        penalty += features["duplicate_count"] * 1.6
        reasons.append("дубли заголовков")
    if features["gap_count"] >= 3:
        penalty += 1.5
        reasons.append("рваная структура строки")
    return penalty, reasons


def _build_explanation(
    header_reasons: list[str],
    data_reasons: list[str],
    anti_reasons: list[str],
    *,
    low_confidence: bool,
) -> str:
    parts = list(dict.fromkeys(data_reasons + header_reasons))
    if low_confidence:
        if anti_reasons:
            parts.append("обнаружены признаки служебной/описательной строки")
        if not data_reasons:
            parts.append("ниже нет уверенного табличного блока")
    return ", ".join(parts[:3]) if parts else "кандидат найден по суммарному score"


def _detect_type(series: pd.Series) -> str:
    cleaned = series.dropna()
    if cleaned.empty:
        return "unknown"
    if pd.api.types.is_bool_dtype(cleaned):
        return "boolean"
    if pd.api.types.is_integer_dtype(cleaned):
        return "integer"
    if pd.api.types.is_float_dtype(cleaned):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(cleaned):
        return "datetime"
    as_text = cleaned.astype(str)
    if as_text.str.fullmatch(r"-?\d+").all():
        return "integer"
    if as_text.str.fullmatch(r"-?\d+([.,]\d+)?").all():
        return "float"
    return "string"
