"""Figure 3: how the four selection rules behave, on simulated descriptors (an illustration, not experimental data).

The rules are the same greedy procedures as in the study, applied to a toy 2-D pool with four five-image regions,
four one-image regions and two visually extreme images.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from v3_common import INK, MUTED, FAINT, COLOR, save

REG_COL = ['#e8590c', '#2f9e44', '#1971c2', '#9c36b5', '#e0a800', '#0c8599', '#d6336c', '#5c940d']
BUDGET = 8


def toy_pool():
    rng = np.random.default_rng(7)
    centres = np.array([[-1.6, 1.0], [1.5, 1.3], [-1.2, -1.5], [1.4, -1.2],      # heavy regions 0-3
                        [-.1, .25], [.35, -.35], [-.45, -.25], [.25, .55]])       # singleton regions 4-7
    X, R = [], []
    for r in range(4):
        pts = centres[r] + rng.normal(0, .23, (5, 2))
        X.extend(pts); R.extend([r] * 5)
    for r in range(4, 8):
        X.append(centres[r]); R.append(r)
    X = np.array(X); R = np.array(R)
    X[2] = [-3.1, 2.7]     # an extreme image in heavy region 0
    X[13] = [3.0, -2.9]    # an extreme image in heavy region 2... (index 13 belongs to region 2)
    X[7] = [3.2, 2.9]      # an extreme image in heavy region 1
    return X, R


def kcenter(X, eligible_fn, start):
    sel = [start]
    while len(sel) < BUDGET:
        d = np.min(np.linalg.norm(X[:, None] - X[sel][None], axis=2), axis=1)
        d[sel] = -1
        elig = eligible_fn(sel)
        d[~elig] = -1
        sel.append(int(np.argmax(d)))
    return sel


def quota_eligible(groups):
    def f(sel):
        counts = {g: sum(groups[s] == g for s in sel) for g in set(groups)}
        avail = {g for g in set(groups) if any(groups[i] == g and i not in sel for i in range(len(groups)))}
        m = min(counts[g] for g in avail)
        return np.array([groups[i] in avail and counts[groups[i]] == m for i in range(len(groups))])
    return f


def weighted_fl(X, groups):
    sim = 1 / (1 + np.linalg.norm(X[:, None] - X[None], axis=2))
    n = {g: np.sum(groups == g) for g in set(groups)}
    w = np.array([1 / (len(n) * n[g]) for g in groups])
    sel, cover = [], np.zeros(len(X))
    for _ in range(BUDGET):
        gain = [(w * (np.maximum(cover, sim[:, j]) - cover)).sum() if j not in sel else -1 for j in range(len(X))]
        j = int(np.argmax(gain)); sel.append(j); cover = np.maximum(cover, sim[:, j])
    return sel


def main():
    X, R = toy_pool()
    rng = np.random.default_rng(3)
    P = R.copy(); rng.shuffle(P)
    extreme = {2, 7, 13}
    start = 2
    rules = [
        ('Visual k-center', COLOR['kcenter'], kcenter(X, lambda s: np.ones(len(X), bool), start),
         'farthest image first: chases the extremes,\nstacks picks in the big regions'),
        ('Geo-quota k-center', COLOR['region_kcenter'], kcenter(X, quota_eligible(R), start),
         'one pick per real region before any second pick;\nfarthest image within the eligible regions'),
        ('Placebo-quota k-center', COLOR['permuted_region_kcenter'], kcenter(X, quota_eligible(P), start),
         'same quota on shuffled, size-matched groups:\nspreads over the wrong partition'),
        ('Geo-weighted facility location', COLOR['region_weighted_facility_location'], weighted_fl(X, R),
         'each real region carries equal total weight;\nrepresentative images, counts may differ'),
    ]
    fig, axs = plt.subplots(1, 4, figsize=(7.5, 2.75))
    for k, (ax, (name, col, sel, note)) in enumerate(zip(axs, rules)):
        ax.scatter(X[:, 0], X[:, 1], s=26, c=[REG_COL[r] for r in R], alpha=.35, lw=0, zorder=2)
        for i in extreme:
            ax.add_patch(Circle(X[i], .36, fc='none', ec=FAINT, lw=.6, ls=(0, (2, 1.5)), zorder=1))
        path = X[sel]
        ax.plot(path[:, 0], path[:, 1], color=col, lw=.6, alpha=.55, zorder=3)
        ax.scatter(path[:, 0], path[:, 1], s=60, c=[REG_COL[R[i]] for i in sel], ec=INK, lw=.8, zorder=4)
        for o, i in enumerate(sel, 1):
            ax.text(X[i, 0], X[i, 1], str(o), fontsize=4.8, ha='center', va='center', color='white', fontweight='bold', zorder=5)
        ax.set_xlim(-3.7, 3.8); ax.set_ylim(-3.6, 3.5); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(True); s.set_color(col); s.set_linewidth(1.2)
        ax.set_title(f'{"abcd"[k]}  {name}', fontsize=7, color=col, loc='left', pad=3)
        reached = len({R[i] for i in sel}); ext = len(extreme & set(sel))
        single = len({R[i] for i in sel if R[i] >= 4})
        ax.text(.03, .03, f'{reached}/8 regions · {single}/4 singletons\n{ext}/3 extreme images', transform=ax.transAxes,
                fontsize=5.3, va='bottom', color=INK, bbox=dict(fc='white', ec='none', alpha=.85, pad=1))
        ax.text(.5, -.05, note, transform=ax.transAxes, fontsize=5.3, ha='center', va='top', color=MUTED, linespacing=1.3)
    fig.text(.5, .035, 'Simulated 2-D descriptors: four regions offer five images, four offer one; dashed rings mark '
             'three visually extreme images. Numbers give pick order (budget 8). Illustration only.',
             ha='center', fontsize=5.6, color=MUTED, style='italic')
    fig.subplots_adjust(wspace=.06, left=.01, right=.99, top=.9, bottom=.22)
    save(fig, 'fig3_rules')
    for name, _, sel, _ in rules:
        print(name, sel, sorted({int(R[i]) for i in sel}))


if __name__ == '__main__':
    main()
