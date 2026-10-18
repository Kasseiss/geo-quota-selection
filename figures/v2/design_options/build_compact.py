"""Generate only compact workflow C and append print-size QA; never read outcomes."""
from pathlib import Path
from html import escape
from xml.etree import ElementTree as ET
import hashlib
import json
import subprocess
from PIL import ImageFont

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
W, H = 165.1, 185.4  # 6.5 in wide; approximately 7.3 in high.
FONT = Path('C:/Windows/Fonts/arial.ttf')
BOLD = Path('C:/Windows/Fonts/arialbd.ttf')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_svg(path):
    root = ET.parse(path).getroot()
    vb = [float(x) for x in root.attrib['viewBox'].split()]
    w, h = vb[2:]
    scale = min(6.5 * 25.4 / w, 7.7 * 25.4 / h)
    sizes = [float(e.attrib['font-size']) for e in root.iter()
             if e.tag.endswith('}text')]
    return dict(native_mm=[w, h], insertion_mm=[w * scale, h * scale],
                insertion_inches=[w * scale / 25.4, h * scale / 25.4],
                scale=scale, minimum_print_pt=min(sizes) * scale * 72 / 25.4,
                svg_sha256=sha(path))


def main():
    original = {p.name: sha(p) for p in OUT.glob('figure_v2_variant_[AB].*')}
    parts = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="6.5in" height="{H:.1f}mm" viewBox="0 0 {W:.1f} {H:.1f}" version="1.1">
<title>Compact workflow: development, selection, model recipes and isolated evaluation</title>
<desc>Methods overview only. No model outcomes. All text remains editable Arial. New-panel evaluation has no feedback arrows.</desc>
<defs><marker id="forward-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#000000"/></marker></defs>
<g id="background"><rect x="0.0" y="0.0" width="{W:.1f}" height="{H:.1f}" fill="#FFFFFF"/></g>''']
    texts, boxes = [], []

    def text(key, x, y, value, size=3.3, bold=False, box=None):
        font = ImageFont.truetype(str(BOLD if bold else FONT), round(size * 100))
        l, t, r, b = font.getbbox(value, anchor='ls')
        bounds = [x + l / 100, y + t / 100, x + r / 100, y + b / 100]
        area = box or (0, 0, W, H)
        bx, by, bw, bh = area
        assert bounds[0] >= bx + 1 and bounds[2] <= bx + bw - 1, (key, bounds, area)
        assert bounds[1] >= by + 1 and bounds[3] <= by + bh - 1, (key, bounds, area)
        texts.append(dict(id=key, text=value, font_mm=size, measured_bounds_mm=bounds))
        parts.append(f'<g id="{key}"><text x="{x:.1f}" y="{y:.1f}" font-family="Arial" font-size="{size:.1f}" font-weight="{"bold" if bold else "normal"}" fill="#000000">{escape(value)}</text></g>')

    def panel(letter, y, height, title, lines, color, fill):
        box = (6, y, W - 12, height)
        boxes.append(box)
        parts.append(f'<g id="panel-{letter}" inkscape:groupmode="layer" inkscape:label="Panel {letter}">')
        text('panel-label-' + letter, 6, y - 2.5, letter, 3.6, True)
        parts.append(f'<g id="panel-{letter}-boundary"><rect x="6.0" y="{y:.1f}" width="{W-12:.1f}" height="{height:.1f}" rx="1.5" fill="{fill}" stroke="{color}" stroke-width="0.3"/></g>')
        text('panel-' + letter + '-heading', 11, y + 6, title, 3.6, True, box)
        for index, line in enumerate(lines):
            text(f'panel-{letter}-line-{index+1}', 11, y + 12 + 6 * index, line, box=box)
        parts.append('</g>')

    panel('a', 12, 28, 'Old panel: development only', [
        '24 regions × 5 images = 120 images',
        '3 fixed allocations: 12 source / 4 validation / 8 unused',
        'Calibration uses extra development labels outside budget B',
    ], '#0072B2', '#F1F7FB')
    panel('b', 58, 28, 'Candidate selection without candidate masks', [
        '36 candidates per pool; balanced and skewed profiles',
        'DINOv2 RGB descriptors + source IDs + budget + seed',
        '8 base selectors + real / permuted weighted FL (skewed only)',
    ], '#0072B2', '#FFFFFF')
    panel('c', 104, 28, 'Two different model recipes', [
        'ResNet18 U-Net-style: 90 full fits; B=12, skewed pool',
        'Frozen DINOv2 + MLP: 486 fits; B=6/12/24, both pools',
        '3 allocations × 3 paired fit seeds per condition; 576 fits total',
    ], '#E69F00', '#FFF9EE')
    panel('d', 150, 28, 'New panel: 24 regions × 3 images = 72; evaluation only', [
        'Per fit / region: merge the 3 image confusion matrices',
        'Regional union-class mIoU → average across the 9 fits',
        '24-region paired bootstrap; 10,000 resamples',
    ], '#0072B2', '#F1F7FB')
    parts.append('<g id="arrows" inkscape:groupmode="layer" inkscape:label="Forward flow only">')
    for index, (start, end) in enumerate(((43, 55), (89, 101), (135, 147))):
        parts.append(f'<g id="forward-{index+1}"><line x1="82.5" y1="{start:.1f}" x2="82.5" y2="{end:.1f}" stroke="#000000" stroke-width="0.3" marker-end="url(#forward-arrow)"/></g>')
    parts.append('</g></svg>')
    svg = OUT / 'figure_v2_variant_C.svg'
    svg.write_text('\n'.join(parts), encoding='utf-8')
    parsed = ET.parse(svg).getroot()
    ids = [element.attrib['id'] for element in parsed.iter() if 'id' in element.attrib]
    assert len(ids) == len(set(ids))
    assert not any(element.tag.endswith('}image') for element in parsed.iter())
    assert all('transform' not in element.attrib for element in parsed.iter())
    audit = {letter: audit_svg(OUT / f'figure_v2_variant_{letter}.svg') for letter in 'ABC'}
    assert audit['C']['minimum_print_pt'] >= 9
    assert all(sha(OUT / name) == checksum for name, checksum in original.items())
    runtime = Path('C:/Users/china/.cache/codex-runtimes/codex-primary-runtime/dependencies/node')
    sharp = runtime / 'node_modules/sharp'
    png = svg.with_suffix('.png')
    subprocess.run([str(runtime / 'bin/node.exe'), '-e',
                    'const sharp=require(process.argv[1]); sharp(process.argv[2]).resize({width:1950}).png().toFile(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});',
                    str(sharp), str(svg), str(png)], check=True)
    qa_path = OUT / 'figure_qa.json'
    qa = json.loads(qa_path.read_text(encoding='utf-8'))
    qa['compact_print_audit'] = dict(
        maximum_insertion_inches=[6.5, 7.7],
        method='Preserve aspect ratio; scale=min(max_width/viewBox_width,max_height/viewBox_height); point size=font_size*scale*72/25.4. No transformed text.',
        variants=audit, preserved_AB_sha256=original,
        source_sha256={name: sha(ROOT / name) for name in (
            'configs/v2_design.json', 'configs/v2_extension.json',
            'configs/v2_geographic_sensitivity.json', 'docs/v2_protocol.md')},
        generator_sha256=sha(Path(__file__)),
        preserved_AB_generator_sha256=sha(OUT / 'build_variants.py'),
        c_png=dict(filename=png.name, sha256=sha(png), width_px=1950,
                   renderer='Existing bundled Sharp; 300 pixels/inch at native 6.5 inch width'),
        c_checks=dict(editable_arial=True, embedded_rasters=0, text_bounds='Windows Arial/Arial Bold via Pillow, >=1 mm containment; panel text >=4 mm horizontal inset',
                      minimum_arrow_length_mm=12, arrow_border_clearance_mm=3,
                      model_results_read=False, outcomes_or_effect_claims=False,
                      visual_review='Pending PNG inspection; cross-application embedding not tested'),
        c_texts=texts)
    qa_path.write_text(json.dumps(qa, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
