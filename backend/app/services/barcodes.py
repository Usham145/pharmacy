from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit


_GTIN_LENGTHS = {8, 12, 13, 14}


def _is_valid_gtin(value: str) -> bool:
    if len(value) not in _GTIN_LENGTHS or not value.isdigit():
        return False
    weighted_sum = sum(
        int(digit) * (3 if offset % 2 == 0 else 1)
        for offset, digit in enumerate(reversed(value[:-1]))
    )
    return (10 - weighted_sum % 10) % 10 == int(value[-1])


def product_barcode_key(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("Barcode cannot be blank")

    if raw.startswith("]d2"):
        raw = raw[3:]

    parsed_url = urlsplit(raw)
    if parsed_url.scheme in {"http", "https"} and parsed_url.netloc:
        segments = [unquote(segment) for segment in parsed_url.path.split("/") if segment]
        for index, segment in enumerate(segments[:-1]):
            gtin = segments[index + 1]
            if segment == "01" and len(gtin) == 14 and _is_valid_gtin(gtin):
                return gtin.zfill(14)

    gs1_match = re.match(r"^01(\d{14})(?:\x1d|10|17|21|$)", raw)
    if gs1_match and _is_valid_gtin(gs1_match.group(1)):
        return gs1_match.group(1).zfill(14)

    if _is_valid_gtin(raw):
        return raw.zfill(14)
    return raw
