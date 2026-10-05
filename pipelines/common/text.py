"""Prompt rendering and reply parsing shared by both pipelines.

Every LLM step works the same way:
    prompt = render(template_name, **fields)       # str
    value, ok = parse_xxx(reply)                    # ok=False -> step falls back
Parsers never raise: a malformed reply is a measurable event (parse_ok=False),
not a crash, because cheap models producing bad output is what we study.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class TemplateError(ValueError):
    pass


def load_template(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def render(template: str, **fields: object) -> str:
    """Fill {{name}} placeholders. Missing or unused fields are errors."""
    needed = placeholders(template)
    missing = needed - fields.keys()
    extra = fields.keys() - needed
    if missing:
        raise TemplateError(f"missing fields: {sorted(missing)}")
    if extra:
        raise TemplateError(f"unused fields: {sorted(extra)}")
    # Single pass, so a field value that happens to contain {{x}} is left alone.
    return _PLACEHOLDER.sub(lambda m: str(fields[m.group(1)]), template)


_FENCE = re.compile(r"```[ \t]*([a-zA-Z0-9_-]*)[ \t]*\n(.*?)```", re.DOTALL)


def code_blocks(reply: str, lang: str | None = None) -> list[str]:
    """All fenced code blocks, optionally only those tagged with `lang`."""
    out = []
    for tag, body in _FENCE.findall(reply or ""):
        if lang is None or tag.lower() == lang:
            out.append(body.strip())
    return out


def _first_json_object(text: str) -> object | None:
    """Find the first decodable JSON object anywhere in text."""
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(text[i:])
                return obj
            except json.JSONDecodeError:
                continue
    return None


def parse_json_reply(reply: str) -> tuple[dict | None, bool]:
    """JSON from a ```json block if present, else the first {...} in the reply."""
    for body in code_blocks(reply, "json") + code_blocks(reply, ""):
        obj = _first_json_object(body)
        if isinstance(obj, dict):
            return obj, True
    obj = _first_json_object(reply or "")
    if isinstance(obj, dict):
        return obj, True
    return None, False


def last_sql(reply: str) -> tuple[str, bool]:
    """The SQL in the last ```sql block (MAC-SQL convention). Falls back to an
    untagged block that starts with SELECT/WITH."""
    blocks = code_blocks(reply, "sql")
    if not blocks:
        blocks = [b for b in code_blocks(reply, "") if re.match(r"(?is)\s*(select|with)\b", b)]
    if not blocks:
        return "", False
    sql = blocks[-1].strip().rstrip(";").strip()
    return sql, bool(sql)
