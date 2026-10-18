"""Figure 7: when allocation matters. Frozen DINOv2 + MLP control over two pools and three budgets (486 fits), with the
complete-model cell for reference. Intervals: paired region bootstrap (stored for the main contrast, recomputed with the
study's seed for the secondary contrasts)."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Rectangle

from v3_common import ROOT, INK, MUTED, FAINT, GRID, COLOR, LABEL, contrast, save

ROWS = [('region_kcenter', 'kcenter', 'GeoK − visual K'),
        ('region_kcenter', 'permuted_region_kcenter', 'GeoK − placebo quota'),
        ('region_kcenter', 'facility_location', 'GeoK − facility location'),
        ('region_kcenter', 'fd_roundrobin', 'GeoK − feature clusters'),
        ('region_weighted_facility_location', 'facility_location', 'GeoFL − facility location'),
        ('region_weighted_facility_location', 'permuted_region_weighted_facility_location', 'GeoFL − placebo weights')]
COLS = [('dinov2_mlp128', 'balanced3', 6), ('dinov2_mlp128', 'balanced3', 12), ('dinov2_mlp128', 'balanced3', 24),
        ('dinov2_mlp128', 'skewed5_1', 6), ('dinov2_mlp128', 'skewed5_1', 12), ('dinov2_mlp128', 'skewed5_1', 24),
        ('resnet18_unet', 'skewed5_1', 12)]


def main():
    fig = plt.figure(figsize=(7.5, 4.6))
    ax = fig.add_axes([.2, .43, .78, .46])
    norm = colors.TwoSlopeNorm(0, -2.2, 2.2)
    cmap = plt.get_cmap('RdBu_r')
    for j, (model, pool, b) in enumerate(COLS):
        x = j + (.35 if model == 'resnet18_unet' else 0)
        for i, (a, bb, _) in enumerate(ROWS):
            try:
                c = contrast(a, bb, model, pool, b)
            except KeyError:
                ax.add_patch(Rectangle((x, i), .96, .94, fc='#f3f4f6', ec='none'))
                ax.text(x + .48, i + .47, 'n/a', ha='center', va='center', fontsize=5.4, color=FAINT)
                continue
            sig = c['lo'] > 0 or c['hi'] < 0
            ax.add_patch(Rectangle((x, i), .96, .94, fc=cmap(norm(c['d'])), ec=INK if sig else 'none', lw=.9))
            dark = abs(c['d']) > 1.3
            ax.text(x + .48, i + .36, f'{c["d"]:+.2f}', ha='center', va='center', fontsize=6.4,
                    color='white' if dark else INK, fontweight='bold' if sig else 'normal')
            ax.text(x + .48, i + .7, f'[{c["lo"]:+.1f}, {c["hi"]:+.1f}]', ha='center', va='center', fontsize=4.6,
                    color='white' if dark else MUTED)
    ax.set_xlim(-.05, len(COLS) + .35); ax.set_ylim(len(ROWS), -.05)
    ax.set_yticks(np.arange(len(ROWS)) + .47); ax.set_yticklabels([r[2] for r in ROWS], fontsize=6.4)
    ax.set_xticks([j + .48 + (.35 if m == 'resnet18_unet' else 0) for j, (m, _, _) in enumerate(COLS)])
    ax.set_xticklabels([f'B = {b}' for _, _, b in COLS], fontsize=6.2)
    ax.xaxis.tick_top(); ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for x0, x1, lab in ((0, 2.96, 'frozen DINOv2 + MLP · balanced pool'), (3, 5.96, 'frozen DINOv2 + MLP · skewed pool'),
                        (6.35, 7.31, 'complete model · skewed')):
        ax.plot([x0 + .05, x1 - .05], [-.62, -.62], color=INK, lw=.6, clip_on=False)
        ax.text((x0 + x1) / 2, -.72, lab, ha='center', va='bottom', fontsize=6, color=INK, fontweight='bold')
    fig.text(.005, .965, 'a', fontsize=9.5, fontweight='bold')
    fig.text(.025, .965, 'Allocation contrasts across pools, budgets and models (mIoU points)', fontsize=7.8, fontweight='bold')
    fig.text(.2, .395, 'cell: mean difference [95% paired region bootstrap] · outlined: interval excludes zero · '
             'n/a: weighted rules equal ordinary FL in balanced pools and were not fitted', fontsize=5.3, color=MUTED)

    # ---------------------------------------------------------------- b: curves relative to random
    cond = pd.read_csv(ROOT / 'tables/v2/conditions.csv')
    pol = ['kcenter', 'facility_location', 'region_random', 'region_kcenter', 'region_weighted_facility_location']
    for k, pool in enumerate(('balanced3', 'skewed5_1')):
        bx = fig.add_axes([.08 + k * .3, .075, .23, .23])
        q = cond[(cond.model == 'dinov2_mlp128') & (cond.pool == pool)].set_index(['strategy', 'budget'])
        for p in pol:
            if (p, 6) not in q.index:
                continue
            ys = [100 * (q.loc[(p, b)].equal_region_union_miou_mean - q.loc[('random', b)].equal_region_union_miou_mean)
                  for b in (6, 12, 24)]
            bx.plot([0, 1, 2], ys, color=COLOR[p], lw=1.6 if p.startswith('region') else 1.1, marker='o', ms=3.2,
                    ls='-' if p.startswith('region') else (0, (3, 1.5)))
        bx.axhline(0, color=INK, lw=.6)
        bx.axvspan(.75, 1.25, color='#fff4e6', zorder=0)
        bx.set_xticks([0, 1, 2]); bx.set_xticklabels(['6', '12', '24'])
        bx.set_xlabel('Image budget', fontsize=6.2, labelpad=1)
        bx.set_ylim(-1.6, 1.9)
        if k == 0:
            bx.set_ylabel('Difference from random\n(mIoU points)', fontsize=6.2)
        bx.set_title(f'{"balanced" if pool == "balanced3" else "skewed"} pool', fontsize=6.6, loc='left', pad=2)
        for y in (-1, 1):
            bx.axhline(y, color=GRID, lw=.5, zorder=0)
    lx = fig.add_axes([.7, .075, .28, .23]); lx.axis('off')
    for i, p in enumerate(pol):
        y = .9 - i * .17
        lx.plot([.0, .12], [y, y], color=COLOR[p], lw=1.6 if p.startswith('region') else 1.1,
                ls='-' if p.startswith('region') else (0, (3, 1.5)))
        lx.text(.16, y, LABEL[p], fontsize=6, va='center', color=INK)
    lx.text(0, .02, 'shaded: budget 12 = one image per source region', fontsize=5.4, color=MUTED, style='italic')
    lx.set_xlim(0, 1); lx.set_ylim(0, 1)
    fig.text(.005, .335, 'b', fontsize=9.5, fontweight='bold')
    fig.text(.025, .335, 'Frozen control: gains peak where the budget equals the number of source regions', fontsize=7.8,
             fontweight='bold')
    save(fig, 'fig7_budget_conditions')


if __name__ == '__main__':
    main()
