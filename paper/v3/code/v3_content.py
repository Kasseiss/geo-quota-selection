"""Single source for both submission formats: references, citation numbering, table contents and abbreviations.

Table values are computed from the recorded result files; no number in a table is typed by hand.
"""
import re

import pandas as pd

from v3_common import ROOT, LABEL, numbers, contrast, pixel_contrasts, bootstrap

# MDPI (ACS-like) reference style; each entry is a list of (text, style) runs so both renderers can apply italics/bold
# for journal names, years and volumes.
REFS = {
    'xia2023': [('Xia, J.; Yokoya, N.; Adriano, B.; Broni-Bediako, C. OpenEarthMap: A Benchmark Dataset for Global '
                 'High-Resolution Land Cover Mapping. In Proceedings of the IEEE/CVF Winter Conference on Applications '
                 'of Computer Vision (WACV), Waikoloa, HI, USA, 2–7 January 2023; pp. 6254–6264.', ''),
                (' https://doi.org/10.1109/WACV56688.2023.00619', 'url')],
    'sener2018': [('Sener, O.; Savarese, S. Active Learning for Convolutional Neural Networks: A Core-Set Approach. In '
                   'Proceedings of the International Conference on Learning Representations (ICLR), Vancouver, BC, '
                   'Canada, 30 April–3 May 2018.', '')],
    'wei2015': [('Wei, K.; Iyer, R.; Bilmes, J. Submodularity in Data Subset Selection and Active Learning. In '
                 'Proceedings of the 32nd International Conference on Machine Learning (ICML), Lille, France, 6–11 '
                 'July 2015; PMLR 37, pp. 1954–1963.', '')],
    'nogueira2026': [('Nogueira, K.; Zaytar, A.; Ma, W.; Roscher, R.; Hänsch, R.; Robinson, C.; Ortiz, A.; Fobi, S.; '
                      'Dodhia, R.; Lavista Ferres, J.M.; et al. Core-Set Selection for Data-Efficient Land Cover '
                      'Segmentation. ', ''), ('IEEE Access', 'i'), (' ', ''), ('2026', 'b'), (', ', ''), ('14', 'i'),
                     (', 19891–19903.', ''), (' https://doi.org/10.1109/ACCESS.2026.3659734', 'url')],
    'hacohen2022': [('Hacohen, G.; Dekel, A.; Weinshall, D. Active Learning on a Budget: Opposite Strategies Suit High '
                     'and Low Budgets. In Proceedings of the 39th International Conference on Machine Learning (ICML), '
                     'Baltimore, MD, USA, 17–23 July 2022; PMLR 162, pp. 8175–8195.', '')],
    'alemadi2025': [('Al-Emadi, S.A.; Yang, Y.; Ofli, F. Analysing Satellite Imagery Classification under Spatial '
                     'Domain Shift across Geographic Regions. ', ''), ('Int. J. Comput. Vis.', 'i'), (' ', ''),
                    ('2025', 'b'), (', ', ''), ('133', 'i'), (', 7672–7709.', ''),
                    (' https://doi.org/10.1007/s11263-025-02518-z', 'url')],
    'cai2021': [('Cai, L.; Xu, X.; Zhang, L.; Foo, C.-S. Exploring Spatial Diversity for Region-Based Active Learning. ', ''),
                ('IEEE Trans. Image Process.', 'i'), (' ', ''), ('2021', 'b'), (', ', ''), ('30', 'i'),
                (', 8702–8712.', ''), (' https://doi.org/10.1109/TIP.2021.3120041', 'url')],
    'kaijage2024': [('Kaijage, B.; Belgiu, M.; Bijker, W. Spatially Explicit Active Learning for Crop-Type Mapping from '
                     'Satellite Image Time Series. ', ''), ('Sensors', 'i'), (' ', ''), ('2024', 'b'), (', ', ''),
                    ('24', 'i'), (', 2108.', ''), (' https://doi.org/10.3390/s24072108', 'url')],
    'he2024': [('He, W.; Li, L.; Gao, X. Geocomplexity Statistical Indicator to Enhance Multiclass Semantic Segmentation '
                'of Remotely Sensed Data with Less Sampling Bias. ', ''), ('Remote Sens.', 'i'), (' ', ''), ('2024', 'b'),
               (', ', ''), ('16', 'i'), (', 1987.', ''), (' https://doi.org/10.3390/rs16111987', 'url')],
    'lu2025': [('Lu, R.; Liao, R.; Meng, R.; Hu, Y.; Zhao, Y.; Guo, Y.; Zhang, Y.; Shi, Z.; Ye, S. Strategic Sampling for '
                'Training a Semantic Segmentation Model in Operational Mapping: Case Studies on Cropland Parcel '
                'Extraction. ', ''), ('Remote Sens. Environ.', 'i'), (' ', ''), ('2025', 'b'), (', ', ''), ('331', 'i'),
               (', 115034.', ''), (' https://doi.org/10.1016/j.rse.2025.115034', 'url')],
    'wang2024': [('Wang, Y.; Li, Y.; Bonchi, F.; Wang, Y. Balancing Utility and Fairness in Submodular Maximization. In '
                  'Proceedings of the 27th International Conference on Extending Database Technology (EDBT), Paestum, '
                  'Italy, 25–28 March 2024; pp. 1–14.', ''), (' https://doi.org/10.48786/edbt.2024.01', 'url')],
    'rafiey2024': [('Rafiey, A. Decomposable Submodular Maximization in Federated Setting. In Proceedings of the 41st '
                    'International Conference on Machine Learning (ICML), Vienna, Austria, 21–27 July 2024; PMLR 235, '
                    'pp. 41841–41866.', '')],
    'oquab2024': [('Oquab, M.; Darcet, T.; Moutakanni, T.; Vo, H.V.; Szafraniec, M.; Khalidov, V.; Fernandez, P.; '
                   'Haziza, D.; Massa, F.; El-Nouby, A.; et al. DINOv2: Learning Robust Visual Features without '
                   'Supervision. ', ''), ('Trans. Mach. Learn. Res.', 'i'), (' ', ''), ('2024', 'b'), ('.', ''),
                  (' Available online: https://openreview.net/forum?id=a68SUt6zFt (accessed on 18 October 2026).', '')],
    'arthur2007': [('Arthur, D.; Vassilvitskii, S. k-means++: The Advantages of Careful Seeding. In Proceedings of the '
                    '18th Annual ACM-SIAM Symposium on Discrete Algorithms (SODA), New Orleans, LA, USA, 7–9 January '
                    '2007; pp. 1027–1035.', '')],
    'he2016': [('He, K.; Zhang, X.; Ren, S.; Sun, J. Deep Residual Learning for Image Recognition. In Proceedings of the '
                'IEEE Conference on Computer Vision and Pattern Recognition (CVPR), Las Vegas, NV, USA, 27–30 June '
                '2016; pp. 770–778.', ''), (' https://doi.org/10.1109/CVPR.2016.90', 'url')],
    'ronneberger2015': [('Ronneberger, O.; Fischer, P.; Brox, T. U-Net: Convolutional Networks for Biomedical Image '
                         'Segmentation. In ', ''), ('Medical Image Computing and Computer-Assisted Intervention—MICCAI '
                         '2015', 'i'), ('; Lecture Notes in Computer Science; Springer: Cham, Switzerland, 2015; Volume '
                         '9351, pp. 234–241.', ''), (' https://doi.org/10.1007/978-3-319-24574-4_28', 'url')],
    'loshchilov2019': [('Loshchilov, I.; Hutter, F. Decoupled Weight Decay Regularization. In Proceedings of the '
                        'International Conference on Learning Representations (ICLR), New Orleans, LA, USA, 6–9 May '
                        '2019.', '')],
    'roberts2017': [('Roberts, D.R.; Bahn, V.; Ciuti, S.; Boyce, M.S.; Elith, J.; Guillera-Arroita, G.; Hauenstein, S.; '
                     'Lahoz-Monfort, J.J.; Schröder, B.; Thuiller, W.; et al. Cross-Validation Strategies for Data '
                     'with Temporal, Spatial, Hierarchical, or Phylogenetic Structure. ', ''), ('Ecography', 'i'),
                    (' ', ''), ('2017', 'b'), (', ', ''), ('40', 'i'), (', 913–929.', ''),
                    (' https://doi.org/10.1111/ecog.02881', 'url')],
    'mittal2025': [('Mittal, S.; Niemeijer, J.; Çiçek, Ö.; Tatarchenko, M.; Ehrhardt, J.; Schäfer, '
                    'J.P.; Handels, H.; Brox, T. Realistic Evaluation of Deep Active Learning for Image Classification '
                    'and Semantic Segmentation. ', ''), ('Int. J. Comput. Vis.', 'i'), (' ', ''), ('2025', 'b'), (', ', ''),
                   ('133', 'i'), (', 4294–4316.', ''), (' https://doi.org/10.1007/s11263-025-02372-z', 'url')],
}

ABBREVIATIONS = [('CLS', 'class token'), ('CPU', 'central processing unit'), ('FL', 'facility location'),
                 ('GPU', 'graphics processing unit'), ('IoU', 'intersection over union'),
                 ('mIoU', 'mean intersection over union'), ('MLP', 'multilayer perceptron'),
                 ('OEM', 'OpenEarthMap'), ('RGB', 'red, green, blue'), ('WGS84', 'World Geodetic System 1984')]


class Citer:
    """Numbers [@key; @key] citations by first appearance; renders as [1,2] or as \\cite{key,key}."""

    def __init__(self):
        self.order = []

    def _register(self, keys):
        for k in keys:
            if k not in REFS:
                raise KeyError(k)
            if k not in self.order:
                self.order.append(k)

    def numbers(self, text):
        def repl(m):
            keys = [k.strip().lstrip('@') for k in m.group(1).split(';')]
            self._register(keys)
            nums = sorted(self.order.index(k) + 1 for k in keys)
            parts, i = [], 0
            while i < len(nums):
                j = i
                while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
                    j += 1
                parts.append(f'{nums[i]}–{nums[j]}' if j - i >= 2 else ','.join(map(str, nums[i:j + 1])))
                i = j + 1
            return '[' + ','.join(parts) + ']'
        return re.sub(r'\[(@[^\]]+)\]', repl, text)

    def keys(self, text):
        """Register keys and return the list of (start, end, keys) spans, for renderers that build their own markup."""
        spans = []
        for m in re.finditer(r'\[(@[^\]]+)\]', text):
            keys = [k.strip().lstrip('@') for k in m.group(1).split(';')]
            self._register(keys)
            spans.append((m.start(), m.end(), keys))
        return spans


def fmt(c):
    return f'{c[0]:+.2f} [{c[1]:+.2f}, {c[2]:+.2f}]'


def table_policies():
    rows = [['Random', 'none', 'no', '–'],
            ['Visual k-center', 'farthest image from the chosen set', 'no', '–'],
            ['k-means++ seeding', 'distant images, drawn with probability ∝ d²', 'no', '–'],
            ['Facility location (FL)', 'summed similarity to the closest pick', 'no', '–'],
            ['Feature-cluster round robin', 'one pick per k-means cluster in turn', 'no', '–'],
            ['Geo-quota random', 'random within the least-filled regions', 'quota', 'real'],
            ['Geo-quota k-center', 'farthest image within the least-filled regions', 'quota', 'real'],
            ['Geo-weighted FL', 'FL with equal total weight per region', 'weights', 'real'],
            ['Placebo-quota k-center', 'as geo-quota k-center', 'quota', 'shuffled'],
            ['Placebo-weighted FL', 'as geo-weighted FL', 'weights', 'shuffled']]
    return dict(label='Table 1', key='tab:rules', caption='The ten label-free selection rules.',
                headers=[['Rule', 'Choice Criterion', 'Region Use', 'Groups']], rows=rows,
                widths=[1.75, 2.75, .8, .8], align='llcc', bold=set(),
                notes='All rules receive the same DINOv2 descriptors, region labels, budget and seed, and no masks, class '
                      'counts or scores. Placebo rules use size-preserving shuffles of the region labels.')


def table_matrix():
    rows = [['Complete model (ResNet18 U-Net), GPU', 'skewed', '12', '10', '90', 'main analysis'],
            ['Frozen DINOv2 + MLP head, GPU', 'balanced', '6, 12, 24', '8', '216', 'budget and pool control'],
            ['Frozen DINOv2 + MLP head, GPU', 'skewed', '6, 12, 24', '10', '270', 'budget and pool control'],
            ['Main matrix', '', '', '64 conditions', '576', ''],
            ['Complete model, CPU re-execution', 'skewed', '12', '8', '72', 'second execution'],
            ['Complete model, 2.30 M labels, GPU', 'skewed', '12', '3', '27', 'equal-label experiment']]
    return dict(label='Table 2', key='tab:matrix', caption='Experimental matrix.',
                headers=[['Series', 'Pool', 'Budget', 'Rules', 'Fits', 'Role']], rows=rows,
                widths=[2.35, .7, .75, .9, .5, 1.45], align='lcccc' + 'l', bold={(3, 4)},
                notes='Each condition has three source allocations × three paired seeds. The CPU re-execution and the '
                      'equal-label fits are separate series and are never pooled with the main matrix.')


def atyp(v):
    return '0.000' if abs(v) < .0005 else f'{v:+.3f}'


def table_results():
    from fig6_anatomy import singleton_picks
    N = numbers()
    C, cpu = N['complete'], N['cpu_replication']['policy_means']
    cond = pd.read_csv(ROOT / 'tables/v2/conditions.csv')
    q = cond[cond.model == 'resnet18_unet'].set_index('strategy')
    sp = singleton_picks()
    rows = []
    for p in sorted(C, key=lambda p: -C[p]['mean']):
        rows.append([LABEL[p], f'{100 * C[p]["mean"]:.2f} ({100 * q.loc[p].equal_region_union_miou_fit_sd:.2f})',
                     f'{cpu[p]["cpu"]:.2f}' if p in cpu else '–',
                     f'{100 * q.loc[p].worst_region_union_miou_mean:.2f}', f'{C[p]["regions_mean"]:.1f}',
                     f'{sp[p][1]:.1f}', atyp(C[p]["atyp_mean"] - C[p]["pool_atyp_mean"])])
    return dict(label='Table 3', key='tab:results',
                caption='Complete-model results and selection properties (skewed pools, B = 12).',
                headers=[['Rule', 'mIoU (%)', None, 'Worst', 'Selection Properties', None, None],
                         ['', 'GPU (SD)', 'CPU', 'Region', 'Regions', 'One-Image', 'Atypicality']],
                rows=rows, widths=[1.75, .95, .55, .6, .65, .75, .8], align='lcccccc', bold=set(),
                notes='Means over nine fits; SD is the fit standard deviation (not a geographic interval). Worst region: '
                      'mean of each fit’s lowest regional score. Regions: training regions represented among the 12 '
                      'picks. One-image: picks from the six one-image regions. Atypicality: mean excess cosine distance '
                      'of the picks. The weighted rules were not part of the CPU execution.')


def table_contrasts():
    N = numbers()
    rep = N['cpu_replication']['contrasts']
    pc = pixel_contrasts()
    M = N['pixel_matched']

    def posthoc(src, a, b):
        ra, rb = src[a]['region_means'], src[b]['region_means']
        diffs = {r: 100 * (ra[r] - rb[r]) for r in ra}
        return bootstrap(diffs), sum(v > 0 for v in diffs.values())

    short = {'kcenter': 'Visual K', 'region_kcenter': 'GeoK', 'permuted_region_kcenter': 'PlaceboK',
             'region_weighted_facility_location': 'GeoFL', 'facility_location': 'FL',
             'permuted_region_weighted_facility_location': 'PlaceboFL', 'region_random': 'GeoRand', 'random': 'Random',
             'kmeanspp': 'k-means++'}
    specs = [('region_kcenter', 'kcenter'), ('region_kcenter', 'permuted_region_kcenter'),
             ('permuted_region_kcenter', 'kcenter'), ('region_weighted_facility_location', 'facility_location'),
             ('region_weighted_facility_location', 'permuted_region_weighted_facility_location'),
             ('region_random', 'random'), ('facility_location', 'kcenter'), ('kmeanspp', 'kcenter'),
             ('region_kcenter', 'facility_location')]
    rows = []
    for a, b in specs:
        try:
            c = contrast(a, b)
            g, n = (c['d'], c['lo'], c['hi']), sum(v > 0 for v in c['regional'].values())
        except KeyError:
            g, n = posthoc(N['complete'], a, b)
        if (a, b) == ('region_kcenter', 'kcenter'):
            t = pc['kcenter']['thinned']; thin = fmt((t['d'], t['lo'], t['hi']))
        elif (a, b) == ('region_kcenter', 'permuted_region_kcenter'):
            t = pc['permuted_region_kcenter']['thinned']; thin = fmt((t['d'], t['lo'], t['hi']))
        elif (a, b) == ('permuted_region_kcenter', 'kcenter'):
            t, _ = posthoc(M, a, b); thin = fmt(t) + '*'
        else:
            thin = '–'
        r = rep.get(f'{a}-{b}')
        cpu = (fmt((r['cpu']['d'], r['cpu']['lo'], r['cpu']['hi'])) + f' ({r["cpu"]["regions_positive"]})') if r else '–'
        rows.append([f'{short[a]} − {short[b]}', fmt(g) + f' ({n})', thin, cpu])
    return dict(label='Table 4', key='tab:contrasts',
                caption='Paired contrasts in the complete model (mIoU points; in parentheses, the number of the 24 '
                        'panel regions favouring the first rule).',
                headers=[['Contrast', 'GPU, All Labels', 'GPU, 2.30 M Labels', 'CPU Re-Execution']], rows=rows,
                widths=[1.45, 1.75, 1.6, 1.75], align='lccc', bold={(0, 1)},
                notes='Differences with 95% paired region-bootstrap intervals. The first row is the main contrast; the '
                      'others are secondary. Intervals not stored in the result tables were recomputed with the same '
                      'procedure and seed. *Computed post hoc from the equal-label fits. GeoK, geo-quota k-center; '
                      'PlaceboK, placebo-quota k-center; GeoFL, geo-weighted facility location; GeoRand, geo-quota '
                      'random.')


def outline():
    """The body of the article as a sequence of blocks shared by the Word and LaTeX renderers."""
    import v3_text as T
    B = []
    h1 = lambda t: B.append(('h1', t))
    h2 = lambda t: B.append(('h2', t))
    ps = lambda xs: B.extend(('p', x) for x in xs)
    fig = lambda name, key: B.append(('fig', name, T.CAPTIONS[key], key))
    h1('Introduction'); ps(T.INTRO); B.append(('enum', T.CONTRIBUTIONS))
    ps(['Figure 1 summarizes the design with recorded data. Section 2 describes the data, rules, models and analyses; '
        'Section 3 reports the results in the order of the alternative explanations above; Section 4 discusses what '
        'they imply for choosing training images.'])
    fig('fig1_overview', 'fig1')
    h1('Materials and Methods')
    h2('Data and Geographic Design'); ps(T.M21); fig('fig2_geography', 'fig2')
    h2('Candidate Pools and Budgets'); ps(T.M22)
    h2('Selection Rules'); ps(T.M23[:1]); B.append(('table', table_policies())); ps(T.M23[1:]); fig('fig3_rules', 'fig3')
    h2('Segmentation Models and Calibration'); ps(T.M24)
    h2('Experimental Matrix and Execution History'); ps(T.M25[:1]); B.append(('table', table_matrix())); ps(T.M25[1:])
    h2('Equal-Label Experiment'); ps(T.M26)
    h2('Evaluation, Uncertainty and Selection Diagnostics'); ps(T.M27)
    h1('Results')
    h2('Farthest-Point Coverage Was the Weakest Rule, Twice'); ps(T.R31[:1]); B.append(('table', table_results()))
    fig('fig4_main_results', 'fig4'); ps(T.R31[1:])
    h2('A Geographic Quota Repairs Most of the Loss'); ps(T.R32[:2]); B.append(('table', table_contrasts())); ps(T.R32[2:])
    h2('What the Placebo Groups Reveal'); ps(T.R33)
    h2('Label Counts Do Not Explain the Gain'); ps(T.R34); fig('fig5_label_thinning', 'fig5')
    h2('Breadth and Typicality of the Selected Images'); ps(T.R35); fig('fig6_selection_anatomy', 'fig6')
    h2('When Allocation Matters'); ps(T.R36); fig('fig7_budget_conditions', 'fig7')
    h1('Discussion')
    for h, body in (('At Twelve Images, Diversity Means Outliers', T.D41), ('Does the Identity of the Regions Matter?', T.D42),
                    ('Practical Guidance', T.D43), ('Limitations and Next Steps', T.D44)):
        h2(h); ps(body)
    h1('Conclusions'); ps(T.CONCLUSION)
    return B
