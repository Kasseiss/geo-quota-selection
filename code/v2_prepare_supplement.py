"""Prepare publication-facing supplement from the preserved working draft."""
from pathlib import Path
import json
import re
from v2_compose_manuscript import ROOT, bind


def main():
    source = json.loads((ROOT / 'paper/v2_working/supplement_active_source.json').read_text(encoding='utf-8'))
    source['title'] = 'Supplementary material for Geographic allocation and visual coverage for data efficient land cover segmentation'
    removed = [s for s in source['sections'] if s['title'].startswith('S10.')]
    (ROOT / 'docs/v2_supplement_source_records.json').write_text(
        json.dumps({'purpose': 'Source identity records retained outside publication prose', 'records': removed},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    source['sections'] = [s for s in source['sections'] if not s['title'].startswith('S10.')]
    renumber = {'S8': 'S7', 'S9': 'S8', 'S10': 'S9', 'S11': 'S10',
                **{'S13' + c: 'S11' + c for c in 'abcdefg'}}
    def prose(text):
        text = text.replace('A user-directed backend amendment followed earlier panel-score exposure.',
                            'The backend amendment followed initial panel evaluation.')
        text = text.replace('up to 16 retries', 'up to 16 crop proposals')
        text = text.replace('16-retry rule', '16-proposal rule')
        text = text.replace('Tables S10-S11', 'Tables S9 and S10')
        text = text.replace('Tables S13a-S13g', 'Tables S11a–S11g')
        text = text.replace(' Qualitative examples from this checkpoint are identified as CPU-reference predictions.', '')
        text = re.sub(r'Table (S13[a-g]|S8|S9|S10|S11)\b',
                      lambda m: 'Table ' + renumber[m[1]], text)
        return text
    def blocks(items):
        for b in items:
            if b['type'] == 'paragraph': b['text'] = prose(b['text'])
            elif b['type'] == 'subsection': blocks(b['blocks'])
            elif b['type'] == 'figure':
                number = re.search(r'\d+', b['id']).group()
                b['caption'] = 'Figure S' + number + '. ' + prose(b['caption'])
            elif b['type'] == 'table':
                b['id'] = renumber.get(b['id'], b['id'])
                cap = prose(b['caption'])
                cap = cap.replace('dinov2_mlp128', 'frozen DINOv2 head').replace('resnet18_unet', 'complete spatial model')
                cap = cap.replace('balanced3', 'balanced pool').replace('skewed5_1', 'skewed pool')
                b['caption'] = 'Table ' + b['id'] + '. ' + cap
                b['notes'] = [prose(t) for t in b.get('notes', [])]
                b['rows'] = [[re.sub(r'(?<!\w)-(?=\d)', '−', cell) if isinstance(cell, str) else cell
                              for cell in row] for row in b['rows']]
    for section in source['sections'] + source['back_matter']: blocks(section['blocks'])
    source = bind(source)
    (ROOT / 'paper/v2/supplementary_source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source': 'paper/v2/supplementary_source.json', 'table_count': 17}))


if __name__ == '__main__': main()
