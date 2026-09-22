from __future__ import annotations

import hashlib
import json
import re


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "project"


def redact(value: str) -> str:
    patterns = [
        r"(?i)(api[_-]?key|token|secret|password|senha)\s*[:=]\s*\S+",
        r"sk-[A-Za-z0-9_-]{12,}",
        r"Bearer\s+[A-Za-z0-9._-]+",
    ]
    result = value
    for pattern in patterns:
        result = re.sub(pattern, "[REDACTED]", result)
    return result

