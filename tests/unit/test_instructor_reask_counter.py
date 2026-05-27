"""FIX #31 MOSSA 4 — Counter reask instructor invisibili.

L'analista (2026-05-27) ha segnalato un buco di osservabilità: i reask
di profondità (bullet/notes/validator failures) erano invisibili nei log
finora — vedevamo solo gli 8 reask diagram perché hanno
`diagram_filling_failed` con log dedicato. Il counter locale aggiunto a
``_instructor_client_for`` chiude il buco.

Test coverage:
1. La firma di ``_instructor_client_for`` ritorna ora una tupla a 3
   elementi: ``(client, model_id, counter_dict)``.
2. Il counter è inizializzato a ``{"reasks": 0}``.
3. Il counter è LOCALE per call: due chiamate consecutive producono due
   counter indipendenti (no stato globale, no race).
4. L'hook ``client.on("completion:error", ...)`` è installato e
   incrementa il counter quando chiamato.

NB: NON testiamo l'integrazione vera con instructor + LLM provider
(richiederebbe API key live). Testiamo l'invariant strutturale e il
comportamento del counter.
"""

from __future__ import annotations

import pytest

from app.services.ingestion_service import _instructor_client_for


def test_instructor_client_for_returns_three_tuple() -> None:
    """FIX #31 MOSSA 4: signature change. Era 2-tuple, ora 3-tuple.
    Tutti i 2 call site in generate_module_structured devono unpack
    a 3 elementi."""
    result = _instructor_client_for("openai", "gpt-4o-mini")
    assert len(result) == 3, f"expected 3-tuple, got {len(result)}-tuple"
    client, model_id, counter = result
    assert client is not None
    assert model_id == "gpt-4o-mini"
    assert isinstance(counter, dict)


def test_reask_counter_initialized_to_zero() -> None:
    """Il counter inizia sempre a 0 reasks per ogni nuova chiamata."""
    _client, _model, counter = _instructor_client_for("openai", "gpt-4o-mini")
    assert counter == {"reasks": 0}


def test_reask_counter_is_local_per_call_not_global() -> None:
    """Due chiamate consecutive producono counter INDIPENDENTI.
    Incrementare uno non tocca l'altro. Garanzia anti-race in test
    paralleli e in pipeline con N moduli concurrent."""
    _, _, counter_a = _instructor_client_for("openai", "gpt-4o-mini")
    _, _, counter_b = _instructor_client_for("openai", "gpt-4o-mini")

    assert counter_a is not counter_b  # NON stesso oggetto

    counter_a["reasks"] = 5
    assert counter_b["reasks"] == 0, (
        "counter_b deve essere indipendente da counter_a"
    )


def test_reask_counter_increments_when_hook_fires() -> None:
    """L'hook ``on('completion:error')`` è installato e funziona:
    emettendo l'evento via l'API pubblica di instructor (``hooks.emit_*``),
    il counter incrementa.

    Usiamo ``hooks.emit_completion_error(exc)`` perché è l'API pubblica
    documentata di instructor per dispatchare i ``completion:error``.
    """
    client, _model, counter = _instructor_client_for("openai", "gpt-4o-mini")
    assert counter["reasks"] == 0

    # Emetti 3 volte l'evento per simulare 3 validation retry consecutivi
    fake_exc = ValueError("simulated validation failure on bullets")
    for _ in range(3):
        client.hooks.emit_completion_error(fake_exc)

    assert counter["reasks"] == 3, (
        f"hook deve incrementare counter, got {counter['reasks']} expected 3"
    )


def test_reask_counter_survives_in_telemetry_aggregation() -> None:
    """Simulazione mini-integration: i counter di N batch si sommano
    nel `telemetry['reask_total_module']` cumulativo. Pattern usato in
    generate_module_structured."""
    telemetry = {"reask_total_module": 0}
    for _batch_idx in range(3):
        _, _, counter = _instructor_client_for("openai", "gpt-4o-mini")
        # Simula 2 reask in questo batch
        counter["reasks"] = 2
        telemetry["reask_total_module"] = int(
            telemetry.get("reask_total_module", 0)
        ) + counter["reasks"]

    assert telemetry["reask_total_module"] == 6
