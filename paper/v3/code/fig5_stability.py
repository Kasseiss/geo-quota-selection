"""Figure 5: equal available labels (2.30 M processed pixels per fit) as a near-null perturbation of the complete model."""
import numpy as np
import matplotlib.pyplot as plt

from v3_common import INK, MUTED, FAINT, GRID, COLOR, LABEL, numbers, pixel_contrasts, bootstrap, save

POL = ['kcenter', 'region_kcenter', 'permuted_region_kcenter']


def main():
    N = numbers()
    F, M = N['complete'], N['pixel_matched']
    pc = pixel_contrasts()
    fig = plt.figure(figsize=(7.5, 2.9))

    # ---------------------------------------------------------------- a: how much was removed
    ax = fig.add_axes([.065, .2, .22, .66])
    rng = np.random.default_rng(4)
    for k, p in enumerate(POL):
        before = np.asarray(M[p]['before']) / 1e6
        ax.scatter(k + rng.uniform(-.13, .13, len(before)), before, s=13, c=COLOR[p], ec='white', lw=.4, zorder=3)
        removed = 100 * (1 - 2.3 / before)
        ax.text(k, 2.418, f'{removed.min():.1f}–{removed.max():.1f}%', fontsize=5.4, ha='center', va='bottom', color=INK)
    ax.axhline(2.3, color='#b42318', lw=.9, ls='--')
    ax.text(2.45, 2.301, '2.30 M kept', fontsize=5.6, color='#b42318', ha='right', va='bottom')
    ax.text(-.45, 2.429, 'labels hidden:', fontsize=5.4, color=MUTED, va='bottom')
    ax.set_xticks(range(3)); ax.set_xticklabels(['Visual\nk-center', 'Geo-quota\nk-center', 'Placebo\nquota'], fontsize=6.2)
    ax.set_ylim(2.28, 2.445); ax.set_xlim(-.5, 2.5)
    ax.set_ylabel('Valid processed labels in the\n12 selected images (millions)', fontsize=6.4)
    for y in (2.32, 2.36, 2.40):
        ax.axhline(y, color=GRID, lw=.5, zorder=0)
    fig.text(.005, .955, 'a', fontsize=9.5, fontweight='bold')
    fig.text(.025, .955, 'The selections hardly differ in labels', fontsize=7.8, fontweight='bold')

    # ---------------------------------------------------------------- b: absolute means, full -> thinned
    bx = fig.add_axes([.375, .2, .22, .66])
    for p in POL:
        f, m = np.asarray(F[p]['fits']) * 100, np.asarray(M[p]['fits']) * 100
        for a, b in zip(f, m):
            bx.plot([0, 1], [a, b], color=COLOR[p], lw=.4, alpha=.28)
        bx.plot([0, 1], [f.mean(), m.mean()], color=COLOR[p], lw=2, marker='o', ms=4.5, mec='white', mew=.6, zorder=4)
        bx.text(1.06, m.mean(), f'{m.mean():.2f}', fontsize=5.8, va='center', color=COLOR[p], fontweight='bold')
        bx.text(-.06, f.mean(), f'{f.mean():.2f}', fontsize=5.8, va='center', ha='right', color=COLOR[p], fontweight='bold')
    bx.set_xticks([0, 1]); bx.set_xticklabels(['all labels', '2.30 M labels'], fontsize=6.3)
    bx.set_xlim(-.35, 1.35)
    bx.set_ylabel('Equal-region mIoU (%)', fontsize=6.4)
    fig.text(.33, .955, 'b', fontsize=9.5, fontweight='bold')
    fig.text(.35, .955, 'Policy means (thin lines: the nine fits)', fontsize=7.8, fontweight='bold')

    # ---------------------------------------------------------------- c: contrasts before and after
    cx = fig.add_axes([.735, .2, .25, .66])
    rows = [('kcenter', 'Geo-quota − visual\nk-center', COLOR['region_kcenter']),
            ('permuted_region_kcenter', 'Geo-quota − placebo\nquota', COLOR['permuted_region_kcenter'])]
    for k, (key, lab, col) in enumerate(rows):
        y0 = 1 - k
        for j, (part, ls, mk) in enumerate((('full_label_reference', '-', 'D'), ('thinned', '-', 'o'))):
            c = pc[key][part]
            y = y0 + (.16 if j == 0 else -.16)
            cx.plot([c['lo'], c['hi']], [y, y], color=col, lw=2 if j == 0 else 2, alpha=.45 if j == 0 else .95,
                    solid_capstyle='round')
            cx.scatter([c['d']], [y], marker=mk, s=30, c='white' if j == 0 else col, ec=col, lw=1.1, zorder=3)
            cx.text(3.05, y, f'{c["d"]:+.2f}', fontsize=5.8, va='center', color=INK)
        ch = pc[key]['paired_change']
        cx.text(3.05, y0 - .43, f'change {ch["d"]:+.2f} [{ch["lo"]:+.2f}, {ch["hi"]:+.2f}]', fontsize=5.2,
                va='center', color=MUTED)
        cx.text(-.03, y0, lab, transform=cx.get_yaxis_transform(), fontsize=6.1, ha='right', va='center', color=INK)
    # the implied placebo-quota minus k-center gap, from the same regional means (post hoc, same bootstrap)
    for j, src in enumerate((F, M)):
        d = {r: 100 * (src['permuted_region_kcenter']['region_means'][r] - src['kcenter']['region_means'][r])
             for r in src['kcenter']['region_means']}
        m, lo, hi = bootstrap(d)
        y = -1 + (.16 if j == 0 else -.16)
        cx.plot([lo, hi], [y, y], color=MUTED, lw=2, alpha=.4 if j == 0 else .9, solid_capstyle='round')
        cx.scatter([m], [y], marker='D' if j == 0 else 'o', s=30, c='white' if j == 0 else MUTED, ec=MUTED, lw=1.1, zorder=3)
        cx.text(3.05, y, f'{m:+.2f}', fontsize=5.8, va='center', color=INK)
    cx.text(-.03, -1, 'Placebo quota −\nvisual k-center*', transform=cx.get_yaxis_transform(), fontsize=6.1,
            ha='right', va='center', color=INK)
    cx.axvline(0, color=INK, lw=.6)
    cx.set_ylim(-1.55, 1.45); cx.set_xlim(-1.3, 3.0); cx.set_yticks([]); cx.spines['left'].set_visible(False)
    for x in (-1, 1, 2, 3):
        cx.axvline(x, color=GRID, lw=.5, zorder=0)
    cx.set_xlabel('Difference (mIoU points)', fontsize=6.4)
    fig.text(.625, .955, 'c', fontsize=9.5, fontweight='bold')
    fig.text(.645, .955, 'Which gap survives the perturbation', fontsize=7.8, fontweight='bold')
    cx.text(-.62, -.24, 'open: all labels  ·  filled: 2.30 M labels  ·  bars: 95% paired region bootstrap  ·  '
            '*post hoc, same bootstrap', transform=cx.transAxes, fontsize=5.1, color=MUTED)
    save(fig, 'fig5_label_thinning')


if __name__ == '__main__':
    main()
