"""Figure 1: the study in one picture, drawn from recorded data.

Thumbnails are the real candidate and panel tiles, the feature map is a PCA of the cached DINOv2 CLS descriptors the
selectors used, the three selections are the recorded source0 / seed (0, 0) runs of the complete-model condition, and the
bars in panel d are the recorded nine-fit regional differences of the main contrast.
"""
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

from v3_common import (INK, MUTED, FAINT, COLOR, PALETTE, CLASS_NAMES, POS, NEG, nice, dev_tile, dev_mask, panel_tile,
                       framed, descriptors, run, primary, load_json, save, PANEL_IMAGES)

RED = '#b42318'
REGION_COL = {'accra': '#e8590c', 'bogota': '#2f9e44', 'chicago': '#d6336c', 'pointenoire': '#1971c2',
              'santiago': '#9c36b5', 'ulaanbaatar': '#e0a800', 'daressalaam': '#0c8599', 'mahe': '#74b816',
              'maputo': '#f783ac', 'niamey': '#845ef7', 'rio': '#5c940d', 'vienna': '#495057'}


def split_id(i):
    return i.split('__')


def farrow(fig, p, q, rad=0., color=INK, lw=1.2, ms=10, z=20):
    fig.patches.append(FancyArrowPatch(p, q, transform=fig.transFigure, arrowstyle='-|>', mutation_scale=ms, lw=lw,
                                       color=color, connectionstyle=f'arc3,rad={rad}', zorder=z))


def atyp(pool_desc, idx):
    dist = 1 - pool_desc @ pool_desc.T
    return float(np.mean(dist[idx].sum(1) / (len(pool_desc) - 1)))


def main():
    runs = {s: run('source0', '0_0', s) for s in ('kcenter', 'region_kcenter', 'permuted_region_kcenter')}
    pool = runs['kcenter']['selection']['candidate_ids']
    assert all(r['selection']['candidate_ids'] == pool for r in runs.values())
    regions = sorted({split_id(i)[0] for i in pool})
    counts = Counter(split_id(i)[0] for i in pool)
    order_regions = sorted(regions, key=lambda r: (-counts[r], r == 'daressalaam', r))

    D = descriptors(pool)
    centred = D - D.mean(0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    xy = centred @ vt[:2].T
    pos = {i: xy[k] for k, i in enumerate(pool)}
    index = {i: k for k, i in enumerate(pool)}

    W, H = 7.5, 9.0
    fig = plt.figure(figsize=(W, H))
    asp = W / H
    split = .468
    fig.patches.append(Rectangle((0, split + .004), 1, 1 - split, transform=fig.transFigure, fc='#eef3fa', ec='none', zorder=-5))
    fig.patches.append(Rectangle((0, 0), 1, split - .004, transform=fig.transFigure, fc='#eef6f0', ec='none', zorder=-5))
    fig.lines.append(plt.Line2D([0, 1], [split, split], transform=fig.transFigure, color=RED, lw=1.3, ls=(0, (6, 3))))
    fig.text(.985, .996, 'SELECTION SIDE  ·  sees RGB descriptors and source-region IDs, never masks', fontsize=5.9,
             color='#33557f', fontweight='bold', va='top', ha='right')
    fig.text(.015, .006, 'TRAINING AND EVALUATION SIDE  ·  masks of the 12 chosen images only; panel masks used for scoring only',
             fontsize=5.9, color='#2b6340', fontweight='bold', va='bottom')
    fig.text(.985, split, ' mask firewall ', fontsize=6.4, color='white', fontweight='bold', ha='right', va='center',
             bbox=dict(fc=RED, ec='none', boxstyle='round,pad=0.3'), zorder=30)

    # ------------------------------------------------------------------ a: pool in feature space
    ax = fig.add_axes([.035, .64, .40, .315])
    fig.text(.035, .962, 'a', fontsize=9.5, fontweight='bold')
    fig.text(.055, .962, 'Skewed 36-image candidate pool in DINOv2 space', fontsize=8, fontweight='bold')
    for i in pool:
        r, n = split_id(i)
        ax.add_artist(AnnotationBbox(OffsetImage(framed(dev_tile(r, n, 72), REGION_COL[r], 6), zoom=.205), pos[i],
                                     frameon=False, pad=0))
    pad = .06
    ax.set_xlim(xy[:, 0].min() - pad, xy[:, 0].max() + pad)
    ax.set_ylim(xy[:, 1].min() - pad, xy[:, 1].max() + pad)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_facecolor('white')
    for s in ax.spines.values():
        s.set_visible(True); s.set_color('#c8d3e0')
    ax.set_xlabel('descriptor PC 1', fontsize=6.2, color=MUTED, labelpad=2)
    ax.set_ylabel('descriptor PC 2', fontsize=6.2, color=MUTED, labelpad=2)
    lg = fig.add_axes([.035, .505, .40, .11]); lg.axis('off'); lg.set_xlim(0, 6); lg.set_ylim(-.35, 2.05)
    for k, r in enumerate(order_regions):
        x, y = k % 6, 1.42 - (k // 6) * 1.0
        for j in range(counts[r]):
            lg.add_patch(Rectangle((x + .04 + j * .1, y - .16), .08, .3, fc=REGION_COL[r], ec='white', lw=.4))
        lg.text(x + .04, y + .24, nice(r), fontsize=5.5, color=INK, va='bottom')
    lg.text(.04, -.33, 'Squares = candidates per source region: six regions offer five images, six offer only one',
            fontsize=5.5, color=MUTED, style='italic')

    # ------------------------------------------------------------------ b: three rules on the same pool
    spec = [('kcenter', 'Visual k-center', COLOR['kcenter']),
            ('region_kcenter', 'Geo-quota k-center', COLOR['region_kcenter']),
            ('permuted_region_kcenter', 'Placebo-quota k-center', COLOR['permuted_region_kcenter'])]
    fig.text(.475, .962, 'b', fontsize=9.5, fontweight='bold')
    fig.text(.495, .962, 'Same pool, three rules, 12 picks each (recorded runs)', fontsize=8, fontweight='bold')
    for k, (s, lab, col) in enumerate(spec):
        x0 = .478 + k * .172
        sax = fig.add_axes([x0, .715, .155, .222])
        sel = runs[s]['selection']['selected_ids']
        sax.scatter(xy[:, 0], xy[:, 1], s=8, c=[REGION_COL[split_id(i)[0]] for i in pool], alpha=.3, lw=0)
        path = np.array([pos[i] for i in sel])
        sax.plot(path[:, 0], path[:, 1], color=col, lw=.6, alpha=.6, zorder=2)
        sax.scatter(path[:, 0], path[:, 1], s=24, c=[REGION_COL[split_id(i)[0]] for i in sel], ec=INK, lw=.7, zorder=3)
        for o, (px, py) in enumerate(path[:3], 1):
            sax.annotate(str(o), (px, py), xytext=(0, 4.5), textcoords='offset points', fontsize=5, ha='center',
                         va='bottom', color=INK, fontweight='bold', zorder=4)
        sax.set_xlim(*ax.get_xlim()); sax.set_ylim(*ax.get_ylim()); sax.set_xticks([]); sax.set_yticks([])
        for sp in sax.spines.values():
            sp.set_visible(True); sp.set_color(col); sp.set_linewidth(1.3)
        sax.set_facecolor('white')
        sax.set_title(lab, fontsize=6.9, color=col, fontweight='bold', pad=3, loc='center')
        hit = Counter(split_id(i)[0] for i in sel)
        hax = fig.add_axes([x0, .565, .155, .105])
        hax.bar(range(12), [hit.get(r, 0) for r in order_regions], color=[REGION_COL[r] for r in order_regions], width=.75)
        hax.axvline(5.5, color=FAINT, lw=.5, ls=':')
        hax.set_ylim(0, 5.4); hax.set_xticks([]); hax.set_yticks([0, 2, 4]); hax.tick_params(labelsize=5.2, length=2)
        hax.set_facecolor('none')
        single = sum(hit.get(r, 0) > 0 for r in order_regions[6:])
        hax.text(.5, .99, f'{len(hit)}/12 regions  ·  {single}/6 singletons', transform=hax.transAxes,
                 ha='center', va='top', fontsize=5.3, color=INK)
        if k == 0:
            hax.set_ylabel('picks', fontsize=5.6, labelpad=1)
        hax.text(2.5, -.55, '5-image regions', fontsize=4.9, color=MUTED, ha='center', va='top')
        hax.text(8.5, -.55, '1-image regions', fontsize=4.9, color=MUTED, ha='center', va='top')
    farrow(fig, (.44, .80), (.474, .80))

    # ------------------------------------------------------------------ c: chosen list crosses the firewall
    fig.text(.035, .432, 'c', fontsize=9.5, fontweight='bold')
    fig.text(.055, .432, 'Only the chosen list crosses the firewall', fontsize=8, fontweight='bold')
    sel = runs['region_kcenter']['selection']['selected_ids']
    w = .05; h = w * asp
    for k, i in enumerate(sel):
        r, n = split_id(i)
        cx, ry = .07 + (k % 6) * (w + .005), k // 6
        a1 = fig.add_axes([cx, .355 - ry * (h + .005), w, h]); a1.imshow(framed(dev_tile(r, n), REGION_COL[r], 7)); a1.axis('off')
        a2 = fig.add_axes([cx, .24 - ry * (h + .005), w, h]); a2.imshow(dev_mask(r, n)); a2.axis('off')
    fig.text(.055, .355 - h / 2 + .022, 'RGB', rotation=90, fontsize=6, color=INK, ha='center', va='center')
    fig.text(.055, .24 - h / 2 + .022, 'masks released', rotation=90, fontsize=6, color=INK, ha='center', va='center')
    fig.text(.07, .162, 'Geo-quota k-center list: one image from each of the 12 source regions', fontsize=5.6,
             color=MUTED, style='italic')
    for k, nm in enumerate(CLASS_NAMES):
        x, y = .07 + (k % 4) * .084, .132 - (k // 4) * .022
        fig.patches.append(Rectangle((x, y), .011, .011, transform=fig.transFigure, fc=PALETTE[k + 1] / 255, ec='none'))
        fig.text(x + .014, y + .0055, nm, fontsize=5.3, va='center', color=INK)
    fig.text(.07, .072, 'Budget: 12 whole images per fit. Calibration (24 images) and source validation (20 images)\n'
             'use shared development labels outside this budget.', fontsize=5.2, color=MUTED, linespacing=1.35)

    # trainable U-Net glyph
    ux = fig.add_axes([.415, .10, .205, .33]); ux.axis('off'); ux.set_xlim(0, 1); ux.set_ylim(0, 1)
    enc = [(.04, .62, .30), (.14, .52, .22), (.24, .44, .15), (.34, .38, .10)]
    dec = [(.56, .38, .10), (.66, .44, .15), (.76, .52, .22), (.86, .62, .30)]
    for (x, y, hh) in enc:
        ux.add_patch(FancyBboxPatch((x, y), .075, hh, boxstyle='round,pad=0.005,rounding_size=.01', fc='#cfe3f3', ec='#2b6ea3', lw=.8))
    ux.add_patch(FancyBboxPatch((.445, .34), .075, .07, boxstyle='round,pad=0.005,rounding_size=.01', fc='#b7d3ec', ec='#2b6ea3', lw=.8))
    for (x, y, hh) in dec:
        ux.add_patch(FancyBboxPatch((x, y), .075, hh, boxstyle='round,pad=0.005,rounding_size=.01', fc='#e3f1e7', ec='#2f8f5b', lw=.8))
    for (xe, ye, he), (xd, yd, hd) in zip(enc, dec[::-1]):
        ux.annotate('', (xd, ye + he - .02), (xe + .075, ye + he - .02),
                    arrowprops=dict(arrowstyle='-|>', color='#7a8794', lw=.6, ls=(0, (2, 1.5)), mutation_scale=6))
    ux.text(.19, .955, 'ResNet18 encoder', ha='center', fontsize=5.8, color='#1d4f78', fontweight='bold')
    ux.text(.82, .955, 'U-Net-style decoder', ha='center', fontsize=5.8, color='#1e5e3b', fontweight='bold')
    ux.text(.5, .27, 'all 12.46 M parameters trained\n224-px crops, flips, quarter rotations', ha='center', va='top',
            fontsize=5.4, color=INK, linespacing=1.35)
    ux.text(.5, .12, 'control: frozen DINOv2 patch features\n+ 128-unit MLP head (budgets 6, 12, 24)', ha='center',
            va='top', fontsize=5.2, color=MUTED, style='italic', linespacing=1.35,
            bbox=dict(fc='white', ec='#c7ced6', boxstyle='round,pad=0.35', lw=.6))
    ux.text(.5, .87, 'skip connections', ha='center', fontsize=5, color=MUTED, style='italic')
    farrow(fig, (.402, .30), (.425, .30), ms=9)

    # firewall crossing
    farrow(fig, (.66, .53), (.36, .414), rad=.2, color=COLOR['region_kcenter'], lw=1.5, ms=12)
    fig.text(.56, .49, 'list fixed  →  masks released', fontsize=6, color=COLOR['region_kcenter'], fontweight='bold',
             ha='center', bbox=dict(fc='white', ec=COLOR['region_kcenter'], boxstyle='round,pad=0.25', lw=.8), zorder=31)

    # ------------------------------------------------------------------ d: 24 unseen panel regions
    fig.text(.645, .432, 'd', fontsize=9.5, fontweight='bold')
    fig.text(.665, .432, 'Scored in 24 regions never used for fitting', fontsize=8, fontweight='bold')
    prim = primary()
    manifest = load_json('configs/v2_design.json')['new_test_regions']
    tw = .052; th = tw * asp
    ids = {}
    for p in sorted(PANEL_IMAGES.iterdir()):
        if p.is_dir():
            ids[p.name] = sorted(x.name.replace('_rgb.png', '') for x in p.glob('*_rgb.png'))[0]
    lim = max(abs(v) for v in prim['regional'].values())
    for k, r in enumerate(manifest):
        cx = .648 + (k % 6) * (tw + .005)
        cy = .325 - (k // 6) * (th + .037)
        ta = fig.add_axes([cx, cy, tw, th]); ta.imshow(panel_tile(f'{r}__{ids[r]}', 110)); ta.axis('off')
        fig.text(cx + tw / 2, cy - .002, nice(r), fontsize=4.6, ha='center', va='top', color=INK)
        dv = prim['regional'][r]
        ba = fig.add_axes([cx, cy - .029, tw, .013]); ba.set_xlim(-lim * 1.05, lim * 1.05); ba.set_ylim(0, 1); ba.axis('off')
        ba.axvline(0, color=MUTED, lw=.5)
        ba.add_patch(Rectangle((min(0, dv), .1), abs(dv), .8, fc=POS if dv > 0 else NEG, ec='none'))
        ba.text(lim * 1.05 if dv <= 0 else -lim * 1.05, .5, f'{dv:+.1f}', fontsize=4.4, va='center',
                ha='right' if dv <= 0 else 'left', color=MUTED)
    npos = sum(v > 0 for v in prim['regional'].values())
    fig.text(.815, .398, f'Geo-quota k-center − visual k-center: {prim["d"]:+.2f} mIoU points\n95% region bootstrap '
             f'[{prim["lo"]:+.2f}, {prim["hi"]:+.2f}]  ·  higher in {npos} of 24 regions', fontsize=5.5, linespacing=1.4,
             ha='center', va='center', color=INK, bbox=dict(fc='white', ec='#9aa3ad', boxstyle='round,pad=0.35', lw=.7))
    fig.text(.815, .03, 'bars under tiles: regional difference  ·  orange = quota better, blue = k-center better',
             fontsize=4.9, ha='center', color=MUTED, style='italic')
    farrow(fig, (.615, .25), (.643, .25), ms=9)
    save(fig, 'fig1_overview')


if __name__ == '__main__':
    main()
