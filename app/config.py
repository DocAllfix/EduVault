"""Typed environment configuration (OPT-2 v3.0).

Single source of truth for all environment variables. Every other module
MUST use `from app.config import settings` — direct `os.environ[]` access
is forbidden (OPT-2).

This file deliberately follows pydantic-settings v2 (not the legacy
module-level constants pattern shown in BLUEPRINT §02.5/§02.6, which
predates OPT-2). Field names map 1:1 to upper-case env vars per
pydantic-settings default behavior (e.g. ``database_url`` <- ``DATABASE_URL``).
"""

from __future__ import annotations

import logging
from typing import Literal

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings, validated at startup."""

    # === Database (BP §02.6) ===
    database_url: str  # postgresql://nexus_app:...@postgres:5432/nexus
    database_admin_url: str = ""  # seed.py + migrations only (nexus_admin)

    # === API keys (BP §02.6) ===
    anthropic_api_key: str
    voyage_api_key: str
    brave_search_api_key: str = ""
    # Cluster F: Pexels primary image provider (free tier ~200/h, no attribution)
    # https://www.pexels.com/api/new/
    pexels_api_key: str = ""
    # FIX #18 (2026-05-25): Pixabay fallback intermedio (5000/h free auth)
    # Registrazione gratuita: https://pixabay.com/api/docs/
    pixabay_api_key: str = ""
    # FIX #22 (2026-05-25): Openverse OAuth2 (100/min, 10K/day vs 20/min anon)
    # Registrazione gratuita: POST /v1/auth_tokens/register/ + verify email
    openverse_client_id: str = ""
    openverse_client_secret: str = ""

    # === Auth — single JWT secret, token type in payload (BP §08.1) ===
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    jwt_refresh_expiry_days: int = 7

    # === CORS — explicit origin, never wildcard (REI-10) ===
    frontend_url: str = "http://localhost:3000"

    # === Pipeline (BP §1.4 D-02 — MAX_CONCURRENT_JOBS must stay 1) ===
    pipeline_timeout: int = 1800
    llm_request_timeout: int = 120
    max_concurrent_jobs: int = 1

    # === LLM provider selection (FASE 0b vast-hopping-sketch) ===
    # Default: Azure OpenAI gpt-4.1-mini (10× cheaper than Sonnet 4.6, JSON mode
    # strict nativo, 200K TPM). Anthropic resta come L2 fallback emergenza.
    llm_provider: Literal["anthropic", "azure_openai", "openai", "deepseek"] = "deepseek"

    # OpenAI diretto (fallback L1)
    openai_api_key: str = ""
    openai_content_model: str = "gpt-4o"
    openai_classify_model: str = "gpt-4o-mini"

    # DeepSeek V4 — provider PRIMARY 2026-05-25.
    # PRO è un REASONING model: ottimo per ragionare sui constraints ma:
    # - 2-3× più costoso (token reasoning fatturati)
    # - latenza 10-30s/call (vs 5-10s flash)
    # - JSON mode talvolta conflitta (content vuoto, tutto reasoning)
    # FLASH è il non-thinking, output diretto, 3× più economico, qualità OK
    # per slide normative italiane. Pro resta L1 fallback (vedi chain in
    # ingestion_service) e per override manuale corsi complessi.
    deepseek_api_key: str = ""
    deepseek_content_model: str = "deepseek-v4-flash"  # default non-thinking
    deepseek_classify_model: str = "deepseek-v4-flash"
    deepseek_premium_model: str = "deepseek-v4-pro"    # reasoning per override

    # === Azure OpenAI (primary L0 + premium L1 fallback) ===
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment_content: str = "gpt-4.1-mini"   # L0: primary
    azure_openai_deployment_classify: str = "gpt-4.1-mini"  # classify_chunk
    azure_openai_deployment_premium: str = "gpt-4o"         # L1: fallback premium

    # F-PERF 2026-06-01 FASE 3 — Tier Azure OpenAI gpt-4.1-mini.
    # Italy North Global Standard: 46M TPM (era 200k, +230×).
    # Concurrency cap derivato dal budget tokens-per-minute SENZA degradare
    # qualita' (nessun cambio modello, deployment, prompts, retry interni):
    # - classify_chunk (settings.classify_max_concurrent): chunk avg ~3500
    #   tokens. 46M TPM / (3500 × 5s/60s) ≈ 157k RPS teorici. Cap 200
    #   concurrent = ~84k TPM/sec picco → 5M TPM sustained, ~11% budget.
    # - content_agent (settings.content_agent_concurrency, riga 125): cap 50
    #   moduli simultaneamente. Calcolato a riga 125 docstring.
    # Qualita': cap concurrency NON tocca prompt, instructor schema,
    # retry interno fill_loop, structured output. Solo velocita'.
    azure_openai_tpm: int = 46_000_000
    classify_max_concurrent: int = 200

    # F-PERF FASE 3 — Voyage embed batch boost
    # Voyage v3 supporta batch 1024 (era 128). Triplica throughput embed
    # senza degradare qualita' (stesso modello, stessa dimensione).
    voyage_embed_batch_size: int = 512

    # === Anthropic (legacy + L2 fallback emergenza) ===
    # llm_classify_model / llm_content_model = nomi dei modelli Anthropic usati SOLO
    # quando llm_provider="anthropic" oppure quando il fallback raggiunge L2.
    llm_classify_model: str = "claude-haiku-4-5-20251001"
    llm_content_model: str = "claude-sonnet-4-6"
    llm_content_model_fallback: str = "claude-sonnet-4-6"   # L2 emergenza content_agent

    # === Parallelizzazione moduli ===
    # FIX #29.3 (2026-05-26): 100→10. Con TOOLS mode + Azure mini (200K TPM standard),
    # 100 moduli paralleli saturavano il TPM e producevano timeout HTTP senza 429
    # espliciti (Azure mette in coda invece di rifiutare). 10 lascia ~6 chiamate
    # parallele effettive in volo con margine ai retry instructor — dimensionato sui
    # token, non sui moduli (ogni batch da 7 slide ~8K token, vedi FIX #29.1).
    content_agent_concurrency: int = 50  # F-PERF 2026-06-01 FASE 3: era 20, alzato a 50 con quota Italy North 46M TPM (~7.5M TPM picco = 16% del budget). Corsi 8h hanno 24 moduli → tutti in volo simultaneamente con buffer retry. Qualita' invariata (no prompt/schema change).
    voci_per_module_concurrency: int = 4  # F-PERF 2026-06-01 FASE 4: parallelizza loop voce-per-voce intra-modulo (D-201). Era sequenziale (n_voci × ~80s LLM call = 9min bottleneck). 4 voci/modulo concorrenti × 10 moduli = 40 LLM concorrenti picco × ~5K token = 200K TPM (~0.4% budget 46M). Ordine slide preservato via gather index-aligned.

    # === F-STUDIO-UX 2026-06-01 Step 0 (D-207): preview source PPTX-fedele ===
    # "pptx": preview.png = render LibreOffice headless del PPTX scaricabile
    #   → utente vede in webapp ESATTAMENTE ciò che ha nel file finale (immagini,
    #   diagrammi, layout python-pptx). VERIFICATO IN PROD su corso af08e1d1:
    #   soffice consumava troppa RAM su 342 slide → container OOM-killed (502
    #   "Application failed to respond"). Disabilitato di default.
    # "pdf_dispensa" (default, legacy stable): rendering del PDF dispensa
    #   Jinja2+WeasyPrint testo-only. Non e` fedele al PPTX (no immagini) ma
    #   non crasha. Per riabilitare "pptx" servirà strategia memory-safe
    #   (es. extract single-slide via python-pptx + soffice page-range).
    preview_source: Literal["pptx", "pdf_dispensa"] = "pdf_dispensa"
    tts_voice: str = "it-IT-DiegoNeural"

    # === v2 refactor — provider keys (Fase 0 piano vast-hopping-sketch v2) ===
    # Tutti opzionali finché i corrispondenti feature flag sotto sono False.
    cohere_api_key: str = ""             # D2 rerank-multilingual-v3.0 (Cohere API, no model in-process)
    azure_speech_key: str = ""           # D6 Azure Cognitive Services Speech SDK (SSML completo)
    azure_speech_region: str = ""        # es. "westeurope"
    voyage_multimodal_model: str = "voyage-multimodal-3"  # D4 image library embedding

    # === v2 refactor — feature flags (VAA-e: safety-net dietro flag) ===
    # Ogni nuovo componente v2 legge il flag corrispondente. Default tutti False:
    # comportamento pipeline v1 invariato finché il flag non viene alzato per
    # famiglia di corsi nella promozione A/B (D10).
    #
    # NOTA: pydantic-settings v2 mappa nested dict da env solo via JSON
    # (V2_FEATURES='{"rerank_enabled":true}'). Per semplicità ops, ogni flag è
    # un campo bool top-level con prefisso V2_.
    v2_rerank_enabled: bool = False          # D2: rerank Cohere a 2 stadi (recall+rerank)
    v2_kg_traversal_enabled: bool = False    # D1: 1-hop graph traversal post-rerank
    v2_drop_list_enabled: bool = True        # SAFETY-NET: drop-list regex v1 attive (D10 spegne per famiglia)
    v2_skeleton_validation: bool = False     # D3: scheletro narrativo + gate 1-click utente
    v2_catalog_from_db: bool = False         # D8: lettura catalogo da DB invece di catalog_config.py
    v2_chat_enabled: bool = False            # D7: chat-panel in Course Studio (F1 actions)
    v2_chat_mutations_enabled: bool = False  # D7 F2: tool-use mutations (oggi NO)
    v2_image_library_enabled: bool = False   # D4: image library prima di Pexels web
    v2_audio_provider_azure: bool = False    # D6: Azure Speech SDK con SSML (default edge-tts)
    v2_quality_badges_enabled: bool = False  # D9: badge UI slide problematiche
    v2_b2_cosine_selector_enabled: bool = False  # F2.12 B2: top-K cosine_voyage selector (sostituisce Cohere ranking)
    v2_b3_cross_title_decay_enabled: bool = False  # F2.13 B3: cross-Titolo decay sul pool B2 (D-166 chiusura via top_section column)
    b3_decay_factor: float = 0.4   # F2.13 B3: peso decay per chunk cross-titolo (analista sign-off 2026-05-30)
    b3_threshold_ratio: float = 0.30  # F2.13 B3: soglia scarto = max_pool * ratio (auto-adattiva, sign-off analista)
    b3_min_observations: int = 4   # F2.13 B3: numero minimo chunks per regulation per applicare decay. Se n_obs(rid) < soglia, dominante e' rumore statistico (3 obs split 2:1 = singola differenza) -> skip B3 sui chunks di quella regulation (do no harm sotto incertezza). Sign-off analista 2026-05-30 post-osservazione GEN M1 Art. 236 false-discard.
    v2_b3_strong_dominance_enabled: bool = False  # H8b-γ3 (analista 2026-05-31 post H8 verdict 22.4% core): B3 escalation hard_discard quando dominanza_per_regulation supera soglia. Estensione naturale di B3 esistente, zero conoscenza course-specific (NO Tabella 2 mascherata).
    b3_strong_dominance_threshold: float = 0.70  # H8b-γ3: ratio (winner_count / total_chunks_per_reg) sopra cui regulation e' considerata "strong dominance". Su pool ben-dominato (>=70% chunks della top_section dominante), cross-titolo chunks vengono hard_discard invece di decay_kept. Su pool diversificati (<70%) comportamento legacy invariato. Calibrato sul sample-read M0 post-H8 (cluster #35-41 Titolo III in pool dominato Titolo I 78%).
    v2_b4_corpus_thin_enabled: bool = False  # F2.14 B4: D9 vincolante corpus-thin (Caso 1 sign-off analista 2026-05-30 post-sample-read M0 PPTX). Caso 2+3 esclusi (richiedevano Tabella 2 course_type->expected_titoli, vanno a F2.13 D8 catalog DB).
    b4_min_chunks_per_voice: int = 3   # F2.14 B4: soglia n_chunks_per_regulation_per_voce. Se una regulation ha meno chunks di questa soglia nel pool finale post-B3 di una voce -> corpus thin per quella voce. Default start point analista 2026-05-30, calibrazione dai prossimi E2E.
    b4_corpus_thin_behavior: str = "block"  # F2.14 B4: "block" (default sicura) | "mark_only" (scappatoia). Block: warning visibile in generation_jobs.status, UI mostra all'operatore prima del replay. Mark_only: genera comunque + scrive low_corpus_confidence in metadata slide. Analista sign-off 2026-05-30: default block, mark_only solo se operatore esperto override.

    # F8 — Cleanup A/B per famiglia (D10, vast-hopping §F8 post-MVP 2026-05-31).
    # Ogni flag spegne il drop-list pattern di UNA famiglia di corsi. Default
    # TRUE (drop attivi = pipeline v1 invariata, safety-net D10). Quando flag
    # viene messo a FALSE su Railway env per una famiglia, quel drop-pattern e'
    # disabilitato per quella famiglia → A/B comparison contro baseline.
    # Promozione: famiglia "verde" (badge D9 = 0, qualita' >= analista review 10)
    # → flag rimosso permanente in commit chirurgico + pattern eliminato dal codice.
    # NO big-bang: 12 famiglie, 1 per volta.
    v2_drop_segnaletica_enabled: bool = True       # corso Lavoratori Specifica, modulo "Segnaletica"
    v2_drop_prevenzione_generale_enabled: bool = True  # corso Lavoratori Generale, modulo "Prevenzione e protezione"
    v2_drop_incidenti_preposti_enabled: bool = True    # corso Preposti, modulo "Incidenti mancati"

    @property
    def v2_features(self) -> dict[str, bool]:
        """Vista aggregata dei flag v2 per logging/debug.

        Restituisce un dict {feature_name: enabled} comodo da serializzare in
        un log structured event a startup, così l'operatore vede sempre
        quali componenti v2 sono attivi nel container corrente.
        """
        return {
            "rerank_enabled": self.v2_rerank_enabled,
            "kg_traversal_enabled": self.v2_kg_traversal_enabled,
            "drop_list_enabled": self.v2_drop_list_enabled,
            "skeleton_validation": self.v2_skeleton_validation,
            "catalog_from_db": self.v2_catalog_from_db,
            "chat_enabled": self.v2_chat_enabled,
            "chat_mutations_enabled": self.v2_chat_mutations_enabled,
            "image_library_enabled": self.v2_image_library_enabled,
            "audio_provider_azure": self.v2_audio_provider_azure,
            "quality_badges_enabled": self.v2_quality_badges_enabled,
            "b2_cosine_selector_enabled": self.v2_b2_cosine_selector_enabled,
            "b3_cross_title_decay_enabled": self.v2_b3_cross_title_decay_enabled,
            "b3_strong_dominance_enabled": self.v2_b3_strong_dominance_enabled,
            "b4_corpus_thin_enabled": self.v2_b4_corpus_thin_enabled,
        }

    # === Branding ===
    organization_name: str = "corsi8108"

    # === Seed (BP §02.7 + REI-13: domain NOT decided) ===
    # Used by scripts/seed.py on first run only.
    # Email host is intentionally a placeholder until PHASE 7 (REI-13).
    admin_bootstrap_email: str = "admin@<DOMAIN_TBD>"
    admin_bootstrap_password: str = "CHANGE_ME"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()


def configure_logging() -> None:
    """Configure structlog (REI-7: structured JSON logs, never print()).

    Called once in app.main.startup() per BLUEPRINT §02.5.
    """
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
