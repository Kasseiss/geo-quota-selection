"""Shared paths, style, names and data loaders for the v3 figures.

Every plotted number is read from the recorded tables or run files; nothing is typed in by hand.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT.parents[1]
DEV_IMAGES = PROJECT / 'data/formal120/OpenEarthMap_wo_xBD'
PANEL_IMAGES = ROOT / 'v2/data/new_panel'
CACHE = ROOT / 'cache/dinov2-formal120'
CUDA = ROOT / 'evidence/v2/cuda_execution'
PIX = ROOT / 'evidence/v2/pixel_budget_execution'
OUT = ROOT / 'paper/v3/figures'
ASSETS = Path(__file__).resolve().parent / 'assets'
OUT.mkdir(parents=True, exist_ok=True)

mpl.rcParams.update({
    'font.family': 'Arial', 'font.size': 7.5, 'axes.linewidth': .6, 'axes.spines.top': False,
    'axes.spines.right': False, 'svg.fonttype': 'none', 'pdf.fonttype': 42, 'savefig.dpi': 450, 'figure.dpi': 110,
    'axes.titlesize': 8.2, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'axes.labelsize': 7.4,
    'xtick.labelsize': 6.8, 'ytick.labelsize': 6.8, 'xtick.major.width': .6, 'ytick.major.width': .6,
    'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'legend.frameon': False, 'legend.fontsize': 6.6,
})

INK, MUTED, FAINT, GRID = '#1f2328', '#5f6b7a', '#9aa4b1', '#e6e9ee'
GEO, PLACEBO, VISUAL = '#d9480f', '#7b3fbf', '#1c5fb8'
POS, NEG = '#d9480f', '#1c5fb8'

POLICIES = ['random', 'kcenter', 'kmeanspp', 'facility_location', 'fd_roundrobin', 'region_random', 'region_kcenter',
            'permuted_region_kcenter', 'region_weighted_facility_location', 'permuted_region_weighted_facility_location']
LABEL = {'random': 'Random', 'kcenter': 'Visual k-center', 'kmeanspp': 'k-means++ seeding',
         'facility_location': 'Facility location', 'fd_roundrobin': 'Feature-cluster round robin',
         'region_random': 'Geo-quota random', 'region_kcenter': 'Geo-quota k-center',
         'permuted_region_kcenter': 'Placebo-quota k-center', 'region_weighted_facility_location': 'Geo-weighted FL',
         'permuted_region_weighted_facility_location': 'Placebo-weighted FL'}
SHORT = {'random': 'Random', 'kcenter': 'K', 'kmeanspp': 'k-means++', 'facility_location': 'FL', 'fd_roundrobin': 'FD',
         'region_random': 'GeoRand', 'region_kcenter': 'GeoK', 'permuted_region_kcenter': 'PlaceboK',
         'region_weighted_facility_location': 'GeoFL', 'permuted_region_weighted_facility_location': 'PlaceboFL'}
FAMILY = {'random': 'visual', 'kcenter': 'visual', 'kmeanspp': 'visual', 'facility_location': 'visual',
          'fd_roundrobin': 'visual', 'region_random': 'geo', 'region_kcenter': 'geo',
          'region_weighted_facility_location': 'geo', 'permuted_region_kcenter': 'placebo',
          'permuted_region_weighted_facility_location': 'placebo'}
COLOR = {'random': '#8c97a6', 'kcenter': '#1c5fb8', 'kmeanspp': '#4f8fdc', 'facility_location': '#0f8a9d',
         'fd_roundrobin': '#7fb2e8', 'region_random': '#f08c00', 'region_kcenter': '#d9480f',
         'region_weighted_facility_location': '#b02a37', 'permuted_region_kcenter': '#7b3fbf',
         'permuted_region_weighted_facility_location': '#b98be0'}
SOURCE_MARK = {'source0': 'o', 'source1': 's', 'source2': '^'}

# OpenEarthMap classes 1-8 (0 = void)
CLASS_NAMES = ['Bareland', 'Rangeland', 'Developed', 'Road', 'Tree', 'Water', 'Agriculture', 'Building']
PALETTE = np.asarray([[0, 0, 0], [145, 100, 60], [220, 190, 90], [210, 90, 160], [140, 140, 140], [30, 125, 60],
                      [45, 120, 210], [190, 220, 80], [220, 65, 45]], dtype=np.uint8)

NICE = {'christchurch': 'Christchurch', 'bogota': 'Bogotá', 'chiangmai': 'Chiang Mai', 'daressalaam': 'Dar es Salaam',
        'mahe': 'Mahé', 'pointenoire': 'Pointe-Noire', 'ulaanbaatar': 'Ulaanbaatar', 'chisinau': 'Chișinău',
        'al_qurnah': 'Al Qurnah', 'buenos_aires': 'Buenos Aires', 'coxsbazar': "Cox's Bazar", 'san_tome': 'São Tomé',
        'ngaoundere': 'Ngaoundéré', 'tyrolw': 'Tyrol W', 'western': 'Western (GH)', 'kitsap': 'Kitsap',
        'rio': 'Rio', 'vegas': 'Las Vegas'}


def nice(r):
    return NICE.get(r, r.replace('_', ' ').title())


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def numbers():
    return json.loads((OUT / 'v3_numbers.json').read_text(encoding='utf-8'))


def contrast(a, b, model='resnet18_unet', pool='skewed5_1', budget=12, metric='union_class_miou'):
    for c in load_json('tables/v2/contrasts.json')['contrasts']:
        if (c['model'], c['pool'], c['budget'], c['a'], c['b']) == (model, pool, budget, a, b):
            m = c['metrics'][metric]
            regional = {x['region']: x['difference'] * 100 for x in m['regional_differences']}
            bs = m.get('bootstrap')
            # secondary contrasts store no interval; recompute with the study's paired region bootstrap and seed
            lo, hi = (bs['lower'] * 100, bs['upper'] * 100) if bs else bootstrap(regional)[1:]
            return dict(d=m['difference'] * 100, lo=lo, hi=hi, regional=regional, stored_interval=bool(bs),
                        sources={x['source_split']: x['difference'] * 100 for x in m.get('source_allocation_sensitivity', [])})
    raise KeyError((model, pool, budget, a, b))


def primary():
    m = load_json('tables/v2/primary.json')['metrics']['union_class_miou']
    return dict(d=m['difference'] * 100, lo=m['bootstrap']['lower'] * 100, hi=m['bootstrap']['upper'] * 100,
                regional={x['region']: x['difference'] * 100 for x in m['regional_differences']})


def pixel_contrasts():
    out = {}
    for c in load_json('tables/v2_pixel_budget/descriptive_analysis.json')['contrasts']:
        key = c['b']
        out[key] = {}
        for part in ('full_label_reference', 'thinned', 'paired_change'):
            o = c[part]['overall24']
            out[key][part] = dict(d=o['difference'] * 100, lo=o['bootstrap']['lower'] * 100, hi=o['bootstrap']['upper'] * 100,
                                  sources={s: c[part][s]['difference'] * 100 for s in ('source0', 'source1', 'source2')})
    return out


def bootstrap(diffs, seed=2026101805, reps=10000):
    """Same paired percentile region bootstrap as code/core.py, for contrasts computed post hoc."""
    d = np.asarray([diffs[r] for r in sorted(diffs)], float)
    rng = np.random.default_rng(seed)
    s = d[rng.integers(0, len(d), (reps, len(d)))].mean(1)
    return float(d.mean()), float(np.quantile(s, .025)), float(np.quantile(s, .975))


def dev_tile(region, name, size=120):
    im = Image.open(DEV_IMAGES / region / 'images' / f'{name}.tif').convert('RGB').resize((size, size), Image.BILINEAR)
    return np.asarray(im)


def dev_mask(region, name, size=120):
    lb = np.asarray(Image.open(DEV_IMAGES / region / 'labels' / f'{name}.tif').resize((size, size), Image.NEAREST))
    return PALETTE[np.clip(lb, 0, 8)]


def panel_tile(image_id, size=120):
    region, name = image_id.split('__')
    im = Image.open(PANEL_IMAGES / region / f'{name}_rgb.png').convert('RGB').resize((size, size), Image.BILINEAR)
    return np.asarray(im)


def framed(arr, color, width=5):
    out = arr.copy()
    c = np.array([int(color[k:k + 2], 16) for k in (1, 3, 5)], dtype=np.uint8)
    out[:width], out[-width:], out[:, :width], out[:, -width:] = c, c, c, c
    return out


def descriptors(ids):
    D = np.stack([np.load(CACHE / f'{i}.npz')['descriptor'].astype(np.float64).ravel() for i in ids])
    return D / np.linalg.norm(D, axis=1, keepdims=True)


def run(source, seeds, policy, root=CUDA):
    return json.loads((root / f'{source}_skewed5_1_12_{seeds}_{policy}' / 'result.json').read_text(encoding='utf-8'))


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight', facecolor='white', pad_inches=.03)
    plt.close(fig)
    print('saved', name)


def panel_label(ax_or_fig, x, y, letter, title, fig=None, size=8.4):
    tgt = fig if fig is not None else ax_or_fig
    tgt.text(x, y, letter, fontsize=size + 1.2, fontweight='bold', color=INK, va='bottom',
             transform=(fig.transFigure if fig is not None else ax_or_fig.transAxes))
    tgt.text(x + (.018 if fig is not None else .05), y, title, fontsize=size, fontweight='bold', color=INK, va='bottom',
             transform=(fig.transFigure if fig is not None else ax_or_fig.transAxes))
