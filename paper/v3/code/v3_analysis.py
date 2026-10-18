"""Descriptive numbers for the v3 figures and text, read from the recorded run files (nothing is refitted).

Outputs paper/v3/figures/v3_numbers.json. Selection diagnostics (regions, valid pixels, atypicality) are post hoc
descriptions of the recorded selections; atypicality uses the same DINOv2 CLS descriptors the selectors saw.
"""
import json
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CUDA = ROOT / 'evidence/v2/cuda_execution'
PIX = ROOT / 'evidence/v2/pixel_budget_execution'
CACHE = ROOT / 'cache/dinov2-formal120'
OUT = ROOT / 'paper/v3/figures/v3_numbers.json'
POLICIES = ['random', 'kcenter', 'kmeanspp', 'facility_location', 'fd_roundrobin', 'region_random', 'region_kcenter',
            'permuted_region_kcenter', 'region_weighted_facility_location', 'permuted_region_weighted_facility_location']
SOURCES = ['source0', 'source1', 'source2']
SEEDS = ['0_0', '1_1', '2_2']

_desc = {}


def descriptor(i):
    if i not in _desc:
        v = np.load(CACHE / f'{i}.npz')['descriptor'].astype(np.float64).ravel()
        _desc[i] = v / np.linalg.norm(v)
    return _desc[i]


def atypicality(pool, chosen):
    """Mean cosine distance from each chosen image to the other candidates of its pool (higher = more unusual)."""
    D = np.stack([descriptor(i) for i in pool])
    dist = 1 - D @ D.T
    idx = {i: k for k, i in enumerate(pool)}
    return float(np.mean([dist[idx[c]].sum() / (len(pool) - 1) for c in chosen]))


def fit_record(path):
    r = json.loads(path.read_text(encoding='utf-8'))
    sel = r['selection']
    regs = {k: v['union_class_miou'] for k, v in r['test']['aggregate']['regions'].items()}
    return dict(score=r['test']['aggregate']['equal_region_union_miou'], regions=regs,
                selected=sel['selected_ids'], pool=sel['candidate_ids'],
                n_regions=len(set(i.split('__')[0] for i in sel['selected_ids'])),
                pixels=sel.get('selected_valid_original_pixels'),
                class_counts=sel.get('selected_original_class_counts'),
                atyp=atypicality(sel['candidate_ids'], sel['selected_ids']),
                pool_atyp=atypicality(sel['candidate_ids'], sel['candidate_ids']))


def main():
    out = {'complete': {}, 'pixel_matched': {}}
    for p in POLICIES:
        fits = [fit_record(CUDA / f'{s}_skewed5_1_12_{q}_{p}' / 'result.json') for s in SOURCES for q in SEEDS]
        out['complete'][p] = dict(
            fits=[f['score'] for f in fits],
            by_source={s: float(np.mean([f['score'] for f in fits[k * 3:(k + 1) * 3]])) for k, s in enumerate(SOURCES)},
            mean=float(np.mean([f['score'] for f in fits])),
            regions_mean=float(np.mean([f['n_regions'] for f in fits])),
            pixels_mean=float(np.mean([f['pixels'] for f in fits])),
            pixels=[f['pixels'] for f in fits],
            atyp_mean=float(np.mean([f['atyp'] for f in fits])),
            pool_atyp_mean=float(np.mean([f['pool_atyp'] for f in fits])),
            region_means={r: float(np.mean([f['regions'][r] for f in fits])) for r in fits[0]['regions']},
            class_share=(np.sum([np.asarray(f['class_counts'][1:], float) / np.sum(f['class_counts'][1:]) for f in fits], 0) / len(fits)).tolist(),
            seed0_source0=dict(selected=fits[0]['selected'], pool=fits[0]['pool']),
        )
    for p in ['kcenter', 'region_kcenter', 'permuted_region_kcenter']:
        fits = []
        for s in SOURCES:
            for q in SEEDS:
                r = json.loads((PIX / f'{s}_skewed5_1_12_{q}_{p}' / 'result.json').read_text(encoding='utf-8'))
                fits.append(dict(score=r['test']['aggregate']['equal_region_union_miou'],
                                 regions={k: v['union_class_miou'] for k, v in r['test']['aggregate']['regions'].items()},
                                 before=r['pixel_supervision'].get('available_valid_pixels_before'),
                                 after=r['pixel_supervision'].get('available_valid_pixels_after')))
        out['pixel_matched'][p] = dict(fits=[f['score'] for f in fits], mean=float(np.mean([f['score'] for f in fits])),
                                       by_source={s: float(np.mean([f['score'] for f in fits[k * 3:(k + 1) * 3]])) for k, s in enumerate(SOURCES)},
                                       before=[f['before'] for f in fits], after=[f['after'] for f in fits],
                                       region_means={r: float(np.mean([f['regions'][r] for f in fits])) for r in fits[0]['regions']})
    OUT.write_text(json.dumps(out, indent=1), encoding='utf-8')
    for p, v in out['complete'].items():
        print(f"{p:42s} mIoU {100*v['mean']:6.2f}  regions {v['regions_mean']:5.2f}  pixels {v['pixels_mean']/1e6:6.2f}M  atyp {v['atyp_mean']:.4f} (pool {v['pool_atyp_mean']:.4f})")
    for p, v in out['pixel_matched'].items():
        print(f"matched {p:34s} mIoU {100*v['mean']:6.2f}  after {set(v['after'])}  before-min {min(v['before'])}")


if __name__ == '__main__':
    main()
