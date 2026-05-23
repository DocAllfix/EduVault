"""Unit tests for BLUEPRINT §06.1.1 Stadio 2 chunking primitives.

Targets the regex / helpers / hybrid entry point on synthetic strings —
no PDF dependency. The PDF-driven E2E lives in
``tests/integration/test_ingestion.py``.
"""

from __future__ import annotations

from app.services.ingestion_service import (
    ALLEGATO_PATTERN,
    ART_PATTERN,
    COMMA_PATTERN,
    chunk_regulation,
    chunk_structured_regulation,
    chunk_unstructured_regulation,
    compute_content_hash,
    extract_uncaptured_text,
    normalize_for_coverage,
)

REG_ID = "00000000-0000-0000-0000-000000000001"


# ─────────── ART_PATTERN ───────────


def test_art_pattern_matches_basic_article() -> None:
    text = "Art. 1 - Definizioni. Il presente decreto definisce.\n"
    matches = list(ART_PATTERN.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == "1"


def test_art_pattern_matches_bis_ter_quater() -> None:
    text = (
        "Art. 37-bis - Norme transitorie. Disposizioni.\n"
        "Art. 37-ter - Sanzioni. Pene.\n"
        "Art. 37-quater - Allegato. Estensione.\n"
    )
    nums = [m.group(1) for m in ART_PATTERN.finditer(text)]
    assert nums == ["37-bis", "37-ter", "37-quater"]


def test_art_pattern_matches_articolo_long_form() -> None:
    text = "Articolo 5 - Disposizioni generali. Contenuto.\n"
    matches = list(ART_PATTERN.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == "5"


# ─────────── COMMA_PATTERN ───────────


def test_comma_pattern_splits_numbered_paragraphs() -> None:
    text = (
        "1. Il datore di lavoro garantisce la sicurezza. "
        "2. Il lavoratore osserva le disposizioni. "
        "3. Il medico competente effettua la sorveglianza."
    )
    pairs = COMMA_PATTERN.findall(text)
    assert len(pairs) == 3
    assert [p[0] for p in pairs] == ["1", "2", "3"]


# ─────────── ALLEGATO_PATTERN ───────────


def test_allegato_pattern_matches_roman_numerals() -> None:
    text = "Allegato I - Cassetta di pronto soccorso. Contenuto minimo."
    matches = list(ALLEGATO_PATTERN.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1).strip() == "Allegato I"


# ─────────── normalize_for_coverage ───────────


def test_normalize_strips_gazzetta_header_and_page_marker() -> None:
    raw = (
        "Gazzetta Ufficiale della Repubblica Italiana Serie Generale n. 51\n"
        "Testo utile del decreto.\n— 12 —\nAltro testo utile."
    )
    norm = normalize_for_coverage(raw)
    assert "Gazzetta Ufficiale" not in norm
    assert "— 12 —" not in norm
    assert "Testo utile" in norm
    assert "Altro testo utile" in norm


# ─────────── chunk_structured_regulation ───────────


def test_structured_chunking_emits_per_comma_when_multiple() -> None:
    text = (
        "Art. 1 - Classificazione.\n"
        "1. Le aziende sono classificate in tre gruppi. "
        "2. Il datore di lavoro identifica la categoria. "
        "3. La comunicazione avviene al RLS.\n"
    )
    chunks = chunk_structured_regulation(text, REG_ID)
    # Article with 3 commi → 3 chunks (one per comma)
    assert len(chunks) == 3
    assert chunks[0]["article"] == "Art. 1"
    assert chunks[0]["paragraph"] == "Comma 1"
    assert chunks[0]["hierarchy_path"] == "Art. 1 > Comma 1"
    assert "gruppi" in chunks[0]["body"]


def test_structured_chunking_keeps_article_as_single_when_no_commi() -> None:
    text = "Art. 2 - Oggetto. Il decreto disciplina la materia.\n"
    chunks = chunk_structured_regulation(text, REG_ID)
    assert len(chunks) == 1
    assert chunks[0]["article"] == "Art. 2"
    assert chunks[0]["paragraph"] is None
    assert chunks[0]["hierarchy_path"] == "Art. 2"


def test_structured_chunking_emits_allegato_chunk() -> None:
    text = (
        "Art. 1 - Oggetto. Disciplina.\n\n"
        "Allegato I - Cassetta. "
        "Contenuto minimo: guanti monouso, garze sterili, soluzione fisiologica, "
        "pinzette sterili, teli, cerotti e bende elastiche di varie misure."
    )
    chunks = chunk_structured_regulation(text, REG_ID)
    allegati = [c for c in chunks if c["article"].startswith("Allegato")]
    assert len(allegati) == 1
    assert "guanti monouso" in allegati[0]["body"]


# ─────────── chunk_unstructured_regulation ───────────


def test_unstructured_chunking_overlaps_previous_sentence() -> None:
    text = (
        "Prima parte del paragrafo iniziale. Seconda frase del primo paragrafo che è "
        "abbastanza lunga per superare la soglia minima di cinquanta caratteri.\n\n"
        "Secondo paragrafo che parla di altre cose ed è pure abbastanza lungo per non "
        "essere scartato dal filtro di lunghezza minima."
    )
    chunks = chunk_unstructured_regulation(text, REG_ID)
    assert len(chunks) == 2
    # The 2nd chunk should carry an overlap from the last sentence of the 1st
    assert "Seconda frase del primo paragrafo" in chunks[1]["body"]


# ─────────── extract_uncaptured_text ───────────


def test_extract_uncaptured_returns_paragraphs_not_in_chunks() -> None:
    # extract_uncaptured uses body[:100] as a fingerprint, so the chunk body
    # must share its first 100 chars with the paragraph to be filtered out.
    captured_para = (
        "Paragrafo strutturato catturato dal regex lungo abbastanza per superare "
        "la soglia dei cento caratteri richiesta dal fingerprint hash truncato a 100."
    )
    orphan_para = (
        "Paragrafo orfano non catturato dalla pipeline strutturata "
        "e che deve emergere nel residual perché ha lunghezza sufficiente."
    )
    full = f"{captured_para}\n\n{orphan_para}"
    chunks = [{"body": captured_para}]  # identical body → matching fingerprint

    residual = extract_uncaptured_text(full, chunks)

    assert "orfano" in residual
    assert "strutturato catturato dal regex" not in residual


# ─────────── chunk_regulation (hybrid) ───────────


def test_hybrid_high_coverage_uses_only_structured() -> None:
    text = (
        "Art. 1 - Oggetto. Il presente decreto disciplina la materia in modo esaustivo "
        "e completo coprendo ogni aspetto rilevante della normativa applicabile.\n"
        "Art. 2 - Definizioni. Ai fini del presente decreto si intende per lavoratore "
        "la persona che presta la propria attività lavorativa nell'ambito dell'organizzazione."
    )
    chunks = chunk_regulation(text, REG_ID)
    # Pure structured, no fallback paragraphs
    assert all(c["hierarchy_path"].startswith("Art.") for c in chunks)
    assert len(chunks) == 2


def test_hybrid_low_coverage_triggers_fallback() -> None:
    # No Art. marker at all → structured pass yields 0 chunks → coverage=0
    # → fallback paragraph chunker activates.
    text = (
        "Premessa narrativa molto estesa che non segue lo schema Art./Comma e che "
        "rappresenta tutto il testo di un documento non strutturato.\n\n"
        "Secondo paragrafo narrativo, sempre senza struttura normativa esplicita, "
        "che insieme al primo deve attivare il fallback per copertura sotto soglia.\n\n"
        "Terzo paragrafo discorsivo da catturare con overlap di una frase dal "
        "paragrafo precedente per garantire continuità semantica nel chunking."
    )
    chunks = chunk_regulation(text, REG_ID)
    assert chunks, "fallback must produce at least one chunk"
    assert all(c["hierarchy_path"].startswith("Paragrafo") for c in chunks)


# ─────────── compute_content_hash ───────────


def test_content_hash_is_64_hex_chars() -> None:
    h = compute_content_hash("Art. 1 - Oggetto. Disciplina.")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_is_deterministic_and_distinct() -> None:
    body_a = "Il datore di lavoro garantisce la sicurezza dei lavoratori."
    body_b = "Il datore di lavoro garantisce la sicurezza dei lavoratori "  # trailing space
    assert compute_content_hash(body_a) == compute_content_hash(body_a)
    assert compute_content_hash(body_a) != compute_content_hash(body_b)
