from __future__ import annotations

import json
import os
from pathlib import Path

_locales: dict[str, dict] = {}
_LOCALES_DIR = Path(__file__).parent / 'locales'


def _load_locale(lang: str) -> dict | None:
    if lang in _locales:
        return _locales[lang]
    path = _LOCALES_DIR / f'{lang}.json'
    try:
        with open(path, encoding='utf-8') as f:
            _locales[lang] = json.load(f)
        return _locales[lang]
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# Pre-load known locales
_load_locale('en')
_load_locale('es')


def t(key: str, lang: str = 'en', vars: dict | None = None) -> str:
    """Get a translated string by dot-separated key."""
    locale = _load_locale(lang) or _load_locale('en') or {}
    fallback = _load_locale('en') or {}

    def resolve(obj: dict, parts: list[str]) -> str | None:
        cur = obj
        for part in parts:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur if isinstance(cur, str) else None

    parts = key.split('.')
    result = resolve(locale, parts) or resolve(fallback, parts) or key

    if vars:
        for k, v in vars.items():
            result = result.replace('{{' + k + '}}', str(v))

    return result
