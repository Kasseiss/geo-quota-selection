"""Editable methods schematics only; no model outputs or scientific results."""
from pathlib import Path
import hashlib
import json
from html import escape
from xml.etree import ElementTree as ET
from PIL import ImageFont

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FONT = Path('C:/Windows/Fonts/arial.ttf')
BOLD = Path('C:/Windows/Fonts/arialbd.ttf')


class Canvas:
    def __init__(self, name, height):
        self.name, self.height, self.parts, self.texts, self.arrows = name, height, [], [], []
        self.parts.append(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="180mm" height="{height:.1f}mm" viewBox="0 0 180 {height:.1f}" version="1.1">
<title>{escape(name)}</title>
<desc>Extension-study methods only. No performance values. Editable Arial text. The new panel has no feedback connection to development, selection or calibration.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#000000"/></marker></defs>
<g id="page"><rect x="0.0" y="0.0" width="180.0" height="{height:.1f}" fill="#FFFFFF"/></g>''')

    def group(self, key, label=None):
        self.parts.append(f'<g id="{key}" inkscape:groupmode="layer" inkscape:label="{escape(label or key)}">')

    def end(self): self.parts.append('</g>')

    def box(self, key, x, y, w, h, fill='#FFFFFF', stroke='#000000', radius=0, sw=.3):
        self.parts.append(f'<g id="{key}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.1f}"/></g>')

    def text(self, key, x, y, text, size=3.3, bold=False, anchor='start', bounds=None):
        self.parts.append(f'<g id="{key}"><text x="{x:.1f}" y="{y:.1f}" font-family="Arial" font-size="{size:.1f}" font-weight="{"bold" if bold else "normal"}" fill="#000000" text-anchor="{anchor}">{escape(text)}</text></g>')
        font = ImageFont.truetype(str(BOLD if bold else FONT), round(size*100))
        left, top, right, bottom = font.getbbox(text, anchor='ls')
        offset = 0 if anchor=='start' else (right-left)/100/(2 if anchor=='middle' else 1)
        bb=(x+left/100-offset,y+top/100,x+right/100-offset,y+bottom/100)
        if bounds:
            bx,by,bw,bh=bounds
            assert bb[0]>=bx+.8 and bb[2]<=bx+bw-.8 and bb[1]>=by+.8 and bb[3]<=by+bh-.8,(key,text,bb,bounds)
        assert bb[0]>=1 and bb[2]<=179 and bb[1]>=1 and bb[3]<=self.height-1,(key,bb)
        self.texts.append(dict(id=key,text=text,size_mm=size,bounds_mm=[round(a,1) for a in bb]))

    def lines(self, key, x, y, lines, gap=5.5, bounds=None, size=3.3, bold_first=False):
        for i,line in enumerate(lines):self.text(f'{key}-{i+1}',x,y+i*gap,line,size=size,bold=bold_first and i==0,bounds=bounds)

    def arrow(self,key,x1,y1,x2,y2):
        length=((x2-x1)**2+(y2-y1)**2)**.5
        assert length>=10
        self.arrows.append(dict(id=key,start=[x1,y1],end=[x2,y2],length_mm=length))
        self.parts.append(f'<g id="{key}"><line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#000000" stroke-width="0.3" marker-end="url(#arrow)"/></g>')

    def save(self):
        self.parts.append('</svg>')
        data='\n'.join(self.parts)
        ET.fromstring(data)
        assert '<image ' not in data and 'textLength' not in data
        path=OUT/(self.name+'.svg');path.write_text(data,encoding='utf-8')
        return dict(svg=path.name,width_mm=180,height_mm=self.height,text_elements=len(self.texts),
                    minimum_font_at_6_3_inches_pt=min(t['size_mm'] for t in self.texts)*72/25.4*(6.3*25.4/180),
                    text_bounds_checked_with='Windows Arial / Arial Bold via Pillow; 0.8 mm container inset',
                    arrows=self.arrows,svg_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def vertical():
    c=Canvas('figure_v2_variant_A',274)
    c.group('labels','Title and panel labels')
    c.text('title',8,8,'Source selection and permanently held-out evaluation',4.0,True)
    for letter,y in [('a',15.5),('b',56.5),('c',133.5),('d',200.5)]:c.text('panel-label-'+letter,8,y,letter,3.7,True)
    c.end()
    c.group('panel-a','Development regions and fixed allocations')
    a=(8,18,164,23);c.box('development',*a)
    c.lines('development-text',13,25,[
        'Old development: 24 regions × 5 images = 120',
        '3 fixed source allocations: 12 train / 4 validation / 8 unused',
        'All earlier test regions are now development data'],gap=5.5,bounds=a,bold_first=True)
    c.end()
    c.group('panel-b','Candidate pools and eight selectors')
    b=(8,59,164,59);c.box('selection',*b)
    c.text('selection-title',13,66,'36 candidates per source allocation; two pool profiles',3.7,True,bounds=b)
    c.lines('selection-details',13,72,[
        'Balanced: 12 × 3 images; imbalanced: 6 × 5 + 6 × 1 images',
        'DINOv2 RGB descriptors + source IDs + budget + seed',
        '8 selectors; candidate masks and target features excluded'],gap=5.5,bounds=b)
    c.lines('eight-policies',13,91,[
        'Random · k-center · quota random · quota k-center',
        'Permuted quota k-center · k-means++ · facility location',
        'Feature-diversity round-robin (adaptation)'],gap=5.5,bounds=b)
    c.lines('weighted-fl-supplement',13,107,[
        'Plus two skewed-only weighted FL controls: real / permuted source groups',
        'Same FL objective; row weights 1/(R × n_group); columns unweighted'],gap=5.5,bounds=b)
    c.end()
    c.group('panel-c','Two different model recipes')
    r=(8,136,164,49);c.box('recipe-container',*r)
    c.text('recipe-title',13,143,'Fit the selected images using two different model recipes',3.7,True,bounds=r)
    c.lines('full-recipe',13,150,[
        'ResNet18 U-Net-style',
        '90 fits (72 base + 18 weighted)',
        'B=12 · imbalanced pool',
        'All weights trainable; BN stats fixed',
        '224 crops / 448 inference'],gap=5.0,bounds=r,bold_first=True)
    c.lines('frozen-recipe',99,150,[
        'Frozen DINOv2 + MLP',
        '486 fits (432 base + 54 weighted)',
        'B=6/12/24 · both pools',
        'Head trained; 600 steps; LR 0.001',
        '448 inference'],gap=5.0,bounds=r,bold_first=True)
    c.text('calibration-resource',13,177,'Old validation calibrates the full recipe; development labels are outside B.',bounds=r)
    c.text('repetition-resource',13,182,'576 total fits; 3 source allocations × 3 paired fit seeds (0/1/2)',bounds=r)
    c.end()
    c.group('panel-d','Permanent panel and regional analysis')
    d=(8,203,164,50);c.box('evaluation',*d)
    c.text('evaluation-title',13,210,'Permanent evaluation panel and paired regional analysis',3.7,True,bounds=d)
    c.lines('evaluation-only',13,216,[
        '24 new regions × 3 images = 72; evaluation only',
        'No panel feedback to selection, calibration or checkpoint choice'],gap=5.5,bounds=d)
    c.lines('analysis-order',13,227,[
        '1  Within each fit and region, sum the 3 image confusion matrices',
        '2  Compute regional union-class mIoU',
        '3  Average 3 allocations × 3 paired fit seeds (= 9 fits) within each region',
        '4  Form 24 paired region differences; bootstrap regions 10,000 times'],gap=5.5,bounds=d)
    c.end()
    c.group('arrows','Forward flow only')
    c.arrow('development-to-selection',90,44,90,56)
    c.arrow('selection-to-recipes',90,121,90,133)
    c.arrow('recipes-to-evaluation',90,188,90,200)
    c.end()
    c.group('scope-notes','Interpretation boundary')
    c.lines('recipe-nonclaim',8,263,[
        'Different model recipes do not isolate encoder fine-tuning.',
        'Weighted FL is not claimed as novel; quota-versus-FL does not isolate quota rigidity.'],gap=5.0)
    c.end()
    return c.save()


def columns():
    c=Canvas('figure_v2_variant_B',175)
    c.group('labels','Title and panel labels')
    c.text('title',8,8,'A fixed selection comparison across two model recipes',4.0,True)
    for letter,x,y in [('a',8,14.5),('b',99,14.5),('c',8,120.5)]:c.text('panel-label-'+letter,x,y,letter,3.7,True)
    c.end()
    c.group('panel-a','Development and selection column')
    a=(8,17,73,88);c.box('selection-column',*a,fill='#EDF6FB',stroke='#0072B2',radius=2,sw=.4)
    c.text('development-selection-title',13,23,'Development and selection',3.7,True,bounds=a)
    c.lines('development-allocation',13,29,[
        'Old 24 regions × 5 = 120 images',
        '3 splits: 12 train / 4 val / 8 unused'],gap=5.5,bounds=a)
    c.lines('profiles',13,41,[
        '36 candidates in each pool',
        'Balanced 12 × 3; skewed 6 × 5 + 6 × 1'],gap=5.5,bounds=a)
    c.text('selection-descriptor',13,52,'DINOv2 RGB + source IDs + B + seed',bounds=a)
    c.text('policy-header',13,58,'8 base selectors; no candidate labels',bold=True,bounds=a)
    c.lines('eight-policies',13,64,[
        'Random; k-center; quota random',
        'Quota k-center; permuted quota',
        'k-means++; facility location',
        'Feature-diversity round-robin',
        '(fixed-cluster adaptation)'],gap=5.0,bounds=a)
    c.lines('weighted-fl-supplement',13,90,[
        '+ Real / permuted weighted FL',
        'Skewed only: 1/(R × n_group)',
        'Same FL; columns unweighted'],gap=5.0,bounds=a)
    c.end()
    c.group('panel-b','Full and frozen model recipes')
    b=(99,17,73,88);c.box('recipe-column',*b,fill='#FFF8EB',stroke='#E69F00',radius=2,sw=.4)
    c.text('recipe-column-title',104,23,'Two different model recipes',3.7,True,bounds=b)
    full=(104,29,63,26);c.box('full-model',*full,stroke='#E69F00',radius=1.5,sw=.4)
    c.lines('full-recipe',108,35,[
        'ResNet18 U-Net-style',
        '90 fits (72 + 18); B=12; skewed',
        'All weights train; BN stats fixed',
        '224 crops / 448 inference'],gap=5.0,bounds=full,bold_first=True)
    frozen=(104,61,63,22);c.box('frozen-model',*frozen,fill='#F3F8FC',stroke='#0072B2',radius=1.5,sw=.4)
    c.lines('frozen-recipe',108,67,[
        'Frozen DINOv2 + MLP',
        '486 fits; both pools; B=6/12/24',
        '600 steps; LR 0.001; head trained'],gap=5.0,bounds=frozen,bold_first=True)
    c.lines('shared-resources',104,89,[
        'Old val sets full recipe; labels',
        'outside B. Paired fit seeds 0/1/2',
        '(selection = init); 3 splits; 576 fits'],gap=5.5,bounds=b)
    c.end()
    c.group('panel-c','Permanent evaluation and region-level inference')
    d=(8,123,164,33);c.box('new-panel-analysis',*d,fill='#F3F8FC',stroke='#0072B2',radius=2,sw=.4)
    c.text('inference-title',13,129,'Permanent panel: 24 new regions × 3 images = 72',3.7,True,bounds=d)
    c.lines('regional-analysis',13,135,[
        'Evaluation only at 448; no feedback to selection, calibration or checkpoint choice',
        '1  Per fit / region: sum 3 image confusion matrices → regional union-class mIoU',
        '2  Average 3 allocations × 3 paired fit seeds (= 9 fits) → 24 region differences',
        '3  Bootstrap the 24 regions 10,000 times; splits and seeds are not extra regions'],gap=5.5,bounds=d)
    c.end()
    c.group('arrows','Forward arrows only')
    c.arrow('selection-to-model-recipes',84,66,96,66)
    c.arrow('recipes-to-new-panel-analysis',135.5,108,135.5,120)
    c.end()
    c.group('scope-notes','Recipe comparison boundary')
    c.lines('nonclaim',8,164,[
        'Seeds pair selection with optimization; model recipes do not isolate fine-tuning.',
        'Weighted FL is not claimed as novel; quota-versus-FL does not isolate quota rigidity.'],gap=5.5)
    c.end()
    return c.save()


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    metadata=dict(scope='Methods schematic; source design and protocol only; no results or data-plot placeholders',
        source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [ROOT/'configs/v2_design.json',ROOT/'configs/v2_extension.json',ROOT/'docs/v2_protocol.md']},
        variants=[vertical(),columns()])
    (OUT/'figure_qa.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))
