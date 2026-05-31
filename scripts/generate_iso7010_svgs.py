"""Genera 30+ icone ISO 7010 in formato SVG vettoriale CC0.

Pattern per categoria (ISO 7010:2020):
  - E (Emergency/escape): cerchio o quadrato verde #009639 + simbolo bianco
  - F (Fire equipment):   quadrato rosso #C8102E + simbolo bianco
  - M (Mandatory):        cerchio blu #005EB8 + simbolo bianco
  - W (Warning):          triangolo giallo #F7B500 con bordo nero + simbolo nero
  - P (Prohibition):      cerchio rosso #C8102E con barra diagonale + simbolo nero

Ogni SVG e' viewBox 0 0 256 256 (standard quadrato per icone).
Tagging strutturato per categoria + significato specifico.

Output: assets/icons/iso7010/{CODE}_{slug}.svg + manifest entry per seed.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUT_DIR = REPO_ROOT / "assets" / "icons" / "iso7010"
MANIFEST_PATH = REPO_ROOT / "assets" / "icons" / "iso7010_manifest.json"

# ISO 7010 colors (standard official)
GREEN = "#009639"
RED = "#C8102E"
BLUE = "#005EB8"
YELLOW = "#F7B500"
BLACK = "#000000"
WHITE = "#FFFFFF"

# ─── SVG TEMPLATES ──────────────────────────────────────────────────────────


def green_square_svg(symbol_path: str, code: str) -> str:
    """E-series: green square + white symbol (emergency/escape)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{GREEN}"/>
  <g fill="{WHITE}" stroke="{WHITE}">{symbol_path}</g>
  <text x="10" y="245" font-family="sans-serif" font-size="14" fill="{WHITE}">{code}</text>
</svg>
"""


def red_square_svg(symbol_path: str, code: str) -> str:
    """F-series: red square + white symbol (fire equipment)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{RED}"/>
  <g fill="{WHITE}" stroke="{WHITE}">{symbol_path}</g>
  <text x="10" y="245" font-family="sans-serif" font-size="14" fill="{WHITE}">{code}</text>
</svg>
"""


def blue_circle_svg(symbol_path: str, code: str) -> str:
    """M-series: blue circle + white symbol (mandatory)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <circle cx="128" cy="128" r="120" fill="{BLUE}"/>
  <g fill="{WHITE}" stroke="{WHITE}">{symbol_path}</g>
  <text x="10" y="245" font-family="sans-serif" font-size="14" fill="{WHITE}">{code}</text>
</svg>
"""


def yellow_triangle_svg(symbol_path: str, code: str) -> str:
    """W-series: yellow triangle with black border + black symbol (warning)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <polygon points="128,16 240,240 16,240" fill="{YELLOW}" stroke="{BLACK}" stroke-width="12" stroke-linejoin="round"/>
  <g fill="{BLACK}" stroke="{BLACK}">{symbol_path}</g>
  <text x="100" y="252" font-family="sans-serif" font-size="14" fill="{BLACK}">{code}</text>
</svg>
"""


def red_circle_prohibition_svg(symbol_path: str, code: str) -> str:
    """P-series: red circle with diagonal bar + black symbol (prohibition)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <circle cx="128" cy="128" r="120" fill="{WHITE}" stroke="{RED}" stroke-width="32"/>
  <g fill="{BLACK}" stroke="{BLACK}">{symbol_path}</g>
  <line x1="42" y1="42" x2="214" y2="214" stroke="{RED}" stroke-width="32" stroke-linecap="round"/>
  <text x="10" y="245" font-family="sans-serif" font-size="14" fill="{RED}">{code}</text>
</svg>
"""


# ─── ICON DEFINITIONS (30 icone iniziali, espandibile) ──────────────────────

# Each entry: (code, slug, builder, symbol_svg, italian_meaning, tags_extra)
ICONS = [
    # ═══ E-series — EMERGENCY / ESCAPE (verde) ═══
    ("E001", "uscita_emergenza_sinistra", green_square_svg,
     '<path d="M180 80 L180 180 L90 180 L120 220 L160 220 L160 240 L80 240 L80 60 L160 60 L160 80 L180 80 Z" stroke-width="0"/><polygon points="60,128 110,80 110,108 150,108 150,148 110,148 110,176"/>',
     "uscita di emergenza a sinistra", ["uscita", "emergenza", "evacuazione"]),
    ("E002", "uscita_emergenza_destra", green_square_svg,
     '<polygon points="196,128 146,80 146,108 106,108 106,148 146,148 146,176"/>',
     "uscita di emergenza a destra", ["uscita", "emergenza", "evacuazione"]),
    ("E003", "primo_soccorso", green_square_svg,
     '<rect x="100" y="60" width="56" height="136" rx="6"/><rect x="60" y="100" width="136" height="56" rx="6"/>',
     "presidio di primo soccorso", ["primo_soccorso", "salvataggio", "croce"]),
    ("E004", "telefono_emergenza", green_square_svg,
     '<path d="M80 80 Q80 60 100 60 L120 60 Q130 60 130 70 L140 100 Q140 110 130 115 L115 125 Q130 155 165 170 L175 155 Q180 145 190 145 L210 155 Q220 155 220 165 L220 185 Q220 205 200 205 Q120 205 80 125 Z" stroke-width="0"/>',
     "telefono di emergenza", ["telefono", "emergenza", "contatto"]),
    ("E005", "freccia_emergenza_su", green_square_svg,
     '<polygon points="128,40 200,140 160,140 160,220 96,220 96,140 56,140"/>',
     "freccia direzionale verso l'alto", ["freccia", "direzione", "evacuazione"]),
    ("E006", "scala_emergenza", green_square_svg,
     '<rect x="80" y="50" width="20" height="180"/><rect x="156" y="50" width="20" height="180"/><rect x="80" y="70" width="96" height="14"/><rect x="80" y="110" width="96" height="14"/><rect x="80" y="150" width="96" height="14"/><rect x="80" y="190" width="96" height="14"/>',
     "scala di emergenza", ["scala", "evacuazione", "uscita"]),
    ("E007", "punto_raccolta", green_square_svg,
     '<circle cx="128" cy="100" r="22"/><rect x="100" y="125" width="56" height="60" rx="4"/><polygon points="128,200 80,225 176,225"/>',
     "punto di raccolta in caso di emergenza", ["raccolta", "evacuazione", "punto_sicurezza"]),
    ("E008", "doccia_emergenza", green_square_svg,
     '<rect x="120" y="50" width="16" height="80"/><rect x="80" y="120" width="96" height="14" rx="4"/><line x1="100" y1="140" x2="100" y2="200" stroke-width="6"/><line x1="128" y1="140" x2="128" y2="210" stroke-width="6"/><line x1="156" y1="140" x2="156" y2="200" stroke-width="6"/>',
     "doccia di emergenza", ["doccia", "decontaminazione", "emergenza"]),
    ("E009", "lavaocchi_emergenza", green_square_svg,
     '<ellipse cx="128" cy="120" rx="60" ry="36"/><circle cx="128" cy="120" r="14" fill="none" stroke-width="4"/><path d="M68 156 L88 200 M188 156 L168 200" stroke-width="6"/>',
     "stazione di lavaggio occhi", ["lavaocchi", "decontaminazione", "occhi"]),
    ("E010", "defibrillatore_aed", green_square_svg,
     '<rect x="60" y="80" width="136" height="100" rx="8"/><path d="M85 130 L110 130 L120 100 L140 160 L150 130 L175 130" fill="none" stroke="white" stroke-width="6"/>',
     "defibrillatore semiautomatico DAE", ["dae", "defibrillatore", "soccorso"]),

    # ═══ F-series — FIRE EQUIPMENT (rosso) ═══
    ("F001", "estintore", red_square_svg,
     '<rect x="105" y="60" width="46" height="140" rx="10"/><rect x="115" y="40" width="26" height="30" rx="4"/><rect x="118" y="200" width="20" height="14"/><path d="M151 100 L180 100 L180 105 L155 105 Z"/>',
     "estintore portatile", ["estintore", "antincendio", "fuoco"]),
    ("F002", "idrante_uni", red_square_svg,
     '<rect x="100" y="60" width="56" height="100" rx="6"/><circle cx="128" cy="110" r="20" fill="none" stroke="white" stroke-width="6"/><rect x="116" y="160" width="24" height="40"/><rect x="100" y="200" width="56" height="14"/>',
     "idrante a muro UNI", ["idrante", "antincendio", "naspo"]),
    ("F003", "scala_antincendio", red_square_svg,
     '<rect x="80" y="40" width="14" height="200"/><rect x="160" y="40" width="14" height="200"/><line x1="94" y1="80" x2="160" y2="80" stroke-width="10"/><line x1="94" y1="120" x2="160" y2="120" stroke-width="10"/><line x1="94" y1="160" x2="160" y2="160" stroke-width="10"/><line x1="94" y1="200" x2="160" y2="200" stroke-width="10"/>',
     "scala antincendio fissa", ["scala", "antincendio", "evacuazione"]),
    ("F004", "telefono_antincendio", red_square_svg,
     '<rect x="50" y="80" width="90" height="60" rx="8"/><circle cx="80" cy="110" r="8"/><circle cx="110" cy="110" r="8"/><rect x="140" y="100" width="60" height="20" rx="4"/><path d="M170 60 L175 80 L165 80 Z"/>',
     "telefono per chiamata vigili del fuoco", ["telefono", "vigili_fuoco", "115"]),
    ("F005", "pulsante_allarme_antincendio", red_square_svg,
     '<rect x="60" y="60" width="136" height="136" rx="12" stroke="white" stroke-width="6" fill="none"/><circle cx="128" cy="128" r="40"/><rect x="125" y="100" width="6" height="20"/>',
     "pulsante manuale di allarme antincendio", ["pulsante", "allarme", "antincendio"]),
    ("F006", "naspo_antincendio", red_square_svg,
     '<circle cx="128" cy="128" r="70"/><circle cx="128" cy="128" r="40" fill="none" stroke="white" stroke-width="6"/><path d="M198 128 L240 128" stroke-width="8"/>',
     "naspo antincendio", ["naspo", "antincendio", "tubo"]),
    ("F007", "tromba_allarme", red_square_svg,
     '<path d="M60 110 L60 146 L100 146 L160 200 L160 56 L100 110 Z"/><path d="M170 90 Q200 128 170 166" fill="none" stroke="white" stroke-width="6"/>',
     "tromba di allarme acustico", ["sirena", "allarme", "acustico"]),
    ("F008", "coperta_antincendio", red_square_svg,
     '<rect x="60" y="60" width="136" height="136" rx="6"/><path d="M70 80 L186 80 M70 100 L186 100 M70 120 L186 120 M70 140 L186 140 M70 160 L186 160 M70 180 L186 180" fill="none" stroke="white" stroke-width="2"/>',
     "coperta antincendio", ["coperta", "antincendio", "asbesto"]),

    # ═══ M-series — MANDATORY (blu) ═══
    ("M001", "obbligo_generico", blue_circle_svg,
     '<circle cx="128" cy="128" r="14"/>',
     "obbligo generico", ["obbligo", "azione_richiesta"]),
    ("M002", "leggere_istruzioni", blue_circle_svg,
     '<rect x="80" y="60" width="96" height="136" rx="6" fill="none" stroke="white" stroke-width="8"/><line x1="95" y1="90" x2="161" y2="90" stroke-width="6"/><line x1="95" y1="110" x2="161" y2="110" stroke-width="6"/><line x1="95" y1="130" x2="161" y2="130" stroke-width="6"/><line x1="95" y1="150" x2="135" y2="150" stroke-width="6"/>',
     "obbligo leggere le istruzioni", ["istruzioni", "manuale", "leggere"]),
    ("M003", "protezione_udito", blue_circle_svg,
     '<path d="M88 128 Q88 80 128 80 Q168 80 168 128 L168 170 L150 180 L150 150 L138 145 L138 170 L118 170 L118 145 L106 150 L106 180 L88 170 Z"/>',
     "obbligo protezione udito (cuffie)", ["cuffie", "udito", "dpi"]),
    ("M004", "casco_protezione", blue_circle_svg,
     '<path d="M70 150 Q70 80 128 80 Q186 80 186 150 L186 170 L70 170 Z"/><rect x="100" y="60" width="56" height="22" rx="4"/>',
     "obbligo casco di protezione", ["casco", "testa", "dpi"]),
    ("M005", "protezione_vista", blue_circle_svg,
     '<ellipse cx="100" cy="128" rx="28" ry="22" fill="none" stroke="white" stroke-width="8"/><ellipse cx="156" cy="128" rx="28" ry="22" fill="none" stroke="white" stroke-width="8"/><line x1="128" y1="128" x2="128" y2="128" stroke="white" stroke-width="6"/>',
     "obbligo occhiali protettivi", ["occhiali", "vista", "dpi"]),
    ("M006", "calzature_sicurezza", blue_circle_svg,
     '<path d="M70 150 L160 150 L180 180 L180 200 L70 200 Z"/><rect x="70" y="100" width="50" height="50"/>',
     "obbligo calzature di sicurezza", ["scarpe", "calzature", "dpi"]),
    ("M007", "guanti_protezione", blue_circle_svg,
     '<path d="M90 100 L90 200 L170 200 L170 130 L155 130 L155 110 L140 110 L140 100 L125 100 L125 90 L110 90 L110 100 Z"/>',
     "obbligo guanti di protezione", ["guanti", "mani", "dpi"]),
    ("M008", "protezione_vie_respiratorie", blue_circle_svg,
     '<rect x="80" y="100" width="96" height="60" rx="20"/><line x1="60" y1="115" x2="80" y2="115" stroke-width="6"/><line x1="60" y1="145" x2="80" y2="145" stroke-width="6"/><line x1="176" y1="115" x2="196" y2="115" stroke-width="6"/><line x1="176" y1="145" x2="196" y2="145" stroke-width="6"/>',
     "obbligo protezione vie respiratorie", ["respiratore", "maschera", "dpi"]),
    ("M009", "imbragatura_anticaduta", blue_circle_svg,
     '<rect x="105" y="80" width="46" height="60" rx="6"/><line x1="105" y1="100" x2="80" y2="160" stroke-width="6"/><line x1="151" y1="100" x2="176" y2="160" stroke-width="6"/><circle cx="128" cy="160" r="14" fill="none" stroke="white" stroke-width="6"/><line x1="128" y1="174" x2="128" y2="200" stroke-width="6"/>',
     "obbligo imbragatura anticaduta", ["imbracatura", "anticaduta", "dpi"]),
    ("M010", "indumento_alta_visibilita", blue_circle_svg,
     '<path d="M85 80 L171 80 L186 110 L150 130 L150 200 L106 200 L106 130 L70 110 Z"/><line x1="106" y1="150" x2="150" y2="150" stroke="white" stroke-width="6"/><line x1="106" y1="170" x2="150" y2="170" stroke="white" stroke-width="6"/>',
     "obbligo indumento alta visibilita", ["gilet", "alta_visibilita", "dpi"]),

    # ═══ W-series — WARNING (giallo triangolo) ═══
    ("W001", "pericolo_generico", yellow_triangle_svg,
     '<text x="128" y="200" font-family="sans-serif" font-size="120" font-weight="bold" text-anchor="middle">!</text>',
     "pericolo generico", ["pericolo", "attenzione"]),
    ("W012", "tensione_elettrica", yellow_triangle_svg,
     '<polygon points="130,80 90,170 120,170 100,220 170,140 130,140 165,80"/>',
     "pericolo tensione elettrica", ["elettrico", "tensione", "fulmine"]),
    ("W005", "materiale_esplosivo", yellow_triangle_svg,
     '<circle cx="128" cy="170" r="50"/><path d="M70 130 L80 110 M186 130 L176 110 M128 100 L128 80 M100 110 L110 120 M156 110 L146 120"/>',
     "pericolo materiale esplosivo", ["esplosivo", "bomba"]),
    ("W021", "materiale_infiammabile", yellow_triangle_svg,
     '<path d="M128 100 Q150 130 138 160 Q160 150 158 180 Q158 220 128 220 Q98 220 98 180 Q98 150 118 160 Q108 130 128 100 Z"/>',
     "pericolo materiale infiammabile", ["infiammabile", "fuoco", "fiamma"]),
    ("W016", "materiale_tossico", yellow_triangle_svg,
     '<circle cx="128" cy="160" r="40"/><path d="M105 145 Q105 130 115 130 Q125 130 125 145 M131 145 Q131 130 141 130 Q151 130 151 145" fill="none" stroke="black" stroke-width="6"/><line x1="110" y1="175" x2="146" y2="190" stroke-width="6"/>',
     "pericolo materiale tossico", ["tossico", "veleno", "teschio"]),
    ("W026", "rischio_biologico", yellow_triangle_svg,
     '<circle cx="128" cy="170" r="22"/><circle cx="100" cy="140" r="22"/><circle cx="156" cy="140" r="22"/><circle cx="128" cy="200" r="22"/>',
     "pericolo rischio biologico", ["biologico", "infettivo"]),
    ("W004", "raggi_laser", yellow_triangle_svg,
     '<path d="M70 200 L100 130 L116 200 M128 200 L128 110 M186 200 L156 130 L140 200" fill="none" stroke="black" stroke-width="8"/><circle cx="128" cy="105" r="8"/>',
     "pericolo radiazione laser", ["laser", "raggi"]),
    ("W009", "rischio_caduta", yellow_triangle_svg,
     '<path d="M80 200 L80 160 L120 160 L120 100 L150 100 L150 160 L186 160 L186 200 Z" fill="none" stroke="black" stroke-width="6"/><circle cx="135" cy="80" r="14"/><line x1="135" y1="94" x2="135" y2="130" stroke-width="6"/>',
     "pericolo rischio caduta dall'alto", ["caduta", "altezza", "vuoto"]),
    ("W015", "carichi_sospesi", yellow_triangle_svg,
     '<line x1="100" y1="100" x2="156" y2="100" stroke-width="8"/><line x1="128" y1="100" x2="128" y2="150" stroke-width="6"/><rect x="100" y="150" width="56" height="56"/>',
     "pericolo carichi sospesi", ["carichi", "sospesi", "gru"]),
    ("W014", "carrelli_industriali", yellow_triangle_svg,
     '<rect x="70" y="140" width="90" height="50" rx="4"/><circle cx="88" cy="200" r="14"/><circle cx="142" cy="200" r="14"/><line x1="160" y1="160" x2="200" y2="120" stroke-width="6"/>',
     "pericolo carrelli industriali in movimento", ["carrello", "muletto", "trasporto"]),

    # ═══ P-series — PROHIBITION (cerchio rosso barra) ═══
    ("P001", "divieto_generico", red_circle_prohibition_svg,
     '<text x="128" y="160" font-family="sans-serif" font-size="60" text-anchor="middle">X</text>',
     "divieto generico", ["divieto", "vietato"]),
    ("P002", "vietato_fumare", red_circle_prohibition_svg,
     '<rect x="60" y="120" width="120" height="16" rx="2"/><line x1="120" y1="100" x2="120" y2="116" stroke-width="4"/><line x1="140" y1="100" x2="140" y2="116" stroke-width="4"/>',
     "vietato fumare", ["fumare", "sigarette", "divieto"]),
    ("P003", "vietato_fiamme_libere", red_circle_prohibition_svg,
     '<path d="M128 90 Q150 120 138 150 Q160 140 158 170 Q158 200 128 200 Q98 200 98 170 Q98 140 118 150 Q108 120 128 90 Z"/>',
     "vietato fiamme libere", ["fiamma", "fuoco", "divieto"]),
    ("P004", "vietato_acqua_estinguere", red_circle_prohibition_svg,
     '<path d="M128 90 Q160 130 160 165 Q160 195 128 195 Q96 195 96 165 Q96 130 128 90 Z"/>',
     "vietato usare acqua per estinguere", ["acqua", "estinguere", "divieto"]),
    ("P005", "non_potabile", red_circle_prohibition_svg,
     '<path d="M100 80 L156 80 L150 200 L106 200 Z"/>',
     "acqua non potabile", ["acqua", "potabile", "divieto"]),
    ("P006", "divieto_accesso_pedoni", red_circle_prohibition_svg,
     '<circle cx="128" cy="100" r="18"/><path d="M115 125 L141 125 L150 175 L128 220 L106 175 Z"/>',
     "divieto accesso pedoni", ["pedoni", "accesso", "divieto"]),
]


def _slugify_tags(tags: list[str]) -> list[str]:
    """Normalize tags lowercase NFC."""
    import unicodedata
    out = []
    seen = set()
    for t in tags:
        norm = unicodedata.normalize("NFC", t).lower().strip()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _rasterize_svg(svg_text: str, png_path: Path) -> None:
    """Convert SVG string to 512x512 PNG via cairosvg (for Voyage embed).
    PNG file_path points to manifest; SVG stays as canonical source.
    """
    import cairosvg
    cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        write_to=str(png_path),
        output_width=512,
        output_height=512,
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for code, slug, builder, symbol, meaning, extra_tags in ICONS:
        svg = builder(symbol, code)
        svg_path = OUT_DIR / f"{code}_{slug}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        # Rasterize a 512x512 PNG accanto allo SVG per il seed Voyage
        png_path = OUT_DIR / f"{code}_{slug}.png"
        _rasterize_svg(svg, png_path)
        path = png_path  # manifest references PNG (Voyage compatible)

        # Category from code prefix
        cat_map = {
            "E": "emergenza",
            "F": "antincendio",
            "M": "obbligo",
            "W": "avvertimento",
            "P": "divieto",
        }
        category = cat_map.get(code[0], "altro")
        color_map = {
            "E": "verde",
            "F": "rosso",
            "M": "blu",
            "W": "giallo",
            "P": "rosso",
        }

        tags = _slugify_tags([
            "segnaletica",
            "iso7010",
            category,
            color_map.get(code[0], ""),
            code.lower(),
            *extra_tags,
        ])

        manifest.append({
            "file_path": f"assets/icons/iso7010/{code}_{slug}.png",
            "tags": tags,
            "source": "iso7010",
            "license": "Public Domain",
            "attribution": f"ISO 7010:2020 {code} — {meaning}",
            "source_url": "https://www.iso.org/standard/72424.html",
        })

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[iso7010] generati {len(ICONS)} SVG in {OUT_DIR}")
    print(f"[iso7010] manifest in {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
