"""Remove every C.F.P. Montessori reference from the active PPTX master.

Rebrand 2026-07-11 (plan vast-hopping-sketch). Surgical zip-level edit of
``assets/templates/nexus_master_v4_patched.pptx`` — the layout/shape structure
that ``slide_builder_v2.py`` maps by index is NOT touched. Operations:

1. Remove every ``<p:pic>`` that references ``cfp_logo.jpeg`` from all
   slideLayout/slideMaster parts (the logo lives only in that layer; the
   builder never clones layout pics — see slide_builder_v2.py:694-701).
2. Drop the now-orphan relationship entries and the media file itself.
3. Replace the cover footer text "C.F.P. Montessori — Formazione Globale"
   with "EduVault".
4. Rewrite docProps (title/author/company) and the theme name.
5. Validate: python-pptx must open and re-save the result.

A backup ``.pre_eduvault.bak`` is written next to the template first.

Run from the repo root:
    python scripts/rebrand_master_to_eduvault.py
"""

from __future__ import annotations

import re
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

from lxml import etree

TEMPLATE = Path("assets/templates/nexus_master_v4_patched.pptx")
BACKUP = TEMPLATE.with_suffix(".pptx.pre_eduvault.bak")
LOGO_MEDIA = "ppt/media/cfp_logo.jpeg"

NSMAP = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

TEXT_FIXES = [
    ("C.F.P. Montessori — Formazione Globale", "EduVault"),
    ("C.F.P. Montessori — Formazione Globale", "EduVault"),
    ("CFP Montessori — Nexus Master v4", "EduVault — Nexus Master v4"),
    ("CFP Montessori", "EduVault"),
    ('name="CFP"', 'name="EduVault"'),
]


def _logo_rids(rels_xml: bytes) -> set[str]:
    """rIds in a .rels part whose Target points at the logo media."""
    root = etree.fromstring(rels_xml)
    rids = set()
    for rel in root.findall("rel:Relationship", NSMAP):
        if rel.get("Target", "").endswith("cfp_logo.jpeg"):
            rids.add(rel.get("Id"))
    return rids


def _strip_logo_rels(rels_xml: bytes) -> bytes:
    root = etree.fromstring(rels_xml)
    for rel in list(root.findall("rel:Relationship", NSMAP)):
        if rel.get("Target", "").endswith("cfp_logo.jpeg"):
            root.remove(rel)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _strip_logo_pics(part_xml: bytes, rids: set[str]) -> tuple[bytes, int]:
    root = etree.fromstring(part_xml)
    removed = 0
    for pic in root.iter("{%s}pic" % NSMAP["p"]):
        blip = pic.find(".//a:blip", NSMAP)
        embed = blip.get("{%s}embed" % NSMAP["r"]) if blip is not None else None
        if embed in rids:
            pic.getparent().remove(pic)
            removed += 1
    out = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return out, removed


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"FAIL: template not found: {TEMPLATE}")
    if not BACKUP.exists():
        shutil.copy2(TEMPLATE, BACKUP)
        print(f"[backup] {BACKUP}")
    else:
        print(f"[backup] already present: {BACKUP}")

    src = zipfile.ZipFile(TEMPLATE)
    names = src.namelist()

    # Pass 1: map each layout/master part to the rIds of its logo relationship.
    part_rids: dict[str, set[str]] = {}
    for name in names:
        if re.match(r"ppt/(slideLayouts|slideMasters)/_rels/.+\.rels$", name):
            rids = _logo_rids(src.read(name))
            if rids:
                part = name.replace("_rels/", "").removesuffix(".rels")
                part_rids[part] = rids

    print(f"[scan] parts referencing the logo: {sorted(part_rids)}")

    buf = BytesIO()
    pics_removed = 0
    text_fixed = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for name in names:
            if name == LOGO_MEDIA:
                print(f"[drop] {name}")
                continue
            data = src.read(name)
            if re.match(r"ppt/(slideLayouts|slideMasters)/_rels/.+\.rels$", name):
                part = name.replace("_rels/", "").removesuffix(".rels")
                if part in part_rids:
                    data = _strip_logo_rels(data)
            elif name in part_rids:
                data, n = _strip_logo_pics(data, part_rids[name])
                pics_removed += n
            if name.endswith(".xml"):
                text = data.decode("utf-8")
                for old, new in TEXT_FIXES:
                    if old in text:
                        text = text.replace(old, new)
                        text_fixed += 1
                data = text.encode("utf-8")
            dst.writestr(name, data)
    src.close()
    TEMPLATE.write_bytes(buf.getvalue())
    print(f"[done] pics removed: {pics_removed}, text fixes applied: {text_fixed}")

    # Validation 1: python-pptx round-trip.
    from pptx import Presentation

    prs = Presentation(str(TEMPLATE))
    n_layouts = sum(len(m.slide_layouts) for m in prs.slide_masters)
    tmp = TEMPLATE.with_suffix(".roundtrip.tmp")
    prs.save(str(tmp))
    tmp.unlink()
    print(f"[validate] python-pptx open/save OK — {n_layouts} layouts")

    # Validation 2: zero CFP strings / logo media left.
    z = zipfile.ZipFile(TEMPLATE)
    leftovers = []
    for name in z.namelist():
        if "cfp" in name.lower():
            leftovers.append(name)
        if name.endswith(".xml"):
            t = z.read(name).decode("utf-8", "ignore")
            if re.search(r"Montessori|C\.F\.P|CFP", t):
                leftovers.append(f"{name} (text)")
    if leftovers:
        raise SystemExit(f"FAIL: CFP leftovers: {leftovers}")
    print("[validate] zero CFP references in the template OK")


if __name__ == "__main__":
    main()
