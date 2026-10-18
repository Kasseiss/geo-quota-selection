"""Figure 6: what each rule actually picked (post hoc description of the 90 recorded complete-model selections).

Atypicality of a pick = its mean cosine distance (DINOv2 CLS) to the other 35 candidates of its pool; we report the mean over
the 12 picks minus the mean over the whole pool, so 0 means "as typical as an average candidate".
"""
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from scipy import stats

from v3_common import INK, MUTED, FAINT, GRID, COLOR, LABEL, SHORT, FAMILY, POLICIES, numbers, run, save

SOURCES = ['source0', 'source1', 'source2']
SEEDS = ['0_0', '1_1', '2_2']


def singleton_picks():
    out = {}
    for p in POLICIES:
        heavy, single = [], []
        for s in SOURCES:
            for q in SEEDS:
                sel = run(s, q, p)['selection']
                cnt = Counter(i.split('__')[0] for i in sel['candidate_ids'])
                picks = [i.split('__')[0] for i in sel['selected_ids']]
                single.append(sum(cnt[r] == 1 for r in picks))
                heavy.append(sum(cnt[r] == 5 for r in picks))
        out[p] = (np.mean(heavy), np.mean(single))
    return out


def main():
    N = numbers()['complete']
    pol = sorted(POLICIES, key=lambda p: N[p]['mean'])
    ex = {p: N[p]['atyp_mean'] - N[p]['pool_atyp_mean'] for p in pol}
    miou = {p: 100 * N[p]['mean'] for p in pol}
    reg = {p: N[p]['regions_mean'] for p in pol}
    sp = singleton_picks()
    norm = colors.Normalize(17.5, 21.6)
    cmap = plt.get_cmap('YlOrRd')

    fig = plt.figure(figsize=(7.5, 2.95))
    # ---------------------------------------------------------------- a: breadth vs atypicality
    ax = fig.add_axes([.06, .19, .27, .67])
    for p in pol:
        ax.scatter(reg[p], ex[p], s=70, c=[cmap(norm(miou[p]))], ec=COLOR[p], lw=1.4, zorder=3,
                   marker={'visual': 'o', 'geo': 'D', 'placebo': 's'}[FAMILY[p]])
    lab_off = {'kcenter': (6, 2), 'permuted_region_kcenter': (6, -6), 'facility_location': (-6, 5),
               'fd_roundrobin': (6, 3), 'permuted_region_weighted_facility_location': (6, -3), 'kmeanspp': (6, 2),
               'random': (-6, -7), 'region_kcenter': (-7, 0), 'region_weighted_facility_location': (-7, 0),
               'region_random': (-7, 0)}
    for p in pol:
        dx, dy = lab_off[p]
        ax.annotate(SHORT[p], (reg[p], ex[p]), xytext=(dx, dy), textcoords='offset points', fontsize=5.6,
                    ha='left' if dx > 0 else 'right', va='center', color=COLOR[p], fontweight='bold')
    ax.set_xlim(6.6, 12.6); ax.set_ylim(-.008, .066)
    ax.set_xlabel('Source regions represented (of 12)', fontsize=6.4)
    ax.set_ylabel('Excess atypicality of the picks\n(cosine distance, vs pool mean)', fontsize=6.4)
    ax.axhline(0, color=FAINT, lw=.6, ls=':')
    ax.annotate('broad and typical', (12.45, -.005), fontsize=5.6, ha='right', color=MUTED, style='italic')
    ax.annotate('narrow and unusual', (6.75, .0625), fontsize=5.6, ha='left', color=MUTED, style='italic')
    for y in (.02, .04, .06):
        ax.axhline(y, color=GRID, lw=.5, zorder=0)
    cax = ax.inset_axes([.45, .9, .32, .035])
    cb = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal')
    cb.ax.tick_params(labelsize=5.2, length=1.5, pad=1); cb.outline.set_linewidth(.4)
    cb.set_ticks([18, 19, 20, 21])
    ax.text(.45, .815, 'fill: mIoU (%)', transform=ax.transAxes, fontsize=5.2, color=MUTED, va='top')
    ax.text(.45, .75, 'circle visual · diamond geo\nsquare placebo', transform=ax.transAxes, fontsize=5.2, color=MUTED, va='top')
    fig.text(.005, .905, 'a', fontsize=9.5, fontweight='bold')
    fig.text(.025, .905, 'Two properties of a selection', fontsize=7.8, fontweight='bold')

    # ---------------------------------------------------------------- b: where the 12 picks went
    bx = fig.add_axes([.465, .19, .2, .67])
    for y, p in enumerate(pol):
        h, s = sp[p]
        bx.barh(y, h, color='#c9d1da', height=.62)
        bx.barh(y, s, left=h, color=COLOR[p], height=.62)
        bx.text(h + s + .15, y, f'{s:.1f}', fontsize=5.6, va='center', color=COLOR[p], fontweight='bold')
    bx.set_yticks(range(len(pol))); bx.set_yticklabels([LABEL[p] for p in pol], fontsize=5.8)
    bx.axvline(6, color=FAINT, lw=.5, ls=':')
    bx.set_xlim(0, 13.5); bx.set_xticks([0, 3, 6, 9, 12])
    bx.set_xlabel('Picks (of 12)', fontsize=6.4)
    bx.tick_params(axis='y', length=0)
    fig.text(.36, .905, 'b', fontsize=9.5, fontweight='bold')
    fig.text(.38, .905, 'Where the 12 picks went', fontsize=7.8, fontweight='bold')
    fig.text(.465, .005, 'grey: five-image regions  ·  colour: one-image regions (max 6)', fontsize=5.4, color=MUTED,
             va='center')

    # ---------------------------------------------------------------- c: score against atypicality
    cx = fig.add_axes([.75, .19, .235, .67])
    for p in pol:
        cx.scatter(ex[p], miou[p], s=40, c=COLOR[p], ec='white', lw=.5, zorder=3,
                   marker={'visual': 'o', 'geo': 'D', 'placebo': 's'}[FAMILY[p]])
    x = np.array([ex[p] for p in pol]); y = np.array([miou[p] for p in pol])
    rho, pv = stats.spearmanr(x, y)
    b1, b0 = np.polyfit(x, y, 1)
    xx = np.linspace(x.min() - .003, x.max() + .003, 20)
    cx.plot(xx, b0 + b1 * xx, color=FAINT, lw=.8, ls='--', zorder=1)
    cx.text(.97, .96, f'Spearman ρ = {rho:.2f}\n(10 rules, descriptive)', transform=cx.transAxes, ha='right', va='top',
            fontsize=5.6, color=INK)
    for p in ('kcenter', 'region_random', 'region_weighted_facility_location', 'region_kcenter'):
        cx.annotate(SHORT[p], (ex[p], miou[p]), xytext=(4, -6 if p == 'region_kcenter' else 3),
                    textcoords='offset points', fontsize=5.5, color=COLOR[p], fontweight='bold')
    cx.set_xlabel('Excess atypicality', fontsize=6.4)
    cx.set_ylabel('Equal-region mIoU (%)', fontsize=6.4)
    for yy in (18, 19, 20, 21):
        cx.axhline(yy, color=GRID, lw=.5, zorder=0)
    fig.text(.7, .905, 'c', fontsize=9.5, fontweight='bold')
    fig.text(.72, .905, 'Unusual picks, lower scores', fontsize=7.8, fontweight='bold')
    save(fig, 'fig6_selection_anatomy')
    print('rho', rho, 'p', pv, {SHORT[p]: (round(reg[p], 2), round(ex[p], 4), round(sp[p][1], 2)) for p in pol})


if __name__ == '__main__':
    main()
