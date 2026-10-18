"""Figure 2: where the data come from and how the three source allocations rotate the development regions.

Development locations are the supported tile-envelope centres of the earlier geography audit; panel locations average the
WGS84 sample envelopes stored in each panel image's provenance sidecar. Land outline: Natural Earth 1:110m (public domain).
"""
import json

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Wedge

from v3_common import INK, MUTED, FAINT, GRID, PROJECT, PANEL_IMAGES, ASSETS, nice, load_json, save

ROLE_COL = {'T': '#1c5fb8', 'V': '#2f9e44', 'U': '#c9d1da'}
PANEL_COL = '#d9480f'


def land(ax):
    g = json.loads((ASSETS / 'ne_110m_land.geojson').read_text(encoding='utf-8'))
    for f in g['features']:
        geom = f['geometry']
        polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
        for poly in polys:
            ax.add_patch(Polygon(np.asarray(poly[0]), closed=True, fc='#eceff3', ec='#c3cad3', lw=.35, zorder=1))


def dev_locations():
    audit = json.loads((PROJECT / 'evidence/geography_audit.json').read_text(encoding='utf-8'))
    out = {}
    for e in audit['selected_region_envelopes']:
        b = e['sampled_tile_union_envelope']
        out[e['region']] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return out


def panel_locations():
    out = {}
    for d in sorted(PANEL_IMAGES.iterdir()):
        cs = []
        for j in d.glob('*.json'):
            g = json.loads(j.read_text(encoding='utf-8'))['source_rgb'].get('geography', {})
            e = g.get('wgs84_sample_envelope')
            if e:
                cs.append(((e[0] + e[2]) / 2, (e[1] + e[3]) / 2))
        if cs:
            out[d.name] = tuple(np.mean(cs, 0))
    return out


def main():
    design = load_json('configs/v2_design.json')
    splits = design['source_splits']
    role = {}
    for s in splits:
        for k, key in (('T', 'train'), ('V', 'validation'), ('U', 'unused_development')):
            for r in s[key]:
                role.setdefault(r, {})[s['id']] = k
    dev = dev_locations()
    pan = panel_locations()
    missing = [r for r in design['new_test_regions'] if r not in pan]

    fig = plt.figure(figsize=(7.5, 5.3))
    ax = fig.add_axes([.01, .405, .98, .52])
    land(ax)
    ax.set_xlim(-182, 182); ax.set_ylim(-56, 74); ax.set_aspect('equal')
    for x in range(-150, 181, 30):
        ax.axvline(x, color=GRID, lw=.35, zorder=0)
    for y in range(-30, 61, 30):
        ax.axhline(y, color=GRID, lw=.35, zorder=0)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True); s.set_color('#c3cad3'); s.set_linewidth(.5)

    # development regions: three-wedge glyph, one wedge per source allocation
    for r, (x, y) in dev.items():
        for k, sid in enumerate(('source0', 'source1', 'source2')):
            ax.add_patch(Wedge((x, y), 3.1, 90 + k * 120, 90 + (k + 1) * 120, fc=ROLE_COL[role[r][sid]], ec='white',
                               lw=.4, zorder=4))
    for r, (x, y) in pan.items():
        ax.scatter(x, y, marker='*', s=48, c=PANEL_COL, ec='white', lw=.4, zorder=5)

    # labels with simple manual offsets to avoid collisions in dense areas
    off = {'rotterdam': (-4, 4, 'right'), 'aachen': (-4, -6, 'right'), 'vienna': (2, -6, 'left'),
           'chisinau': (4, 3, 'left'), 'bielefeld': (3, 5, 'left'), 'paris': (-4, 1, 'right'),
           'tyrolw': (-2, -8, 'right'), 'svaneti': (4, 2, 'left'), 'niamey': (4, 3, 'left'), 'accra': (3, 4, 'left'),
           'western': (-4, 5, 'right'), 'kinshasa': (1, -7, 'left'), 'pointenoire': (-4, -4, 'right'),
           'kampala': (4, 4, 'left'), 'kagera': (-4, -5, 'right'), 'daressalaam': (4, -5, 'left'),
           'zanzibar': (4, 3, 'left'), 'mahe': (4, 0, 'left'), 'dowa': (4, -3, 'left'), 'maputo': (4, -3, 'left'),
           'monrovia': (-4, -2, 'right'), 'san_tome': (-3, -3, 'right'), 'ngaoundere': (3, 4, 'left'),
           'khartoum': (4, 2, 'left'), 'al_qurnah': (4, 2, 'left'), 'dhaka': (-4, 3, 'right'),
           'coxsbazar': (-3, -5, 'right'), 'chiangmai': (4, 3, 'left'), 'baybay': (4, 0, 'left'),
           'shanghai': (-4, 3, 'right'), 'kyoto': (4, -4, 'left'), 'tokyo': (4, 3, 'left'),
           'ulaanbaatar': (4, 2, 'left'), 'melbourne': (-4, 0, 'right'), 'christchurch': (-4, -3, 'right'),
           'tonga': (4, 0, 'left'), 'chicago': (4, 2, 'left'), 'kitsap': (4, 2, 'left'), 'vegas': (-4, 0, 'right'),
           'austin': (4, -3, 'left'), 'bogota': (4, 2, 'left'), 'chiclayo': (-4, 0, 'right'),
           'abancay': (4, -3, 'left'), 'santiago': (-4, -3, 'right'), 'rio': (4, 0, 'left'),
           'buenos_aires': (4, 0, 'left'), 'rosario': (-6, 4, 'right'), 'soriano': (2, -6, 'left')}
    for src, color in ((dev, INK), (pan, PANEL_COL)):
        for r, (x, y) in src.items():
            dx, dy, ha = off.get(r, (4, 0, 'left'))
            if abs(dy) >= 4:
                ax.plot([x, x + dx * .6], [y, y + dy * .75], color=color, lw=.3, alpha=.6, zorder=3)
            ax.text(x + dx, y + dy, nice(r), fontsize=4.9, ha=ha, va='center', color=color, zorder=6,
                    bbox=dict(fc='white', ec='none', alpha=.55, pad=.2, boxstyle='round,pad=0.1'))

    fig.text(.012, .94, 'a', fontsize=9.5, fontweight='bold')
    fig.text(.032, .94, 'Forty-eight OpenEarthMap regions in two disjoint roles', fontsize=8, fontweight='bold')
    # legend row under the map
    g = fig.add_axes([.012, .335, .04, .05]); g.axis('off'); g.set_aspect('equal'); g.set_xlim(-1, 1); g.set_ylim(-1, 1)
    for k, c in enumerate(('T', 'V', 'U')):
        g.add_patch(Wedge((0, 0), .9, 90 + k * 120, 90 + (k + 1) * 120, fc=ROLE_COL[c], ec='white', lw=.6))
    fig.text(.055, .36, 'development region (5 images); wedges show its role in source0 (top), then source1 and source2 '
             '(clockwise)', fontsize=5.5, va='center', color=INK)
    for k, (c, lab) in enumerate((('T', 'training'), ('V', 'validation'), ('U', 'unused'))):
        x = .62 + k * .075
        fig.patches.append(Rectangle((x, .352), .012, .016, transform=fig.transFigure, fc=ROLE_COL[c], ec='none'))
        fig.text(x + .016, .36, lab, fontsize=5.5, va='center', color=INK)
    st = fig.add_axes([.85, .345, .02, .03]); st.axis('off'); st.set_xlim(-1, 1); st.set_ylim(-1, 1)
    st.scatter([0], [0], marker='*', s=48, c=PANEL_COL, ec='white', lw=.4)
    fig.text(.872, .36, 'panel region (3 images)', fontsize=5.5, va='center', color=PANEL_COL)

    # ------------------------------------------------------------ b: allocation matrix
    fig.text(.012, .29, 'b', fontsize=9.5, fontweight='bold')
    fig.text(.032, .29, 'Three cyclic source allocations of the 24 development regions', fontsize=8, fontweight='bold')
    bx = fig.add_axes([.11, .135, .88, .135])
    regs = design['old_development_regions']
    for i, r in enumerate(regs):
        for j, sid in enumerate(('source0', 'source1', 'source2')):
            c = role[r][sid]
            bx.add_patch(Rectangle((i, 2 - j), .92, .86, fc=ROLE_COL[c], ec='none'))
            bx.text(i + .46, 2 - j + .43, c, ha='center', va='center', fontsize=5, color='white' if c != 'U' else MUTED,
                    fontweight='bold')
    bx.set_xlim(-.1, len(regs)); bx.set_ylim(-.05, 3)
    bx.set_yticks([2.43, 1.43, .43]); bx.set_yticklabels(['source0', 'source1', 'source2'], fontsize=6)
    bx.set_xticks(np.arange(len(regs)) + .46); bx.set_xticklabels([nice(r) for r in regs], rotation=50, ha='right', fontsize=5.2)
    bx.tick_params(length=0)
    for s in bx.spines.values():
        s.set_visible(False)
    fig.text(.11, .01, 'Each allocation: 12 training regions (60 images; candidate pools of 36), 4 validation regions '
             '(20 images), 8 unused. The 24 panel regions (72 images) are never used for selection, fitting or calibration.',
             fontsize=5.4, color=MUTED)
    if missing:
        fig.text(.99, .94, 'no supported georeference: ' + ', '.join(nice(r) for r in missing), fontsize=5, ha='right',
                 color=MUTED)
    save(fig, 'fig2_geography')


if __name__ == '__main__':
    main()
