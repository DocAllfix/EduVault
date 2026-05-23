"""Generate a synthetic 4-page PDF mimicking DM 388/2003 structure.

Used by tests/integration/test_ingestion.py when the real PDF is not
available in storage/pdfs/dm388_03.pdf.

This fixture preserves the structural features the parser must handle:
- multi-page extraction with ``layout=True``
- Italian normative article numbering (Art. 1, Art. 2, Art. 2-bis)
- numbered paragraphs (commi) inside articles
- one Allegato section
- enough text to exceed a reasonable lower-bound on extracted chars

Run manually: ``python tests/fixtures/pdfs/generate_dm388_synthetic.py``
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


def build_synthetic_pdf(out_path: Path) -> None:
    """Write a 4-page synthetic DM 388/2003 lookalike to ``out_path``."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="DM 388/2003 synthetic fixture",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
    )
    heading = ParagraphStyle(
        "heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        spaceAfter=8,
    )

    story = [
        Paragraph(
            "Decreto Ministeriale 15 luglio 2003, n. 388 (sintetico per test)",
            heading,
        ),
        Paragraph(
            "Regolamento recante disposizioni sul pronto soccorso aziendale, "
            "in attuazione dell'articolo 15, comma 3, del decreto legislativo 626/94.",
            body,
        ),
        Spacer(1, 0.5 * cm),
        Paragraph("Art. 1 - Classificazione delle aziende", heading),
        Paragraph(
            "1. Le aziende ovvero le unita' produttive sono classificate, tenuto conto "
            "della tipologia di attivita' svolta, del numero dei lavoratori occupati e "
            "dei fattori di rischio, in tre gruppi.",
            body,
        ),
        Paragraph(
            "2. Il datore di lavoro, sentito il medico competente, ove previsto, "
            "identifica la categoria di appartenenza della propria azienda o unita' "
            "produttiva e la comunica al rappresentante dei lavoratori per la sicurezza.",
            body,
        ),
        PageBreak(),
        Paragraph("Art. 2 - Organizzazione di pronto soccorso", heading),
        Paragraph(
            "1. Nelle aziende o unita' produttive di gruppo A e di gruppo B il datore "
            "di lavoro deve garantire le seguenti attrezzature minime di equipaggiamento "
            "ed assicurare il raccordo con il Sistema di emergenza del Servizio sanitario "
            "nazionale.",
            body,
        ),
        Paragraph(
            "2. Il datore di lavoro, in collaborazione con il medico competente, ove "
            "previsto, sulla base dei rischi specifici presenti nell'azienda o unita' "
            "produttiva, individua e rende disponibili le attrezzature minime di "
            "equipaggiamento e i dispositivi di protezione individuale per gli addetti "
            "al primo intervento interno ed al pronto soccorso.",
            body,
        ),
        Paragraph(
            "3. Le attrezzature ed i dispositivi di cui al comma 2 devono essere "
            "appropriati rispetto ai rischi specifici connessi alla attivita' lavorativa "
            "dell'azienda e devono essere mantenuti in condizioni di efficienza e di "
            "pronto impiego e custoditi in luogo idoneo e facilmente accessibile.",
            body,
        ),
        PageBreak(),
        Paragraph("Art. 2-bis - Disposizioni particolari", heading),
        Paragraph(
            "1. Nelle aziende o unita' produttive di gruppo A, il datore di lavoro deve, "
            "altresi', garantire il raccordo tra il sistema di pronto soccorso interno "
            "ed il Sistema di emergenza sanitaria di cui al D.P.R. 27 marzo 1992.",
            body,
        ),
        Paragraph(
            "2. La formazione dei lavoratori designati va ripetuta con cadenza triennale "
            "almeno per quanto attiene alla capacita' di intervento pratico.",
            body,
        ),
        PageBreak(),
        Paragraph("Allegato I - Contenuto minimo della cassetta di pronto soccorso", heading),
        Paragraph(
            "Guanti sterili monouso (5 paia). Visiera paraschizzi. Flacone di soluzione "
            "cutanea di iodopovidone al 10% di iodio da 1 litro (1). Flacone di soluzione "
            "fisiologica (sodio cloruro 0,9%) da 500 ml (3).",
            body,
        ),
        Paragraph(
            "Compresse di garza sterile 10 x 10 in buste singole (10). Compresse di garza "
            "sterile 18 x 40 in buste singole (2). Teli sterili monouso (2). Pinzette da "
            "medicazione sterili monouso (2). Confezione di rete elastica di misura media (1).",
            body,
        ),
    ]

    doc.build(story)


if __name__ == "__main__":
    target = Path(__file__).with_name("dm388_synthetic.pdf")
    build_synthetic_pdf(target)
    print(f"wrote {target} ({target.stat().st_size} bytes)")
