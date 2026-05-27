"""Enlarge logo PICTURE in nexus_master.pptx content layouts.

Logo attuale: 0.8x0.2 inch in basso-destra (quasi invisibile).
Nuovo: 1.5x0.5 inch in basso-destra (chiaramente leggibile).
"""
from __future__ import annotations
import shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches

TEMPLATE = Path("assets/templates/nexus_master.pptx")
BACKUP = Path("assets/templates/nexus_master.pptx.pre_logo_enlarge.bak")

# Slide size 20 x 11.25 inch
# New logo: 1.8x0.5 inch in bottom-right with 0.2 inch margin
NEW_W = Inches(1.8)
NEW_H = Inches(0.5)
SLIDE_W = Inches(20)
SLIDE_H = Inches(11.25)
MARGIN = Inches(0.2)

if not BACKUP.is_file():
    shutil.copy2(TEMPLATE, BACKUP)
    print(f"Backup creato: {BACKUP}")

prs = Presentation(str(TEMPLATE))

for i, layout in enumerate(prs.slide_layouts):
    if layout.name in ("TITLE", "CLOSING"):
        continue  # questi hanno già il logo più grande
    for shape in layout.shapes:
        if "PICTURE" in str(shape.shape_type) and shape.name == "Image 0":
            old_w = shape.width / 914400
            old_h = shape.height / 914400
            shape.width = NEW_W
            shape.height = NEW_H
            shape.left = SLIDE_W - NEW_W - MARGIN
            shape.top = SLIDE_H - NEW_H - MARGIN
            print(f"Layout {i} '{layout.name}': logo {old_w:.1f}x{old_h:.1f} -> {NEW_W/914400:.1f}x{NEW_H/914400:.1f}")

prs.save(str(TEMPLATE))
print(f"\nTemplate aggiornato.")
