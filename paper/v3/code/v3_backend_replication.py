"""Second execution of the eight base rules: the 72 completed CPU reference fits against the same 72 GPU identities.

Adds a 'cpu_replication' block to paper/v3/figures/v3_numbers.json. Same metric, averaging and bootstrap as the study.
"""
import json
import re
from pathlib import Path

import numpy as np

from v3_common import ROOT, OUT, bootstrap

BASE = ['random', 'kcenter', 'kmeanspp', 'facility_location', 'fd_roundrobin', 'region_random', 'region_kcenter',
        'permuted_region_kcenter']


def load(path):
    r = json.loads(Path(path).read_text(encoding='utf-8'))['test']['aggregate']
    return r['equal_region_union_miou'], {k: v['union_class_miou'] for k, v in r['regions'].items()}


def main():
    cpu, gpu = {}, {}
    for f in (ROOT / 'evidence/v2/runs/resnet18_unet').glob('*/result.json'):
        m = re.match(r'(source\d)_skewed5_1_b12_s(\d)_i(\d)_(.+)', f.parent.name)
        key = (m[1], f'{m[2]}_{m[3]}', m[4])
        cpu[key] = load(f)
        gpu[key] = load(ROOT / f'evidence/v2/cuda_execution/{m[1]}_skewed5_1_12_{m[2]}_{m[3]}_{m[4]}/result.json')
    assert len(cpu) == 72 and {k[2] for k in cpu} == set(BASE)
    out = {'n_fits': len(cpu), 'policy_means': {}, 'contrasts': {}}
    same = np.array([cpu[k][0] - gpu[k][0] for k in cpu]) * 100
    out['same_identity_difference'] = dict(mean=float(same.mean()), sd=float(same.std(ddof=1)),
                                           max_abs=float(abs(same).max()))
    for p in BASE:
        ks = [k for k in cpu if k[2] == p]
        out['policy_means'][p] = dict(cpu=float(np.mean([cpu[k][0] for k in ks]) * 100),
                                      gpu=float(np.mean([gpu[k][0] for k in ks]) * 100))

    def regional(src, p):
        ks = sorted(k for k in src if k[2] == p)
        regs = src[ks[0]][1].keys()
        return {r: float(np.mean([src[k][1][r] for k in ks]) * 100) for r in regs}

    for a, b in [('region_kcenter', 'kcenter'), ('region_kcenter', 'permuted_region_kcenter'),
                 ('permuted_region_kcenter', 'kcenter'), ('region_random', 'random'), ('region_random', 'kcenter'),
                 ('region_kcenter', 'facility_location'), ('kmeanspp', 'kcenter'), ('facility_location', 'kcenter')]:
        row = {}
        for name, src in (('cpu', cpu), ('gpu', gpu)):
            ra, rb = regional(src, a), regional(src, b)
            diffs = {r: ra[r] - rb[r] for r in ra}
            d, lo, hi = bootstrap(diffs)
            fits = [src[k][0] - src[(k[0], k[1], b)][0] for k in cpu if k[2] == a]
            row[name] = dict(d=d, lo=lo, hi=hi, regions_positive=int(sum(v > 0 for v in diffs.values())),
                             fits_positive=int(sum(f > 0 for f in fits)))
        out['contrasts'][f'{a}-{b}'] = row
    nums = json.loads((OUT / 'v3_numbers.json').read_text(encoding='utf-8'))
    nums['cpu_replication'] = out
    (OUT / 'v3_numbers.json').write_text(json.dumps(nums, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
