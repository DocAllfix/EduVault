# config/catalog_config.py
"""Catalog of generatable course types (BLUEPRINT §13).

Each entry maps a slug -> required regulations + structural parameters.
The slugs in "regs" must match regulations.slug in the database. The
Research Agent calls resolve_slugs_to_ids() to validate them before the
RAG query.

Values are heterogeneous (str / list[str] / int / bool), so the dict is
typed dict[str, dict[str, object]] — a TypedDict is intentionally NOT used
here (CLAUDE.md restricts TypedDict to agents/pipeline.py).
"""

from __future__ import annotations

COURSE_CATALOG: dict[str, dict[str, object]] = {
    "sicurezza_lavoratori_generale": {
        "title": "Formazione Generale Lavoratori",
        # Normativa vigente: nuovo Accordo Stato-Regioni 17/04/2025 (GU 119 del
        # 24/05/2025) sostituisce 2011+2016. Periodo transitorio chiuso il
        # 23/05/2026 — i corsi col vecchio Accordo non sono più erogabili sul
        # portale cliente (corsi8108) da quella data.
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2025"],
        "min_hours": 4,
        "max_hours": 4,
        "default_modules": [
            "Concetti di rischio",
            "Prevenzione e protezione",
            "Organizzazione della prevenzione",
            "Diritti e doveri",
        ],
    },
    "sicurezza_lavoratori_specifica_basso": {
        "title": "Formazione Specifica Rischio Basso",
        # Accordo Stato-Regioni 17/04/2025 vigente (vedi nota su generale).
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2025"],
        "min_hours": 4,
        "max_hours": 4,
        "default_modules": [
            "Rischi specifici",
            "DPI",
            "Procedure di emergenza",
            "Segnaletica",
        ],
    },
    "primo_soccorso_gruppo_b_c": {
        # Riferimento ufficiale corsi8108: 8 ore totali online (Modulo A 4h +
        # Modulo B 4h). Modulo C (4h pratica in presenza) escluso da v1.
        # Normative: D.Lgs 81/08 art. 45 c.2 + DM 388/2003 (gruppi B/C).
        "title": "Primo Soccorso — Gruppi B e C",
        "regs": ["dlgs_81_08", "dm_388_2003"],
        "min_hours": 8,
        "max_hours": 8,
        "default_modules": [
            # Modulo A (4h): legislazione + allertamento + riconoscimento + autoprotezione
            "Aspetti legislativi e allertamento sistema di soccorso",
            "Riconoscimento emergenze sanitarie e tecniche di autoprotezione",
            "Patologie acute: shock, edema polmonare, asma, allergie, lipotimia",
            # Modulo B (4h): traumi + lesioni + emorragie
            "Traumi scheletrici, cranio-encefalici e della colonna vertebrale",
            "Lesioni da agenti fisici e chimici, intossicazioni",
            "Emorragie e ferite — gestione delle urgenze",
        ],
    },
    "primo_soccorso_gruppo_a": {
        # Riferimento ufficiale corsi8108: 10 ore totali online (Modulo A 6h +
        # Modulo B 4h). Modulo C (6h pratica in presenza) escluso da v1.
        # Profilo rischio ALTO: aziende centrali termoelettriche, miniere, agenti
        # biologici g.3-4, esplosivi, cantieri >5 lav/anno, alto rischio INAIL.
        # Normative: D.Lgs 81/08 art. 45 c.2 + DM 388/2003 (gruppo A).
        "title": "Primo Soccorso — Gruppo A",
        "regs": ["dlgs_81_08", "dm_388_2003"],
        "min_hours": 10,
        "max_hours": 10,
        "default_modules": [
            # Modulo A (6h): legislazione + intervento operativo BLS
            "Aspetti legislativi del primo soccorso in aziende ad alto rischio",
            "Allertamento del sistema di soccorso e accertamento condizioni psicofisiche",
            "Tecniche di autoprotezione e sostentamento delle funzioni vitali",
            "Respirazione artificiale e massaggio cardiaco esterno (BLS)",
            "Riconoscimento shock, edema polmonare, asma, reazioni allergiche, emorragie",
            # Modulo B (4h): traumi + lesioni + emorragie (identico a B/C)
            "Traumi in ambiente di lavoro: fratture, lussazioni, traumi cranici e spinali",
            "Lesioni toracico-addominali, da freddo/calore, corrente elettrica e agenti chimici",
            "Intossicazioni, ferite lacero-contuse, emorragie esterne",
        ],
    },
    # CLUSTER D test only: course_type minimo per pipeline E2E live senza
    # dover ingerire D.Lgs 81/08 (581 pp = ~30 min). Da rimuovere post-test.
    "primo_soccorso_test_dm388_only": {
        "title": "Primo Soccorso — Test DM 388 only",
        "regs": ["dm_388_2003"],
        "min_hours": 1,
        "max_hours": 1,
        "default_modules": [
            "Allertare il sistema di soccorso",
            "Riconoscere emergenza sanitaria",
        ],
    },
    "antincendio_livello_1": {
        "title": "Addetto Antincendio Livello 1",
        # Corpus antincendio VIGENTE 2026 (post-review-17 analista): i 3 DM
        # del settembre 2021 sostituiscono il DM 10/03/1998 ABROGATO dal
        # 29/10/2022. dm_02_09 (gestione+livelli formativi), dm_03_09
        # (minicodice criteri generali), dm_01_09 (controlli impianti).
        "regs": ["dlgs_81_08", "dm_02_09_2021", "dm_03_09_2021", "dm_01_09_2021"],
        "min_hours": 4,
        "max_hours": 4,
        "default_modules": [
            "Principi dell'incendio",
            "Prevenzione incendi",
            "Protezione antincendio",
            "Procedure operative",
        ],
    },
    "haccp_addetto": {
        "title": "Formazione HACCP Addetti",
        "regs": ["reg_ce_852_2004"],
        "min_hours": 4,
        "max_hours": 8,
        "regional": True,  # activates the regional filter in the Research Agent
        "default_modules": [
            "Principi HACCP",
            "Igiene degli alimenti",
            "Rischi biologici e chimici",
            "Autocontrollo e documentazione",
        ],
    },
    "preposti": {
        "title": "Formazione Preposti",
        # Accordo Stato-Regioni 17/04/2025 vigente (il nuovo Accordo ha rafforzato
        # la formazione preposti: durata minima ora 12h, da verificare a catalogo
        # in FASE 7 — qui si aggiorna solo la fonte normativa RAG).
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2025"],
        "min_hours": 8,
        "max_hours": 8,
        "default_modules": [
            "Principali soggetti del sistema di prevenzione",
            "Relazioni tra i vari soggetti",
            "Definizione e individuazione dei fattori di rischio",
            "Incidenti e infortuni mancati",
            "Tecniche di comunicazione e sensibilizzazione",
            "Valutazione dei rischi dell'azienda",
        ],
    },
}
