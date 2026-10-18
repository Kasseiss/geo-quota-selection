"""Figure 4: complete-model results at budget 12 in skewed pools (90 GPU fits, 24 panel regions)."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from v3_common import (INK, MUTED, FAINT, GRID, COLOR, LABEL, FAMILY, POS, NEG, SOURCE_MARK, nice, numbers, contrast,
                       primary, save)

SOURCES = ['source0', 'source1', 'source2']


def main():
    N = numbers()['complete']
    CPU = numbers()['cpu_replication']
    order = sorted(N, key=lambda p: N[p]['mean'])
    fig = plt.figure(figsize=(7.5, 6.4))

    # ------------------------------------------------------------- a: ranking
    ax = fig.add_axes([.165, .475, .375, .47])
    rng = np.random.default_rng(1)
    for y, p in enumerate(order):
        fits = np.asarray(N[p]['fits']) * 100
        for k, s in enumerate(SOURCES):
            v = fits[k * 3:(k + 1) * 3]
            ax.scatter(v, y + rng.uniform(-.17, .17, 3), s=9, marker=SOURCE_MARK[s], fc='white', ec=COLOR[p], lw=.6, zorder=3)
        m = N[p]['mean'] * 100
        sd = np.std(fits, ddof=1)
        ax.plot([m - sd, m + sd], [y, y], color=COLOR[p], lw=1.4, alpha=.45, zorder=2, solid_capstyle='round')
        ax.scatter([m], [y], s=46, marker='D', c=COLOR[p], ec=INK, lw=.5, zorder=4)
        if p in CPU['policy_means']:
            ax.scatter([CPU['policy_means'][p]['cpu']], [y + .3], s=26, marker='*', c=INK, lw=0, zorder=5)
        ax.text(26.3, y, f'{m:.2f}', fontsize=6.2, va='center', ha='right', color=INK)
        ax.text(27.3, y, f'{N[p]["regions_mean"]:.1f}', fontsize=6.2, va='center', ha='left',
                color=INK if N[p]['regions_mean'] > 11 else MUTED, fontweight='bold' if N[p]['regions_mean'] > 11 else 'normal')
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([LABEL[p] for p in order], fontsize=6.6)
    for t, p in zip(ax.get_yticklabels(), order):
        t.set_color({'geo': '#a83a0c', 'placebo': '#5f2f95', 'visual': '#1f3d66'}[FAMILY[p]])
    ax.set_xlim(12.5, 28.6); ax.set_ylim(-.7, len(order) - .3)
    ax.set_xticks([14, 16, 18, 20, 22, 24])
    ax.spines['bottom'].set_bounds(13, 25)
    ax.set_xlabel('Equal-region union-class mIoU (%)')
    for x in range(14, 25, 2):
        ax.axvline(x, color=GRID, lw=.5, zorder=0)
    ax.text(26.3, len(order) - .25, 'mean', fontsize=5.8, ha='right', va='bottom', color=MUTED)
    ax.text(27.3, len(order) - .25, 'regions', fontsize=5.8, ha='left', va='bottom', color=MUTED)
    ax.tick_params(axis='y', length=0)
    fig.text(.01, .965, 'a', fontsize=9.5, fontweight='bold')
    fig.text(.03, .965, 'Ten selection rules, 12 images, trainable ResNet18 U-Net', fontsize=8, fontweight='bold')
    hs = [Line2D([], [], marker=SOURCE_MARK[s], ls='', mfc='white', mec=INK, mew=.6, ms=3.5, label=s) for s in SOURCES]
    hs += [Line2D([], [], marker='D', ls='', mfc=FAINT, mec=INK, mew=.5, ms=4.5, label='mean of 9 GPU fits'),
           Line2D([], [], marker='*', ls='', mfc=INK, mec=INK, ms=5, label='CPU re-execution mean'),
           Line2D([], [], color=FAINT, lw=1.4, label='± fit SD')]
    fig.legend(handles=hs, loc='lower left', fontsize=5.6, ncol=6, handletextpad=.3, columnspacing=1.0, bbox_to_anchor=(.03, .375), frameon=False)
    fig.text(.03, .352, 'label colour: blue = visual descriptors only · orange = real source regions · purple = '
             'size-matched placebo groups;\n"regions" = mean number of the 12 source regions represented among the 12 picks',
             fontsize=5.4, color=MUTED, linespacing=1.35, va='bottom')

    # ------------------------------------------------------------- b: contrast ladder
    bx = fig.add_axes([.715, .475, .175, .47])
    specs = [('region_kcenter', 'kcenter', 'Geo-quota k-center\n− visual k-center', 'main'),
             ('region_kcenter', 'permuted_region_kcenter', 'Geo-quota k-center\n− placebo quota', ''),
             ('region_weighted_facility_location', 'facility_location', 'Geo-weighted FL\n− facility location', ''),
             ('region_weighted_facility_location', 'permuted_region_weighted_facility_location', 'Geo-weighted FL\n− placebo weights', '')]
    for y, (a, b, lab, tag) in enumerate(specs[::-1]):
        c = contrast(a, b)
        col = COLOR[a]
        bx.plot([c['lo'], c['hi']], [y, y], color=col, lw=2.2, solid_capstyle='round', alpha=.85)
        bx.scatter([c['d']], [y], s=52, marker='D', c='white', ec=col, lw=1.4, zorder=3)
        rep = CPU['contrasts'].get(f'{a}-{b}')
        if rep:
            r = rep['cpu']
            bx.plot([r['lo'], r['hi']], [y - .2, y - .2], color=INK, lw=.9, alpha=.7)
            bx.scatter([r['d']], [y - .2], s=30, marker='*', c=INK, lw=0, zorder=3)
        for s in SOURCES:
            bx.scatter([c['sources'][s]], [y + .26], s=10, marker=SOURCE_MARK[s], fc=FAINT, ec='none', zorder=2)
        reg = sum(v > 0 for v in c['regional'].values())
        f = np.asarray(N[a]['fits']) - np.asarray(N[b]['fits'])
        bx.text(4.35, y, f'{c["d"]:+.2f}\n[{c["lo"]:+.2f}, {c["hi"]:+.2f}]', fontsize=5.8, va='center', ha='left', color=INK,
                linespacing=1.25)
        bx.text(4.35, y - .37, f'{reg}/24 regions · {int((f > 0).sum())}/9 fits', fontsize=5.1, va='center', ha='left',
                color=MUTED)
        bx.text(-.04, (y + .75) / (len(specs) + .4), lab, fontsize=6.1, va='center', ha='right', color=INK, linespacing=1.2, transform=bx.transAxes)
    bx.axvline(0, color=INK, lw=.6)
    bx.set_xlim(-1.5, 4.2); bx.set_ylim(-.75, len(specs) - .35)
    bx.set_yticks([]); bx.spines['left'].set_visible(False)
    bx.set_xlabel('Difference (mIoU points)')
    for x in (-1, 1, 2, 3, 4):
        bx.axvline(x, color=GRID, lw=.5, zorder=0)
    fig.text(.6, .965, 'b', fontsize=9.5, fontweight='bold')
    fig.text(.62, .965, 'Paired contrasts (complete model)', fontsize=8, fontweight='bold')
    bx.text(-.6, -.2, 'bar: 95% paired region bootstrap · grey: source0/1/2 means · black star: CPU re-execution', transform=bx.transAxes, fontsize=5.2,
            color=MUTED)

    # ------------------------------------------------------------- c: 24 regions
    cx = fig.add_axes([.07, .095, .915, .2])
    prim = primary()
    c = contrast('region_kcenter', 'kcenter')
    srcs = {}
    for s in SOURCES:
        srcs[s] = {}
    # source-level regional values are recomputed from the recorded fits for display only
    import json
    from v3_common import run
    for s in SOURCES:
        acc = {}
        for q in ('0_0', '1_1', '2_2'):
            ra = run(s, q, 'region_kcenter')['test']['aggregate']['regions']
            rb = run(s, q, 'kcenter')['test']['aggregate']['regions']
            for r in ra:
                acc.setdefault(r, []).append(ra[r]['union_class_miou'] - rb[r]['union_class_miou'])
        srcs[s] = {r: 100 * np.mean(v) for r, v in acc.items()}
    regs = sorted(prim['regional'], key=lambda r: -prim['regional'][r])
    for i, r in enumerate(regs):
        v = prim['regional'][r]
        cx.bar(i, v, width=.62, color=POS if v > 0 else NEG, alpha=.9, zorder=3)
        for s in SOURCES:
            cx.scatter(i + {'source0': -.22, 'source1': 0, 'source2': .22}[s], srcs[s][r], s=7, marker=SOURCE_MARK[s],
                       fc='white', ec=MUTED, lw=.5, zorder=4)
    assert abs(np.mean([prim['regional'][r] for r in regs]) - prim['d']) < 1e-9
    cx.axhline(0, color=INK, lw=.6)
    cx.axhspan(prim['lo'], prim['hi'], color=POS, alpha=.10, zorder=0, lw=0)
    cx.axhline(prim['d'], color=POS, lw=.8, ls='--', zorder=1)
    cx.text(len(regs) - .4, prim['d'] + .25, f'mean {prim["d"]:+.2f} [{prim["lo"]:+.2f}, {prim["hi"]:+.2f}]', fontsize=5.8,
            ha='right', va='bottom', color='#a83a0c')
    cx.set_xticks(range(len(regs)))
    cx.set_xticklabels([nice(r) for r in regs], rotation=45, ha='right', fontsize=5.9)
    cx.set_xlim(-.6, len(regs) - .4)
    cx.set_ylabel('Geo-quota k-center −\nvisual k-center (points)', fontsize=6.4)
    cx.tick_params(axis='x', length=0)
    for y in (-5, 5, 10):
        cx.axhline(y, color=GRID, lw=.5, zorder=0)
    fig.text(.01, .315, 'c', fontsize=9.5, fontweight='bold')
    fig.text(.03, .315, f'The main contrast region by region: higher in {sum(prim["regional"][r] > 0 for r in regs)} of 24 '
             'unseen regions', fontsize=8, fontweight='bold')
    fig.text(.985, -.005, 'bars: nine-fit regional mean · open circle / square / triangle: source0 / source1 / source2 (three '
             'fits each) · band: 95% region bootstrap', fontsize=5.2, color=MUTED, ha='right')
    save(fig, 'fig4_main_results')


if __name__ == '__main__':
    main()
