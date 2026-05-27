"""Convert a Claude Design PowerPoint export (1 layout + N slides-as-examples)
into a proper slide master PPTX with N slide_layouts (one per BP §07.3 type).

The Claude Design export contains:
  - ppt/slideLayouts/slideLayout1.xml  (empty "DEFAULT")
  - ppt/slides/slide{1..8}.xml         (rich pre-designed examples)
  - ppt/notesSlides/notesSlide{1..8}.xml

We need:
  - ppt/slideLayouts/slideLayout{1..8}.xml  (the rich designs, as layouts)
  - no ppt/slides/  (master template has no slides)
  - no ppt/notesSlides/ (those belong to slides, not layouts)

Mapping BP §07.3 layout order (CRITICAL — SlideBuilder relies on it):
  0: TITLE
  1: CONTENT_TEXT
  2: CONTENT_IMAGE
  3: DIAGRAM
  4: QUIZ
  5: CASE_STUDY
  6: RECAP
  7: CLOSING

The conversion is XML-level (zipfile + ElementTree) to preserve every visual
detail (colors, fonts, positions, embedded images). python-pptx is NOT used
because it doesn't support custom slide_layout creation cleanly.

Usage (inside backend container):
  python scripts/convert_design_export_to_master.py \
      --input  /app/assets/templates/nexus_master.pptx \
      --output /app/assets/templates/nexus_master_converted.pptx
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# BP §07.3 layout names in order (idx 0-7)
LAYOUT_NAMES = [
    "TITLE",
    "CONTENT_TEXT",
    "CONTENT_IMAGE",
    "DIAGRAM",
    "QUIZ",
    "CASE_STUDY",
    "RECAP",
    "CLOSING",
]


def extract(input_path: Path, work_dir: Path) -> None:
    with zipfile.ZipFile(input_path, "r") as zf:
        zf.extractall(work_dir)


def convert_slide_xml_to_layout(slide_xml: str, layout_name: str) -> str:
    """Transform a <p:sld> root into a <p:sldLayout type="custom"> root.
    Preserves all shapes, text, fills, embedded images (via rId references).
    """
    # Replace XML root element <p:sld ...> ... </p:sld>
    out = slide_xml
    # 1. Root open tag <p:sld xmlns=...> -> <p:sldLayout xmlns=... type="custom" preserve="1">
    out = re.sub(
        r'<p:sld(\s+xmlns[^>]*?)>',
        lambda m: f'<p:sldLayout{m.group(1)} type="custom" preserve="1">',
        out,
        count=1,
    )
    # 2. Closing </p:sld> -> </p:sldLayout>
    out = out.replace("</p:sld>", "</p:sldLayout>")
    # 3. Rename <p:cSld name="..."> -> <p:cSld name="LAYOUT_NAME">
    out = re.sub(
        r'<p:cSld\s+name="[^"]*">',
        f'<p:cSld name="{layout_name}">',
        out,
        count=1,
    )
    return out


def fix_layout_rels(layout_rels_xml: str) -> str:
    """A slide's _rels points to its slideLayout. A layout's _rels must
    point to the slideMaster instead. Also: drop notesSlide refs (layouts
    don't have notes).

    CRITICAL: rId must be UNIQUE within the rels file. We must NOT hardcode
    rId1 because slides typically have rId1=image (the logo). We replace
    the slideLayout rel IN PLACE preserving its original Id (e.g. rId2 →
    same rId2 but Type changed to slideMaster, Target changed to master).
    """
    # Capture the rId of the slideLayout relationship so we can re-use it
    slide_layout_match = re.search(
        r'<Relationship\s+Id="(rId\d+)"\s+Type="[^"]*slideLayout"\s+Target="[^"]*"/>',
        layout_rels_xml,
    )
    if slide_layout_match:
        original_rid = slide_layout_match.group(1)
        # Replace the slideLayout rel with slideMaster rel, REUSING the same rId
        out = re.sub(
            r'<Relationship\s+Id="' + re.escape(original_rid) + r'"\s+Type="[^"]*slideLayout"\s+Target="[^"]*"/>',
            f'<Relationship Id="{original_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>',
            layout_rels_xml,
            count=1,
        )
    else:
        # No slideLayout rel found (unlikely); append a slideMaster rel with
        # a fresh unique rId based on max existing
        existing_ids = [int(m) for m in re.findall(r'Id="rId(\d+)"', layout_rels_xml)]
        new_rid = (max(existing_ids) if existing_ids else 0) + 1
        out = layout_rels_xml.replace(
            "</Relationships>",
            f'<Relationship Id="rId{new_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>',
        )
    # Drop any notesSlide relationship (notes belong to slides only)
    out = re.sub(
        r'<Relationship\s+Id="[^"]*"\s+Type="[^"]*notesSlide"\s+Target="[^"]*"/>',
        "",
        out,
    )
    return out


def rebuild_presentation_xml(pres_xml: str, num_layouts: int) -> str:
    """Update presentation.xml to:
       - remove <p:sldIdLst> entries (no slides in template)
       - keep sldMasterIdLst as-is (slideMaster1)
       The slideMaster's rels file is what lists the layouts, not this file.
    """
    # Empty the sldIdLst (the listing of actual slides). Master + layouts
    # are independently registered via _rels.
    out = re.sub(
        r'<p:sldIdLst>.*?</p:sldIdLst>',
        '<p:sldIdLst/>',
        pres_xml,
        flags=re.DOTALL,
    )
    return out


def rebuild_presentation_rels(rels_xml: str) -> str:
    """Remove all <Relationship Type=".../slide"> entries from presentation.xml.rels
    (master template has no slides, only the master itself + theme + props).
    The slideMaster's rels lists the slideLayouts.
    """
    out = re.sub(
        r'<Relationship\s+Id="[^"]*"\s+Type="[^"]*relationships/slide"\s+Target="[^"]*"/>',
        "",
        out := rels_xml,
    )
    return out


def rebuild_slide_master_rels(
    master_rels_xml: str, num_layouts: int
) -> tuple[str, int]:
    """slideMaster1.xml.rels must list ALL slideLayouts.

    Returns (new_xml, first_rid_assigned_to_layouts) so the caller can keep
    the slideMaster1.xml sldLayoutIdLst in sync.
    """
    # Strip existing slideLayout entries (we re-add cleanly); keep theme + others
    out = re.sub(
        r'<Relationship\s+Id="[^"]*"\s+Type="[^"]*slideLayout"\s+Target="[^"]*"/>',
        "",
        master_rels_xml,
    )
    # Find max existing rId AFTER strip
    existing_ids = [int(m) for m in re.findall(r'Id="rId(\d+)"', out)]
    next_id = (max(existing_ids) if existing_ids else 0) + 1
    first_layout_rid = next_id
    new_rels = ""
    for i in range(1, num_layouts + 1):
        new_rels += (
            f'<Relationship Id="rId{next_id}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
            f'Target="../slideLayouts/slideLayout{i}.xml"/>'
        )
        next_id += 1
    out = out.replace("</Relationships>", new_rels + "</Relationships>")
    return out, first_layout_rid


def rebuild_slide_master_xml(
    master_xml: str, num_layouts: int, layout_start_rid: int
) -> str:
    """slideMaster1.xml has a <p:sldLayoutIdLst> listing layout rIds.
    Replace it with new rIds matching the rels file. `layout_start_rid` must
    be the first rId assigned to layouts in slideMaster1.xml.rels (caller-
    determined so the two stay in sync).
    """
    new_lst = "<p:sldLayoutIdLst>"
    base_id = 2147483649  # PowerPoint convention for layout ids
    for i in range(num_layouts):
        rid = layout_start_rid + i
        new_lst += f'<p:sldLayoutId id="{base_id + i}" r:id="rId{rid}"/>'
    new_lst += "</p:sldLayoutIdLst>"

    out = re.sub(
        r'<p:sldLayoutIdLst>.*?</p:sldLayoutIdLst>',
        new_lst,
        master_xml,
        flags=re.DOTALL,
    )
    # If there was no sldLayoutIdLst, insert it before </p:sldMaster>
    if new_lst not in out:
        out = out.replace("</p:sldMaster>", new_lst + "</p:sldMaster>")
    return out


def rebuild_content_types(ct_xml: str, num_layouts: int) -> str:
    """[Content_Types].xml must:
       - register slideLayout{1..N}.xml as PartName overrides
       - drop slide{1..M}.xml + notesSlide{1..M}.xml overrides
    """
    out = ct_xml
    # Drop slide and notesSlide overrides
    out = re.sub(
        r'<Override\s+PartName="/ppt/slides/slide\d+\.xml"\s+ContentType="[^"]*"/>',
        "",
        out,
    )
    out = re.sub(
        r'<Override\s+PartName="/ppt/notesSlides/notesSlide\d+\.xml"\s+ContentType="[^"]*"/>',
        "",
        out,
    )
    # Drop existing slideLayout overrides (we'll re-add cleanly)
    out = re.sub(
        r'<Override\s+PartName="/ppt/slideLayouts/slideLayout\d+\.xml"\s+ContentType="[^"]*"/>',
        "",
        out,
    )
    # Inject N new slideLayout overrides before </Types>
    new_overrides = ""
    for i in range(1, num_layouts + 1):
        new_overrides += (
            f'<Override PartName="/ppt/slideLayouts/slideLayout{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        )
    out = out.replace("</Types>", new_overrides + "</Types>")
    return out


def repack(work_dir: Path, output_path: Path) -> None:
    if output_path.exists():
        output_path.unlink()
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(work_dir.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = str(file_path.relative_to(work_dir)).replace("\\", "/")
            zf.write(file_path, arcname)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        extract(args.input, work)

        # Find slide files (slide1.xml, slide2.xml, ...)
        slides_dir = work / "ppt" / "slides"
        slide_files = sorted(
            slides_dir.glob("slide*.xml"),
            key=lambda p: int(re.search(r"\d+", p.stem).group()),
        )
        n_slides = len(slide_files)
        if n_slides != len(LAYOUT_NAMES):
            print(
                f"ERROR: template has {n_slides} slides but BP §07.3 expects "
                f"{len(LAYOUT_NAMES)} layouts (TITLE...CLOSING)",
                file=sys.stderr,
            )
            return 3

        layouts_dir = work / "ppt" / "slideLayouts"
        layouts_rels_dir = layouts_dir / "_rels"

        # Remove the existing empty slideLayout1.xml + its rels (we'll recreate)
        for f in layouts_dir.glob("slideLayout*.xml"):
            f.unlink()
        for f in layouts_rels_dir.glob("slideLayout*.xml.rels"):
            f.unlink()

        # Convert each slide -> layout (preserving original rels for image refs)
        for i, slide_path in enumerate(slide_files):
            layout_idx = i + 1  # 1-based for slideLayout{N}.xml
            layout_name = LAYOUT_NAMES[i]
            slide_xml = slide_path.read_text(encoding="utf-8")
            layout_xml = convert_slide_xml_to_layout(slide_xml, layout_name)
            (layouts_dir / f"slideLayout{layout_idx}.xml").write_text(
                layout_xml, encoding="utf-8"
            )
            # Convert its _rels (image refs preserved, slideLayout->slideMaster)
            slide_rels = (slides_dir / "_rels" / f"{slide_path.stem}.xml.rels")
            if slide_rels.exists():
                rels_xml = slide_rels.read_text(encoding="utf-8")
                layout_rels_xml = fix_layout_rels(rels_xml)
                (layouts_rels_dir / f"slideLayout{layout_idx}.xml.rels").write_text(
                    layout_rels_xml, encoding="utf-8"
                )

        # Remove the now-stale slide/notesSlide directories entirely
        shutil.rmtree(slides_dir, ignore_errors=True)
        shutil.rmtree(work / "ppt" / "notesSlides", ignore_errors=True)

        # Rebuild presentation.xml (clear sldIdLst)
        pres_xml_path = work / "ppt" / "presentation.xml"
        pres_xml = pres_xml_path.read_text(encoding="utf-8")
        pres_xml_path.write_text(
            rebuild_presentation_xml(pres_xml, n_slides), encoding="utf-8"
        )

        # Rebuild presentation.xml.rels (drop slide refs)
        pres_rels_path = work / "ppt" / "_rels" / "presentation.xml.rels"
        pres_rels = pres_rels_path.read_text(encoding="utf-8")
        pres_rels_path.write_text(
            rebuild_presentation_rels(pres_rels), encoding="utf-8"
        )

        # Rebuild slideMaster rels (list all slideLayouts) + capture the rId
        # range so the master XML can list them consistently
        master_rels_path = (
            work / "ppt" / "slideMasters" / "_rels" / "slideMaster1.xml.rels"
        )
        master_rels = master_rels_path.read_text(encoding="utf-8")
        new_master_rels, layout_start_rid = rebuild_slide_master_rels(
            master_rels, n_slides
        )
        master_rels_path.write_text(new_master_rels, encoding="utf-8")

        # Rebuild slideMaster1.xml sldLayoutIdLst (using same rId range)
        master_xml_path = work / "ppt" / "slideMasters" / "slideMaster1.xml"
        master_xml = master_xml_path.read_text(encoding="utf-8")
        master_xml_path.write_text(
            rebuild_slide_master_xml(master_xml, n_slides, layout_start_rid),
            encoding="utf-8",
        )

        # Rebuild [Content_Types].xml
        ct_path = work / "[Content_Types].xml"
        ct_xml = ct_path.read_text(encoding="utf-8")
        ct_path.write_text(rebuild_content_types(ct_xml, n_slides), encoding="utf-8")

        # Repack
        repack(work, args.output)

    print(f"✅ Converted: {args.output}")
    print(f"   {n_slides} slide-examples → {n_slides} slide_layouts")
    print(f"   Layout names: {', '.join(LAYOUT_NAMES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
