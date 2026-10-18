"""Render an editable, evidence-bound JSON source to a free-format DOCX.

This is a layout engine, not a manuscript writer or scientific validator. Imports
of python-docx are delayed until evidence/source checks pass. --self-test uses
stdlib-only parser checks and creates no document or manuscript source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
import unittest

ROOT = Path(__file__).resolve().parents[1]
NUMERIC_FILES = tuple("tables/v2/" + name for name in (
    "conditions_by_source.csv", "conditions.csv", "regions.csv", "classes.csv",
    "contrasts.json", "primary.json"))
BIB_PATH = "docs/references_v2.bib"
CITE = re.compile(r"\{cite:([^{}]*)\}")
SHA = re.compile(r"[0-9a-f]{64}")
ACTIVE_AMENDMENT = "configs/v2_active_gpu_amendment.json"
ACTIVE_AUDIT = "evidence/v2/active_run_completeness.json"
ACTIVE_CODE = "code/v2_active_gpu_results.py"
ACTIVE_ROLE = "descriptive_main_display_after_post_exposure_user_backend_amendment"
ACTIVE_CUDA = "evidence/v2/cuda_execution"
ACTIVE_FROZEN = "evidence/v2/runs/dinov2_mlp128"
CPU_REFERENCE = "evidence/v2/runs/resnet18_unet"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audited_result_inventory_sha256(results):
    """Stable scientific inventory identity; report timestamps are not inputs."""
    require(isinstance(results, dict), "Audited result inventory must be a SHA map")
    return hashlib.sha256(json.dumps(results, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def project_path(root, relative, *, existing=True):
    require(isinstance(relative, str) and relative and ":" not in relative and "\\" not in relative,
            "Expected a relative POSIX project path")
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, "Unsafe project path")
    path = (root / part).resolve()
    require(path.is_relative_to(root.resolve()), "Path escapes project")
    if existing:
        require(path.is_file(), "Missing project file: " + relative)
    return path


def paper_path(value, suffix, root=ROOT, *, existing=True):
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    require(path.is_relative_to(root.resolve()) and (root / "paper/v2").resolve().is_relative_to(root.resolve()),
            "paper/v2 cannot escape the project through a symlink")
    require(path.is_relative_to((root / "paper/v2").resolve()), "Source and output must be inside paper/v2")
    require(path.suffix.lower() == suffix, "Expected " + suffix + " path")
    if existing:
        require(path.is_file(), "Missing source file")
    return path


def _skip(text, position):
    while position < len(text):
        if text[position].isspace():
            position += 1
        elif text[position] == "%":
            end = text.find("\n", position)
            position = len(text) if end < 0 else end + 1
        else:
            break
    return position


def _braced(text, position):
    require(position < len(text) and text[position] == "{", "Expected opening brace")
    depth, start, position = 1, position + 1, position + 1
    while position < len(text):
        character = text[position]
        if character == "\\":
            position += 2
            continue
        if character == "{": depth += 1
        if character == "}": depth -= 1
        if depth == 0:
            return text[start:position], position + 1
        position += 1
    raise ValueError("Unbalanced BibTeX braces")


def parse_bibtex(text):
    """Balanced-brace parser; preserve field contents and reject silent losses.

    Supports brace-form entries, braced/quoted fields and bare numeric values.
    Macro definitions/concatenation are deliberately unsupported, never guessed.
    """
    entries, position = {}, 0
    while (position := _skip(text, position)) < len(text):
        header = re.match(r"@([A-Za-z]+)\s*", text[position:])
        require(header is not None, "Unexpected BibTeX text outside an entry")
        kind = header.group(1).lower()
        position += header.end()
        body, position = _braced(text, position)
        if kind == "comment": continue
        require(kind not in {"string", "preamble"}, "BibTeX macros/preambles are unsupported")
        match = re.match(r"\s*([^,\s]+)\s*,", body)
        require(match is not None, "Missing BibTeX citation key")
        key, cursor = match.group(1), match.end()
        require(key not in entries, "Duplicate bibliography key: " + key)
        fields = {}
        while (cursor := _skip(body, cursor)) < len(body):
            if body[cursor] == ",":
                cursor += 1
                continue
            field = re.match(r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*", body[cursor:])
            require(field is not None, "Invalid BibTeX field in " + key)
            name, cursor = field.group(1).lower(), cursor + field.end()
            require(name not in fields, "Duplicate bibliography field: " + key + "." + name)
            require(cursor < len(body), "Missing field value")
            if body[cursor] == "{":
                value, cursor = _braced(body, cursor)
            elif body[cursor] == '"':
                start, cursor = cursor + 1, cursor + 1
                while cursor < len(body):
                    if body[cursor] == "\\": cursor += 2
                    elif body[cursor] == '"': break
                    else: cursor += 1
                require(cursor < len(body), "Unterminated quoted bibliography field")
                value, cursor = body[start:cursor], cursor + 1
            else:
                number = re.match(r"\d+", body[cursor:])
                require(number is not None, "Unsupported BibTeX macro or field value")
                value, cursor = number.group(0), cursor + number.end()
            fields[name] = value
            cursor = _skip(body, cursor)
            require(cursor == len(body) or body[cursor] == ",", "Expected comma after bibliography field")
        require({"author", "title", "year"} <= fields.keys(), "Incomplete bibliography entry: " + key)
        entries[key] = {"entry_type": kind, **fields}
    return entries


def tex_plain(value):
    accents = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302",
               "~": "\u0303", "=": "\u0304", ".": "\u0307", "c": "\u0327",
               "v": "\u030c", "u": "\u0306", "H": "\u030b", "r": "\u030a"}
    pattern = r"\\([\"'`^~=\.cvuHr])\s*\{?([A-Za-z])\}?"
    value = re.sub(pattern, lambda m: unicodedata.normalize("NFC", m[2] + accents[m[1]]), value)
    for macro, replacement in (("ss", "ß"), ("ae", "æ"), ("AE", "Æ"), ("oe", "œ"),
                               ("OE", "Œ"), ("o", "ø"), ("O", "Ø"), ("aa", "å"), ("AA", "Å")):
        value = re.sub(r"\\" + macro + r"(?![A-Za-z])", replacement, value)
    value = re.sub(r"\\([&%_#${}])", r"\1", value)
    require(re.search(r"\\[A-Za-z]", value) is None, "Unsupported TeX macro in bibliography display")
    return value.replace("{", "").replace("}", "").replace("--", "–").strip()


def text_value(value, scope):
    require(isinstance(value, str) and bool(value.strip()), scope + " must be nonempty text")
    return value


def _only(value, allowed, required, scope):
    require(isinstance(value, dict), scope + " must be an object")
    require(required <= value.keys() and value.keys() <= allowed, scope + ": missing/unknown fields")


def source_texts(source):
    """Yield visible text in exactly the render order, including table cells."""
    yield source["title"]
    yield from source["authors"]
    if "abstract" in source: yield source["abstract"]
    yield from source["keywords"]
    def walk(blocks):
        for block in blocks:
            kind = block["type"]
            if kind == "paragraph": yield block["text"]
            elif kind == "subsection":
                yield block["title"]
                yield from walk(block["blocks"])
            elif kind == "table":
                yield block["caption"]
                yield from block["headers"]
                for row in block["rows"]:
                    yield from ("" if cell is None else str(cell) for cell in row)
                yield from block.get("notes", [])
            elif kind == "figure": yield block["caption"]
    for section in [*source["sections"], *source["back_matter"]]:
        yield section["title"]
        yield from walk(section["blocks"])


def citation_keys(text):
    result = []
    for match in CITE.finditer(text):
        keys = [part.strip() for part in match[1].split(",")]
        require(all(keys) and len(set(keys)) == len(keys), "Empty/duplicate key within citation token")
        result.extend(keys)
    require("{cite" not in CITE.sub("", text), "Malformed citation token")
    return result


def validate_references(texts, reference_order, bibliography):
    require(isinstance(reference_order, list) and all(isinstance(k, str) and k for k in reference_order),
            "reference_order must be a list of keys")
    require(len(set(reference_order)) == len(reference_order), "Duplicate reference_order key")
    require(set(reference_order) <= bibliography.keys(), "Unknown key in reference_order")
    seen = []
    for text in texts:
        for key in citation_keys(text):
            require(key in bibliography and key in reference_order, "Unknown/unlisted citation key: " + key)
            if key not in seen: seen.append(key)
    require(set(seen) == set(reference_order), "Unused entry in reference_order")
    require(seen == reference_order, "reference_order differs from actual first-citation order")
    return {key: i + 1 for i, key in enumerate(reference_order)}


def replace_citations(text, numbers):
    citation_keys(text)  # Malformed tokens must not pass through to the document.
    return CITE.sub(lambda m: "[" + ", ".join(str(numbers[k.strip()]) for k in m[1].split(",")) + "]", text)


def validate_source(source, root, bibliography):
    required = {"format", "kind", "title", "authors", "keywords", "sections", "back_matter", "reference_order", "evidence_binding"}
    _only(source, required | {"abstract"}, required, "source")
    require(source["format"] == "v2-document-source-1" and source["kind"] in {"main", "supplement"}, "Invalid source format/kind")
    text_value(source["title"], "title")
    for name in ("authors", "keywords"):
        require(isinstance(source[name], list), name + " must be a list")
        for value in source[name]: text_value(value, name)
    if "abstract" in source: text_value(source["abstract"], "abstract")
    require(isinstance(source["sections"], list) and source["sections"], "At least one section is required")
    require(isinstance(source["back_matter"], list), "back_matter must be a list")
    assets, identifiers = set(), set()
    def blocks(items, level):
        require(isinstance(items, list) and items and level <= 6, "Invalid blocks or section depth")
        for block in items:
            require(isinstance(block, dict) and "type" in block, "Each block requires a type")
            kind = block["type"]
            if kind == "paragraph":
                _only(block, {"type", "text"}, {"type", "text"}, kind)
                text_value(block["text"], "paragraph")
            elif kind == "subsection":
                _only(block, {"type", "title", "blocks"}, {"type", "title", "blocks"}, kind)
                text_value(block["title"], "subsection title"); blocks(block["blocks"], level + 1)
            elif kind in {"table", "figure"}:
                common = {"type", "id", "caption"}
                allowed = common | ({"headers", "rows", "column_weights", "alignments", "font_size_pt", "notes"}
                                    if kind == "table" else {"path", "alt", "width_inches"})
                needed = common | ({"headers", "rows"} if kind == "table" else {"path", "alt"})
                _only(block, allowed, needed, kind)
                identifier = text_value(block["id"], kind + " id")
                require(identifier not in identifiers, "Duplicate figure/table id"); identifiers.add(identifier)
                text_value(block["caption"], kind + " caption")
                if kind == "figure":
                    path = project_path(root, block["path"])
                    require(path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}, "Unsupported image format")
                    text_value(block["alt"], "figure alt")
                    require("{cite" not in block["alt"], "Citations belong in visible text, not alt metadata")
                    width = block.get("width_inches", 6.5)
                    require(type(width) in (int, float) and math.isfinite(width) and 0 < width <= 6.5, "Figure width must fit6.5-inch body")
                    assets.add(block["path"])
                else:
                    headers, rows = block["headers"], block["rows"]
                    require(isinstance(headers, list) and headers and all(isinstance(x, str) and x.strip() for x in headers), "Invalid table headers")
                    require(isinstance(rows, list) and rows and all(isinstance(row, list) and len(row) == len(headers) for row in rows), "Invalid table dimensions")
                    for row in rows:
                        require(all(cell is None or isinstance(cell, str) or
                                    (type(cell) in (int, float) and math.isfinite(cell)) for cell in row), "Invalid table cell")
                    font = block.get("font_size_pt", 9.5)
                    require(type(font) in (int, float) and math.isfinite(font) and 9 <= font <= 11, "Table font must be9..11pt")
                    weights = block.get("column_weights", [1.] * len(headers))
                    require(isinstance(weights, list) and len(weights) == len(headers) and all(
                        type(w) in (int, float) and math.isfinite(w) and w > 0 for w in weights), "Invalid table column weights")
                    require(math.isfinite(sum(weights)), "Table column weights overflow")
                    alignment = block.get("alignments", ["left"] * len(headers))
                    require(isinstance(alignment, list) and len(alignment) == len(headers) and
                            all(a in {"left", "center", "right"} for a in alignment), "Invalid table alignments")
                    notes = block.get("notes", [])
                    require(isinstance(notes, list) and all(isinstance(n, str) and n.strip() for n in notes), "Invalid table notes")
            else: raise ValueError("Unknown block type: " + str(kind))
    for section in [*source["sections"], *source["back_matter"]]:
        _only(section, {"title", "blocks"}, {"title", "blocks"}, "section")
        text_value(section["title"], "section title"); blocks(section["blocks"], 1)
    numbers = validate_references(source_texts(source), source["reference_order"], bibliography)
    return numbers, assets


def secondary_evidence_gate(root, mapping):
    """Bind post-freeze supplements separately from the original six tables."""
    require(isinstance(mapping, dict), "Supplemental evidence must be a SHA map")
    if (root / ACTIVE_AMENDMENT).exists():
        require({ACTIVE_AMENDMENT, ACTIVE_AUDIT} <= mapping.keys(),
                "Missing active amendment/audit manuscript evidence")
    families = (
        ("configs/v2_cuda_execution_plan.json", "evidence/v2/cuda_execution_audit.json",
         "tables/v2_cuda/descriptive_analysis.json", 90),
        ("configs/v2_pixel_budget_plan.json", "evidence/v2/pixel_budget_audit.json",
         "tables/v2_pixel_budget/descriptive_analysis.json", 27),
    )
    for plan, audit_name, analysis_name, count in families:
        if (root / plan).exists():
            require({plan, audit_name, analysis_name} <= mapping.keys(),
                    "Missing supplemental manuscript evidence: " + plan)
            if count == 90:
                from v2_cuda_delivery_inventory import build_inventory
                build_inventory(root)
            else:
                from v2_audit_pixel_budget import validate_bundle
                validate_bundle(root)
    for relative, checksum in mapping.items():
        require(isinstance(checksum, str) and SHA.fullmatch(checksum) is not None,
                "Invalid supplemental SHA256")
        require(sha_file(project_path(root, relative)) == checksum,
                "Stale supplemental evidence binding: " + relative)


def evidence_gate(root, binding, assets):
    required = {"audited_result_inventory_sha256", "freeze_sha256",
                "numeric_file_sha256", "bibliography_sha256", "asset_sha256"}
    _only(binding, required | {"supplemental_file_sha256"}, required, "evidence_binding")
    secondary_evidence_gate(root, binding.get("supplemental_file_sha256", {}))
    def match(relative, checksum):
        require(isinstance(checksum, str) and SHA.fullmatch(checksum) is not None, "Invalid SHA256 binding")
        require(sha_file(project_path(root, relative)) == checksum, "Stale evidence binding: " + relative)
    active = (root / ACTIVE_AMENDMENT).exists()
    audit_name = ACTIVE_AUDIT if active else "evidence/v2/run_completeness.json"
    if active:
        # This delegate validates the actual mixed-source inventory and current
        # descriptive tables; it must never complete the abandoned CPU90 plan.
        from v2_active_gpu_results import validate_bundle
        validated = validate_bundle(root)
        require(isinstance(validated, dict) and validated.get("passed") is True and not validated.get("errors"),
                "Full active bundle validation did not pass")
    audit_sha = sha_file(project_path(root, audit_name))
    analysis_sha = sha_file(project_path(root, "tables/v2/analysis_identity.json"))
    match("configs/v2_freeze.json", binding["freeze_sha256"])
    match(BIB_PATH, binding["bibliography_sha256"])
    audit = read_json(root / audit_name)
    analysis = read_json(root / "tables/v2/analysis_identity.json")
    freeze = read_json(root / "configs/v2_freeze.json")
    require(audit.get("passed") is True and audit.get("expected_total") == audit.get("validated_runs") ==
            audit.get("observed_result_files") == 576 and len(audit.get("results", {})) == 576, "Passed exact576-run audit required")
    require(not any(audit.get(k) for k in ("errors", "missing", "extra", "duplicates")), "Unresolved run-audit errors")
    require(freeze.get("status") == "FROZEN_BEFORE_NEW_PANEL_EVALUATION", "Invalid freeze status")
    require(isinstance(freeze.get("file_sha256"), dict) and len(freeze["file_sha256"]) == 53,
            "The preserved53-file freeze is required")
    for relative, checksum in freeze["file_sha256"].items():
        match(relative, checksum)
        require(audit.get("inputs", {}).get(relative) == checksum, "Audit omits/changes a frozen input")
    require(analysis.get("counts", {}).get("fits") == 576 and
            analysis.get("audit_sha256") == audit_sha, "Analysis does not bind the current complete576 audit")
    require(isinstance(binding["audited_result_inventory_sha256"], str) and
            SHA.fullmatch(binding["audited_result_inventory_sha256"]) is not None and
            audited_result_inventory_sha256(audit["results"]) == binding["audited_result_inventory_sha256"],
            "Audited scientific result inventory changed")
    require(analysis.get("audited_input_sha256") == audit.get("inputs") and
            audit.get("inputs", {}).get("configs/v2_freeze.json") == binding["freeze_sha256"], "Analysis/audit/current freeze differ")
    require(analysis.get("result_sha256") == audit["results"], "Analysis result inventory differs from audit")
    for name in ("numeric_file_sha256", "asset_sha256"):
        require(isinstance(binding[name], dict), name + " must be a SHA map")
    require(set(binding["numeric_file_sha256"]) == set(NUMERIC_FILES) and
            analysis.get("output_sha256") == binding["numeric_file_sha256"], "Exactly six current analysis output bindings required")
    for relative, checksum in binding["numeric_file_sha256"].items(): match(relative, checksum)
    require(set(binding["asset_sha256"]) == assets, "Figure assets must be bound exactly")
    for relative, checksum in binding["asset_sha256"].items(): match(relative, checksum)
    if active:
        require(audit.get("format") == "v2-active-run-completeness-1" and
                analysis.get("format") == "v2-active-analysis-identity-1", "Active report formats differ")
        require(audit.get("role") == ACTIVE_ROLE and audit.get("new_confirmatory_evidence") is False and
                audit.get("original_CPU90_completed") is False and analysis.get("new_confirmatory_evidence") is False and
                audit.get("active_model_counts") == {"resnet18_unet": 90, "dinov2_mlp128": 486},
                "Active GPU display must retain its descriptive backend revision scope")
        amendment_sha = sha_file(project_path(root, ACTIVE_AMENDMENT))
        require(audit.get("inputs", {}).get(ACTIVE_AMENDMENT) == amendment_sha and
                binding["supplemental_file_sha256"].get(ACTIVE_AMENDMENT) == amendment_sha and
                binding["supplemental_file_sha256"].get(ACTIVE_AUDIT) == audit_sha,
                "Active amendment/audit source bindings differ")
        cuda = {p.relative_to(root).as_posix() for p in (root / ACTIVE_CUDA).rglob("result.json")}
        frozen = {p.relative_to(root).as_posix() for p in (root / ACTIVE_FROZEN).rglob("result.json")}
        require(len(cuda) == 90 and len(frozen) == 486 and not cuda & frozen,
                "Active results must be all90 GPU plus486 frozen results")
        actual_results = cuda | frozen
        reference = audit.get("cpu_reference_result_files")
        reference_files = audit.get("cpu_reference_files")
        require(isinstance(reference, dict) and len(reference) == 72 and isinstance(reference_files, dict) and
                set(reference) <= set(reference_files) and not set(reference_files) & actual_results,
                "CPU72 reference must remain separately bound, never part of active576")
        actual_reference = {p.relative_to(root).as_posix() for p in (root / CPU_REFERENCE).rglob("result.json")}
        actual_reference_files = {p.relative_to(root).as_posix() for p in (root / CPU_REFERENCE).rglob("*") if p.is_file()}
        require(actual_reference == set(reference) and actual_reference_files == set(reference_files),
                "CPU reference result/history inventory differs")
        for category in (reference, reference_files):
            for relative, checksum in category.items(): match(relative, checksum)
        require(analysis.get("counts") == {"fits": 576, "conditions_by_source": 192, "conditions": 64,
                "regions_rows": 1536, "classes_rows": 512}, "Active canonical table dimensions differ")
        require(analysis.get("audited_artifact_sha256") == audit.get("artifacts"), "Active artifact analysis binding differs")
    else:
        actual_results = {p.relative_to(root).as_posix() for p in (root / "evidence/v2/runs").rglob("result.json")}
    require(actual_results == set(audit["results"]), "Result inventory changed after audit")
    for category in ("inputs", "artifacts", "results"):
        require(isinstance(audit.get(category), dict), "Missing audited file map")
        for relative, checksum in audit[category].items(): match(relative, checksum)
    require(analysis.get("audit_code_sha256") == audit.get("audit_code_sha256"), "Audit code identity differs")
    if active:
        match(ACTIVE_CODE, audit["audit_code_sha256"])
        match(ACTIVE_CODE, analysis["analysis_code_sha256"])
        reference_sha = freeze["file_sha256"].get("code/v2_statistics.py")
        require(audit.get("statistical_reference_code_sha256") == analysis.get("statistical_reference_code_sha256") == reference_sha,
                "Active orchestration and frozen statistical reference identities differ")
        match("code/v2_statistics.py", reference_sha)
    else:
        match("code/v2_audit_runs.py", audit["audit_code_sha256"])
        match("code/v2_statistics.py", analysis["analysis_code_sha256"])
    observations = {"run_completeness_sha256": audit_sha, "analysis_identity_sha256": analysis_sha,
                    "audited_result_inventory_sha256": binding["audited_result_inventory_sha256"],
                    "audit_report_file": audit_name}
    if active:
        observations.update(active_backend_amendment_sha256=amendment_sha, main_display_role=ACTIVE_ROLE,
                            new_confirmatory_evidence=False, separate_cpu_reference_results=72,
                            statistical_reference_code_sha256=reference_sha)
    return observations


def reference_text(entry, number):
    f = {key: tex_plain(value) for key, value in entry.items()}
    authors = "; ".join(f["author"].split(" and ")).rstrip(".")
    venue = f.get("journal", f.get("booktitle", "arXiv preprint" if "eprint" in f else ""))
    detail = f.get("volume", "") + ("(" + f["number"] + ")" if "number" in f else "")
    if f.get("pages"): detail += (", " if detail else "") + f["pages"]
    pieces = [f"[{number}] {authors}.", f["title"] + ".", venue + "." if venue else "", f["year"] + "."]
    if detail: pieces.append(detail + ".")
    if "eprint" in f: pieces.append("arXiv:" + f["eprint"] + ".")
    if "note" in f: pieces.append(f["note"] + ".")
    link = "https://doi.org/" + f["doi"] if "doi" in f else f.get("url", "")
    if link: pieces.append(link)
    return " ".join(piece for piece in pieces if piece)


def render_document(source, bibliography, numbers, output, root):
    # Future authoring calls require the documents skill's marker and render/PNG
    # inspection workflow outside this engine. Syntax/parser checks never enter.
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.image.image import Image

    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(1)
    section.top_margin = section.bottom_margin = Inches(.8)
    columns = section._sectPr.find(qn("w:cols"))
    if columns is not None: columns.set(qn("w:num"), "1")
    def font(run, size):
        run.font.name = "Times New Roman"; run.font.size = Pt(size); run.font.color.rgb = RGBColor(0, 0, 0)
        fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
        for attribute in list(fonts.attrib):
            if "theme" in attribute.lower(): del fonts.attrib[attribute]
        for key in ("ascii", "hAnsi", "eastAsia", "cs"): fonts.set(qn("w:" + key), "Times New Roman")
    for name in ("Normal", "Title", "Subtitle", "Caption", "Footer", *[f"Heading {i}" for i in range(1, 7)]):
        style = document.styles[name]
        style.font.name = "Times New Roman"; style.font.size = Pt(11); style.font.color.rgb = RGBColor(0, 0, 0)
        rpr = style.element.get_or_add_rPr(); fonts = rpr.get_or_add_rFonts()
        for attribute in list(fonts.attrib):
            if "theme" in attribute.lower(): del fonts.attrib[attribute]
        for key in ("ascii", "hAnsi", "eastAsia", "cs"): fonts.set(qn("w:" + key), "Times New Roman")
        for border in list(style.element.iter(qn("w:pBdr"))): border.getparent().remove(border)
        pf = style.paragraph_format
        pf.page_break_before = False; pf.widow_control = True; pf.keep_with_next = False
        pf.space_after = Pt(6); pf.line_spacing = 1.15
    document.styles["Title"].font.size = Pt(16); document.styles["Title"].font.bold = True
    document.styles["Title"].paragraph_format.keep_with_next = True
    for i in range(1, 7):
        style = document.styles[f"Heading {i}"]
        style.font.size = Pt(13 if i == 1 else 11.5 if i == 2 else 11)
        style.font.bold = True; style.paragraph_format.keep_with_next = True
        style.paragraph_format.keep_together = True; style.paragraph_format.space_before = Pt(10)
    def paragraph(text, style=None, size=11, keep_next=False):
        p = document.add_paragraph(style=style)
        p.paragraph_format.keep_with_next = keep_next
        p.paragraph_format.widow_control = True
        run = p.add_run(replace_citations(text, numbers)); font(run, size)
        return p
    def heading(text, level=1):
        size = 13 if level == 1 else 11.5 if level == 2 else 11
        return paragraph(text, f"Heading {level}", size, True)
    paragraph(source["title"], "Title", 16, True)
    for author in source["authors"]: paragraph(author)
    if "abstract" in source:
        heading("Abstract"); paragraph(source["abstract"])
    if source["keywords"]:
        paragraph("Keywords: " + "; ".join(source["keywords"]))

    def walk(blocks, level):
        for block in blocks:
            kind = block["type"]
            if kind == "paragraph": paragraph(block["text"])
            elif kind == "subsection":
                heading(block["title"], level + 1); walk(block["blocks"], level + 1)
            elif kind == "figure":
                path = project_path(root, block["path"])
                image = Image.from_file(str(path))
                ratio = image.px_height / image.px_width
                width = min(block.get("width_inches", 6.5), 6.5, 7.7 / ratio)
                p = paragraph("", keep_next=True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                shape = p.add_run().add_picture(str(path), width=Inches(width), height=Inches(width * ratio))
                shape._inline.docPr.set("descr", block["alt"])
                shape._inline.docPr.set("title", block["id"])
                paragraph(block["caption"], "Caption", 10)
            elif kind == "table":
                paragraph(block["caption"], "Caption", 10, True)
                table = document.add_table(rows=1, cols=len(block["headers"]))
                table.alignment = WD_TABLE_ALIGNMENT.CENTER; table.autofit = False
                weights = block.get("column_weights", [1.] * len(block["headers"]))
                widths = [Inches(6.5 * w / sum(weights)) for w in weights]
                for column, width in zip(table.columns, widths): column.width = width
                alignment = block.get("alignments", ["left"] * len(widths))
                align_enum = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}
                values = [block["headers"], *block["rows"]]
                for row_number, values_row in enumerate(values):
                    row = table.rows[0] if row_number == 0 else table.add_row()
                    properties = row._tr.get_or_add_trPr()
                    properties.append(OxmlElement("w:cantSplit"))
                    if row_number == 0: properties.append(OxmlElement("w:tblHeader"))
                    for col_number, (cell, value) in enumerate(zip(row.cells, values_row)):
                        cell.width = widths[col_number]; cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                        cell.text = "" if value is None else replace_citations(str(value), numbers)
                        pr = cell._tc.get_or_add_tcPr()
                        borders = OxmlElement("w:tcBorders")
                        for edge in ("top", "left", "bottom", "right"):
                            node = OxmlElement("w:" + edge)
                            visible = (row_number == 0 and edge in {"top", "bottom"}) or (
                                row_number == len(values) - 1 and edge == "bottom")
                            size = "6" if row_number == 0 and edge == "bottom" else "12"
                            for attr, val in (("val", "single" if visible else "nil"),
                                              ("sz", size if visible else "0"), ("color", "000000")):
                                node.set(qn("w:" + attr), val)
                            borders.append(node)
                        pr.append(borders)
                        margin = OxmlElement("w:tcMar")
                        for edge in ("top", "left", "bottom", "right"):
                            node = OxmlElement("w:" + edge); node.set(qn("w:w"), "70"); node.set(qn("w:type"), "dxa"); margin.append(node)
                        pr.append(margin)
                        for p in cell.paragraphs:
                            p.alignment = align_enum[alignment[col_number]]
                            p.paragraph_format.keep_with_next = row_number == 0
                            p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(2)
                            p.paragraph_format.line_spacing = 1.05
                            for run in p.runs: font(run, block.get("font_size_pt", 9.5)); run.bold = row_number == 0
                for note in block.get("notes", []): paragraph(note, size=9.5)
    for entry in [*source["sections"], *source["back_matter"]]:
        heading(entry["title"]); walk(entry["blocks"], 1)
    if source["reference_order"]:
        heading("References")
        for key in source["reference_order"]:
            p = paragraph(reference_text(bibliography[key], numbers[key]), size=10)
            p.paragraph_format.left_indent = Inches(.22); p.paragraph_format.first_line_indent = Inches(-.22)
    footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple"); field.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r"); text = OxmlElement("w:t"); text.text = "1"; run.append(text); field.append(run)
    footer._p.append(field)
    # Never infer author approval, funding, declarations, or creator identities.
    props = document.core_properties
    for name in ("author", "last_modified_by", "comments", "subject", "keywords", "category", "content_status", "identifier", "version"):
        setattr(props, name, "")
    props.title = source["title"]
    temporary = output.with_name(output.stem + ".building.docx")
    require(not temporary.exists(), "Temporary output already exists")
    try:
        document.save(temporary); temporary.replace(output)
    finally:
        if temporary.exists(): temporary.unlink()


def build(source_path, output_path, *, validate_only=False, overwrite=False, root=ROOT):
    root = root.resolve()
    source_path = paper_path(source_path, ".json", root)
    output = paper_path(output_path, ".docx", root, existing=False)
    require(not output.exists() or overwrite or validate_only, "Output exists; use --overwrite for a deliberate rebuild")
    source = read_json(source_path)
    bibliography = parse_bibtex((root / BIB_PATH).read_text(encoding="utf-8-sig"))
    numbers, assets = validate_source(source, root, bibliography)
    observations = evidence_gate(root, source["evidence_binding"], assets)
    # Validate bibliography display before making an output directory/artifact.
    for key in source["reference_order"]: reference_text(bibliography[key], numbers[key])
    report = {"source_sha256": sha_file(source_path), "kind": source["kind"],
              "references_used": len(numbers), "evidence_gate_passed": True,
              "execution_observations": observations,
              "scientific_claims_or_table_values_reviewed": False, "rendered_or_visually_verified": False,
              "author_approval_asserted": False}
    if not validate_only:
        output.parent.mkdir(parents=True, exist_ok=True)
        render_document(source, bibliography, numbers, output, root)
        report.update(output=str(output), output_sha256=sha_file(output), status="generated_requires_render_and_review")
    else: report["status"] = "source_and_bindings_checked_no_document_created"
    return report


class ParserChecks(unittest.TestCase):
    @staticmethod
    def active_fixture(root):
        """Opaque synthetic byte records; no masks, scores, source or DOCX."""
        def put(name, data):
            p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data if isinstance(data, bytes) else (json.dumps(data, sort_keys=True) + "\n").encode())
            return sha_file(p)
        fixed = ["code/v2_statistics.py", "code/v2_audit_runs.py", *[f"code/frozen_fixture_{i}.py" for i in range(51)]]
        frozen = {n: put(n, ("# synthetic preserved bytes: " + n).encode()) for n in fixed}
        freeze_sha = put("configs/v2_freeze.json", {"status": "FROZEN_BEFORE_NEW_PANEL_EVALUATION", "file_sha256": frozen})
        amendment_sha = put(ACTIVE_AMENDMENT, {"fixture": "post-exposure user backend amendment"})
        active_code_sha = put(ACTIVE_CODE, b"# synthetic active descriptive orchestration\n")
        gpu = {f"{ACTIVE_CUDA}/gpu_{i}/result.json": put(f"{ACTIVE_CUDA}/gpu_{i}/result.json", b"synthetic GPU record") for i in range(90)}
        head = {f"{ACTIVE_FROZEN}/frozen_{i}/result.json": put(f"{ACTIVE_FROZEN}/frozen_{i}/result.json", b"synthetic frozen record") for i in range(486)}
        cpu = {f"{CPU_REFERENCE}/cpu_{i}/result.json": put(f"{CPU_REFERENCE}/cpu_{i}/result.json", b"synthetic CPU reference") for i in range(72)}
        history = {f"{CPU_REFERENCE}/cpu_0/history.json": put(f"{CPU_REFERENCE}/cpu_0/history.json", b"synthetic prior history")}
        log_name = f"{ACTIVE_FROZEN}/frozen_0/log.jsonl"
        artifacts = {log_name: put(log_name, b"synthetic raw log\n")}
        outputs = {n: put(n, ("synthetic numeric bytes: " + n).encode()) for n in NUMERIC_FILES}
        bib_sha = put(BIB_PATH, b"synthetic bibliography bytes\n")
        audit = {"format": "v2-active-run-completeness-1", "passed": True, "expected_total": 576,
                 "validated_runs": 576, "observed_result_files": 576, "results": {**gpu, **head},
                 "inputs": {**frozen, "configs/v2_freeze.json": freeze_sha, ACTIVE_AMENDMENT: amendment_sha},
                 "artifacts": artifacts, "cpu_reference_result_files": cpu, "cpu_reference_files": {**cpu, **history},
                 "audit_code_sha256": active_code_sha, "statistical_reference_code_sha256": frozen["code/v2_statistics.py"],
                 "role": ACTIVE_ROLE, "new_confirmatory_evidence": False, "original_CPU90_completed": False,
                 "active_model_counts": {"resnet18_unet": 90, "dinov2_mlp128": 486},
                 "errors": [], "missing": [], "extra": [], "duplicates": []}
        analysis = {"format": "v2-active-analysis-identity-1", "audit_sha256": "filled below",
                    "counts": {"fits": 576, "conditions_by_source": 192, "conditions": 64, "regions_rows": 1536, "classes_rows": 512},
                    "audit_code_sha256": active_code_sha, "analysis_code_sha256": active_code_sha,
                    "statistical_reference_code_sha256": frozen["code/v2_statistics.py"],
                    "new_confirmatory_evidence": False, "output_sha256": outputs}
        binding = {"audited_result_inventory_sha256": "filled below", "freeze_sha256": freeze_sha,
                   "numeric_file_sha256": outputs, "bibliography_sha256": bib_sha, "asset_sha256": {},
                   "supplemental_file_sha256": {ACTIVE_AMENDMENT: amendment_sha}}
        ParserChecks.resign_active_fixture(root, audit, analysis, binding)
        return audit, analysis, binding

    @staticmethod
    def resign_active_fixture(root, audit, analysis, binding):
        """Rebind altered synthetic metadata, so policy checks face fresh SHAs."""
        (root / ACTIVE_AUDIT).parent.mkdir(parents=True, exist_ok=True)
        (root / ACTIVE_AUDIT).write_text(json.dumps(audit, sort_keys=True), encoding="utf-8")
        checksum = sha_file(root / ACTIVE_AUDIT)
        analysis.update(audit_sha256=checksum, audited_input_sha256=audit["inputs"],
                        audited_artifact_sha256=audit["artifacts"], result_sha256=audit["results"])
        (root / "tables/v2/analysis_identity.json").write_text(json.dumps(analysis, sort_keys=True), encoding="utf-8")
        binding["audited_result_inventory_sha256"] = audited_result_inventory_sha256(audit["results"])
        binding["supplemental_file_sha256"][ACTIVE_AUDIT] = checksum

    def test_active_binding_uses_gpu576_and_separate_cpu72_without_completed_cpu_audit(self):
        import tempfile, sys
        from types import SimpleNamespace
        from unittest import mock
        with tempfile.TemporaryDirectory(prefix="active-document-fixture-") as directory:
            root = Path(directory); audit, analysis, binding = self.active_fixture(root)
            self.assertFalse((root / "evidence/v2/run_completeness.json").exists())
            validator = mock.Mock(return_value={"passed": True, "errors": []})
            with mock.patch.dict(sys.modules, {"v2_active_gpu_results": SimpleNamespace(validate_bundle=validator)}):
                observed = evidence_gate(root, binding, set())
                validator.assert_called_once_with(root)
                self.assertEqual(observed["audit_report_file"], ACTIVE_AUDIT)
                self.assertEqual(observed["main_display_role"], ACTIVE_ROLE)
                self.assertFalse(observed["new_confirmatory_evidence"])
                self.assertEqual(observed["separate_cpu_reference_results"], 72)
                # Delegation/refusal is explicitly mocked, not certified as an
                # actual576 audit by these opaque synthetic byte fixtures.
                validator.return_value = {"passed": False, "errors": ["synthetic refusal"]}
                with self.assertRaisesRegex(ValueError, "Full active bundle"): evidence_gate(root, binding, set())
                validator.return_value = {"passed": True, "errors": []}
                p = root / next(iter(audit["cpu_reference_result_files"])); old = p.read_bytes(); p.write_bytes(old+b"changed")
                with self.assertRaisesRegex(ValueError, "Stale evidence"): evidence_gate(root, binding, set())
                p.write_bytes(old)
                p = root / next(iter(audit["results"])); p.write_bytes(p.read_bytes()+b"changed")
                with self.assertRaisesRegex(ValueError, "Stale evidence"): evidence_gate(root, binding, set())

    def test_active_binding_refuses_rebound_cpu_mix_old_tool_identity_and_confirmatory_upgrade(self):
        import tempfile, sys
        from types import SimpleNamespace
        from unittest import mock
        with tempfile.TemporaryDirectory(prefix="active-document-refusal-") as directory:
            root = Path(directory); original_a, original_n, original_b = self.active_fixture(root)
            validator = mock.Mock(return_value={"passed": True, "errors": []})
            with mock.patch.dict(sys.modules, {"v2_active_gpu_results": SimpleNamespace(validate_bundle=validator)}):
                for case in ("cpu_mix", "cpu_reference_71", "old_audit_code", "old_analysis_code", "wrong_statistical_reference",
                             "confirmatory_role", "confirmatory_flag", "pretend_cpu90_complete", "missing_active_source_binding"):
                    a, n, b = [json.loads(json.dumps(v)) for v in (original_a, original_n, original_b)]
                    if case == "cpu_mix":
                        a["results"].pop(next(k for k in a["results"] if k.startswith(ACTIVE_CUDA+"/")))
                        name, checksum = next(iter(a["cpu_reference_result_files"].items())); a["results"][name] = checksum
                    elif case == "cpu_reference_71": a["cpu_reference_result_files"].pop(next(iter(a["cpu_reference_result_files"])))
                    elif case == "old_audit_code":
                        a["audit_code_sha256"] = sha_file(root/"code/v2_audit_runs.py"); n["audit_code_sha256"] = a["audit_code_sha256"]
                    elif case == "old_analysis_code": n["analysis_code_sha256"] = sha_file(root/"code/v2_statistics.py")
                    elif case == "wrong_statistical_reference":
                        a["statistical_reference_code_sha256"] = n["statistical_reference_code_sha256"] = sha_file(root/ACTIVE_CODE)
                    elif case == "confirmatory_role": a["role"] = "prospective_confirmatory_GPU_primary"
                    elif case == "confirmatory_flag": a["new_confirmatory_evidence"] = True
                    elif case == "pretend_cpu90_complete": a["original_CPU90_completed"] = True
                    self.resign_active_fixture(root, a, n, b)
                    if case == "missing_active_source_binding": b["supplemental_file_sha256"].pop(ACTIVE_AMENDMENT)
                    with self.subTest(case=case), self.assertRaises(ValueError): evidence_gate(root, b, set())

    def test_active_amendment_keeps_both_full_supplemental_validators(self):
        import tempfile, sys
        from types import SimpleNamespace
        from unittest import mock
        with tempfile.TemporaryDirectory(prefix="active-supplemental-delegation-") as directory:
            root = Path(directory)
            names = (ACTIVE_AMENDMENT, ACTIVE_AUDIT, "configs/v2_cuda_execution_plan.json",
                     "evidence/v2/cuda_execution_audit.json", "tables/v2_cuda/descriptive_analysis.json",
                     "configs/v2_pixel_budget_plan.json", "evidence/v2/pixel_budget_audit.json",
                     "tables/v2_pixel_budget/descriptive_analysis.json")
            for name in names:
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"fixture": name}), encoding="utf-8")
            mapping = {name:sha_file(root/name) for name in names}
            pixel = mock.Mock()
            with mock.patch("v2_cuda_delivery_inventory.build_inventory") as cuda, mock.patch.dict(
                    sys.modules, {"v2_audit_pixel_budget":SimpleNamespace(validate_bundle=pixel)}):
                secondary_evidence_gate(root, mapping)
                cuda.assert_called_once_with(root); pixel.assert_called_once_with(root)
                pixel.side_effect = ValueError("full pixel bundle rejected")
                with self.assertRaisesRegex(ValueError, "full pixel bundle rejected"): secondary_evidence_gate(root, mapping)
                pixel.side_effect = None
                bad = dict(mapping); bad.pop(ACTIVE_AUDIT)
                with self.assertRaisesRegex(ValueError, "Missing active"): secondary_evidence_gate(root, bad)
                bad = dict(mapping); bad.pop("tables/v2_pixel_budget/descriptive_analysis.json")
                with self.assertRaisesRegex(ValueError, "Missing supplemental"): secondary_evidence_gate(root, bad)

    def test_supplemental_evidence_cannot_be_missing_incomplete_or_changed(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory(prefix="v2-secondary-document-fixture-") as directory:
            root = Path(directory)
            secondary_evidence_gate(root, {})
            plan = "configs/v2_cuda_execution_plan.json"
            audit = "evidence/v2/cuda_execution_audit.json"
            analysis = "tables/v2_cuda/descriptive_analysis.json"
            def put(name, value):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            put(plan, {"synthetic": True})
            with self.assertRaisesRegex(ValueError, "Missing supplemental"):
                secondary_evidence_gate(root, {})
            # The full audit/inventory validator has its own synthetic90 tests.
            # Here its explicit mock tests delegation, refusal propagation and
            # the additional manuscript SHA binding, not scientific validation.
            put(audit, {"fixture": "opaque bytes checked by mocked full validator"})
            put(analysis, {"fixture": "opaque bytes checked by mocked full validator"})
            mapping = {p: sha_file(root / p) for p in (plan, audit, analysis)}
            with mock.patch("v2_cuda_delivery_inventory.build_inventory") as validator:
                secondary_evidence_gate(root, mapping)
                validator.assert_called_once_with(root)
                put(analysis, {"changed": True})
                with self.assertRaisesRegex(ValueError, "Stale supplemental"):
                    secondary_evidence_gate(root, mapping)
                validator.side_effect = ValueError("full inventory rejected stale analysis")
                with self.assertRaisesRegex(ValueError, "full inventory rejected"):
                    secondary_evidence_gate(root, mapping)

    def test_stable_inventory_ignores_report_timestamp_but_not_result_sha(self):
        results = {"runs/b/result.json": "b" * 64, "runs/a/result.json": "a" * 64}
        audit_before = {"created_utc": "2000-01-01T00:00:00Z", "results": dict(results)}
        audit_after = {"created_utc": "2000-01-02T00:00:00Z", "results": dict(reversed(list(results.items())))}
        before = audited_result_inventory_sha256(audit_before["results"])
        self.assertEqual(before, audited_result_inventory_sha256(audit_after["results"]))
        self.assertNotEqual(json.dumps(audit_before, sort_keys=True), json.dumps(audit_after, sort_keys=True))
        for path in results:
            changed = dict(results); changed[path] = "c" * 64
            self.assertNotEqual(before, audited_result_inventory_sha256(changed))

    def test_ordered_blocks_and_recursive_text_traversal(self):
        # Text labels only: this is not a paper source file and is never rendered.
        source = {"title": "T", "authors": [], "keywords": [],
                  "sections": [{"title": "Section", "blocks": [
                      {"type": "paragraph", "text": "P1"},
                      {"type": "figure", "caption": "F"},
                      {"type": "table", "caption": "C", "headers": ["H"], "rows": [["R"]], "notes": ["N"]},
                      {"type": "subsection", "title": "Sub", "blocks": [{"type": "paragraph", "text": "P2"}]}]}],
                  "back_matter": [{"title": "Back", "blocks": [{"type": "paragraph", "text": "P3"}]}]}
        self.assertEqual(list(source_texts(source)), ["T", "Section", "P1", "F", "C", "H", "R", "N", "Sub", "P2", "Back", "P3"])

    def test_balanced_bibtex_and_display(self):
        text = '% comment\n@article{a,author={Doe, A.},title={{Nested} title},year=2026}\n'
        parsed = parse_bibtex(text)
        self.assertEqual(parsed["a"]["title"], "{Nested} title")
        self.assertIn("Nested title", reference_text(parsed["a"], 1))
        self.assertEqual(tex_plain("Schr{\\\"o}der"), "Schröder")
        for bad in (text + text, '@article{a,title={broken}', '@misc{x,author={A},title={T},year=unknown}'):
            with self.assertRaises(ValueError): parse_bibtex(bad)

    def test_citation_order_unknown_duplicate_unused_and_caption(self):
        bibliography = {"a": {}, "b": {}}
        self.assertEqual(validate_references(["{cite:a}", "caption {cite:b,a}"], ["a", "b"], bibliography), {"a": 1, "b": 2})
        self.assertEqual(replace_citations("{cite:b,a}", {"a": 1, "b": 2}), "[2, 1]")
        for texts, order in ((["{cite:b,a}"], ["a", "b"]), (["{cite:a}"], ["a", "b"]),
                             (["{cite:unknown}"], ["a"]), (["{cite:a}"], ["a", "a"]),
                             (["{cite:a,a}"], ["a"]), (["{cite:a"], ["a"])):
            with self.assertRaises(ValueError): validate_references(texts, order, bibliography)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Editable JSON inside paper/v2")
    parser.add_argument("--output", type=Path, help="DOCX destination inside paper/v2")
    parser.add_argument("--validate-only", action="store_true", help="Check source/references/evidence, create no DOCX")
    parser.add_argument("--overwrite", action="store_true", help="Allow a deliberate rebuild of an existing output")
    parser.add_argument("--self-test", action="store_true", help="Stdlib parser checks only, no source/evidence/DOCX reads")
    args = parser.parse_args()
    if args.self_test:
        require(args.source is None and args.output is None, "Parser self-test takes no source/output")
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ParserChecks))
        return 0 if result.wasSuccessful() else 1
    parser.error("--source and --output are required") if args.source is None or args.output is None else None
    try:
        print(json.dumps(build(args.source, args.output, validate_only=args.validate_only, overwrite=args.overwrite), indent=2))
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        parser.exit(1, f"Build refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
