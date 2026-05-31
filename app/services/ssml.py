"""F7.2 — SSML converter for break markers (vast-hopping §F7.2).

Converte `(PAUSE Ns)` markers nelle narrazioni in `<break time="Ns"/>` SSML
per Azure Speech SDK. XML-escape special chars `&<>` PRIMA del replace per
non corrompere SSML output. Wrap in `<speak version="1.0" xmlns=...>` con
voice name esplicito.

Cap massimo 10 break/text (anti-abuse: utente potrebbe scrivere 100
(PAUSE) e bloccare TTS rendering).

Riusato anche per Edge-TTS quando supporta SSML (es. multi-voice prosody)
ma DEFAULT path Edge-TTS resta plain text (compatibilita' v1 invariata).
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

# Pattern: (PAUSE Ns) o (PAUSE N s) case insensitive, optional decimal
_PAUSE_PATTERN = re.compile(
    r"\(\s*PAUSE\s+(\d+(?:\.\d+)?)\s*s?\s*\)",
    re.IGNORECASE,
)

# Max numero di break consentito per text (anti-abuse)
MAX_BREAKS = 10


def text_to_ssml(text: str, voice: str) -> str:
    """Convert plain text con `(PAUSE Ns)` markers in SSML completo.

    Args:
        text: narration plain text con eventuali `(PAUSE 2s)` markers.
        voice: nome voce Azure (es. "it-IT-DiegoNeural"). NON validato qui.

    Returns:
        SSML string `<speak ...><voice ...>...</voice></speak>` con
        `<break time="Ns"/>` al posto dei `(PAUSE Ns)`.

    Cap: max MAX_BREAKS sostituzioni per text. Il resto resta come testo.
    """
    if not text:
        # Minimal valid SSML even for empty text (Azure rifiuta empty)
        return (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="it-IT"><voice name="{escape(voice, {chr(34): "&quot;"})}">'
            f'</voice></speak>'
        )

    # 1. Escape special chars (NON pre-escape parentheses pattern)
    safe = escape(text, {'"': "&quot;", "'": "&apos;"})

    # 2. Replace markers cap MAX_BREAKS
    replacements_count = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal replacements_count
        if replacements_count >= MAX_BREAKS:
            return match.group(0)  # mantieni original text per il resto
        replacements_count += 1
        n = float(match.group(1))
        # Cap time per security: max 10s (Azure rifiuta > 10s anyway)
        n = min(n, 10.0)
        return f'<break time="{n}s"/>'

    body = _PAUSE_PATTERN.sub(_replace, safe)

    voice_escaped = escape(voice, {chr(34): "&quot;"})
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="it-IT"><voice name="{voice_escaped}">{body}</voice></speak>'
    )


def count_breaks(text: str) -> int:
    """Utility: quanti `(PAUSE Ns)` markers nel testo? Usato per audit."""
    return len(_PAUSE_PATTERN.findall(text))


__all__ = ["text_to_ssml", "count_breaks", "MAX_BREAKS"]
