"""Alias normalization for demo objects (IMPLEMENTATION §11).

Lightweight map for known demo objects only. Sophisticated identity resolution is
explicitly out of scope for the MVP.
"""

from __future__ import annotations

import re

ALIASES: dict[str, str] = {
    # ESP32
    "esp32": "ESP32",
    "esp32 development board": "ESP32",
    "esp32 dev board": "ESP32",
    "development board": "ESP32",
    "dev board": "ESP32",
    "small circuit board": "ESP32",
    "circuit board": "ESP32",
    "microcontroller": "ESP32",
    "micro controller": "ESP32",
    # phone
    "phone": "phone",
    "mobile phone": "phone",
    "smartphone": "phone",
    "cell phone": "phone",
    "cellphone": "phone",
    # notebook
    "notebook": "notebook",
    "notepad": "notebook",
    "note pad": "notebook",
    # bottle
    "bottle": "bottle",
    "water bottle": "bottle",
    "waterbottle": "bottle",
}


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def normalize_name(name: str) -> str:
    """Return a canonical demo-object name, else a cleaned lowercased name."""
    key = _clean(name)
    if key in ALIASES:
        return ALIASES[key]
    # Try a substring match for e.g. "green esp32 board".
    for alias, canonical in ALIASES.items():
        if alias in key:
            return canonical
    return key


def object_key(name: str) -> str:
    """Stable key for object_history lookups."""
    return normalize_name(name).lower()
