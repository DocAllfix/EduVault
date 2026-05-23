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
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2011"],
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
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2011"],
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
        "title": "Primo Soccorso Gruppi B e C",
        "regs": ["dlgs_81_08", "dm_388_2003"],
        "min_hours": 12,
        "max_hours": 12,
        "default_modules": [
            "Allertare il sistema di soccorso",
            "Riconoscere emergenza sanitaria",
            "Attuare interventi primo soccorso",
            "Conoscenze generali sui traumi",
            "Conoscenze generali patologie",
            "Acquisire capacità di intervento pratico",
        ],
    },
    "antincendio_livello_1": {
        "title": "Addetto Antincendio Livello 1",
        "regs": ["dlgs_81_08", "dm_02_09_2021"],
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
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2011"],
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
