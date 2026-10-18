"""Assemble the evidence-bound article source from completed V2 analyses.

Prose and table layout are editable here and in the generated JSON. This tool
does not fit models, change scientific outputs, or adjudicate author approval.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from v2_build_documents import source_texts, citation_keys, audited_result_inventory_sha256


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8-sig'))


def sha(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def p(text):
    return {'type': 'paragraph', 'text': text}


def sub(title, *blocks):
    return {'type': 'subsection', 'title': title, 'blocks': list(blocks)}


def table(identifier, caption, headers, rows, notes=(), weights=None):
    return {'type': 'table', 'id': identifier, 'caption': caption, 'headers': headers,
            'rows': rows, 'notes': list(notes), 'column_weights': weights or [1] * len(headers),
            'font_size_pt': 9.5,
            'alignments': ['left'] + ['center'] * (len(headers) - 1)}


def fig(identifier, path, caption, alt, width=6.5):
    return {'type': 'figure', 'id': identifier, 'path': path, 'caption': caption,
            'alt': alt, 'width_inches': width}


def pp(x, signed=False):
    return (f'{100*x:+.2f}' if signed else f'{100*x:.2f}').replace('-', '−')


def interval(m):
    return '[' + pp(m['bootstrap']['lower'], True) + ', ' + pp(m['bootstrap']['upper'], True) + ']'


def bind(source):
    audit = read('evidence/v2/active_run_completeness.json')
    assets = {}
    def walk(blocks):
        for b in blocks:
            if b['type'] == 'figure': assets[b['path']] = sha(b['path'])
            elif b['type'] == 'subsection': walk(b['blocks'])
    for section in source['sections'] + source['back_matter']: walk(section['blocks'])
    source['reference_order'] = []
    for text in source_texts(source):
        for key in citation_keys(text):
            if key not in source['reference_order']: source['reference_order'].append(key)
    extra = ['configs/v2_active_gpu_amendment.json', 'evidence/v2/active_run_completeness.json',
             'configs/v2_cuda_execution_plan.json', 'evidence/v2/cuda_execution_audit.json',
             'tables/v2_cuda/descriptive_analysis.json', 'configs/v2_pixel_budget_plan.json',
             'evidence/v2/pixel_budget_audit.json', 'tables/v2_pixel_budget/descriptive_analysis.json']
    source['evidence_binding'] = {
        'audited_result_inventory_sha256': audited_result_inventory_sha256(audit['results']),
        'freeze_sha256': sha('configs/v2_freeze.json'),
        'numeric_file_sha256': read('tables/v2/analysis_identity.json')['output_sha256'],
        'bibliography_sha256': sha('docs/references_v2.bib'),
        'asset_sha256': assets, 'supplemental_file_sha256': {n: sha(n) for n in extra}}
    return source


def main():
    conditions = list(csv.DictReader((ROOT / 'tables/v2/conditions.csv').open(encoding='utf-8-sig')))
    full = {r['strategy']: r for r in conditions if r['model'] == 'resnet18_unet'}
    cu = read('tables/v2_cuda/descriptive_analysis.json')['contrasts']
    pix = read('tables/v2_pixel_budget/descriptive_analysis.json')['contrasts']
    primary = read('tables/v2/primary.json')
    c = {(a['a'], a['b']): a['overall24'] for a in cu}
    quota = c['region_kcenter', 'kcenter']
    real = c['region_kcenter', 'permuted_region_kcenter']
    wfl = c['region_weighted_facility_location', 'facility_location']
    wfake = c['region_weighted_facility_location', 'permuted_region_weighted_facility_location']
    pq, pr = pix
    names = {'random': 'Uniform random', 'kcenter': 'Visual k-center',
             'region_random': 'Geographic quota random', 'region_kcenter': 'Geographic quota k-center',
             'permuted_region_kcenter': 'Permuted-group quota k-center', 'kmeanspp': 'k-means++ seeding',
             'facility_location': 'Facility location', 'fd_roundrobin': 'Feature-diversity adaptation',
             'region_weighted_facility_location': 'Geographic weighted facility location',
             'permuted_region_weighted_facility_location': 'Permuted weighted facility location'}
    order = ['random', 'kcenter', 'kmeanspp', 'facility_location', 'fd_roundrobin',
             'region_random', 'region_kcenter', 'permuted_region_kcenter',
             'region_weighted_facility_location', 'permuted_region_weighted_facility_location']
    result_rows = [[names[k], pp(float(full[k]['equal_region_union_miou_mean'])),
                    pp(float(full[k]['equal_region_union_miou_fit_sd'])),
                    f"{float(full[k]['selected_region_count_mean']):.2f}"] for k in order]
    contrast_rows = [
        ['Quota k-center − visual k-center', pp(quota['difference'], True), interval(quota)],
        ['Quota k-center − permuted quota k-center', pp(real['difference'], True), interval(real)],
        ['Geographic weighted FL − ordinary FL', pp(wfl['difference'], True), interval(wfl)],
        ['Geographic weighted FL − permuted weighted FL', pp(wfake['difference'], True), interval(wfake)]]
    pixel_rows = []
    for label, a in [('Quota k-center − visual k-center', pq),
                     ('Quota k-center − permuted quota k-center', pr)]:
        for mode, key in [('Full processed labels', 'full_label_reference'),
                          ('2.30 million available labels', 'thinned'),
                          ('Matched − full contrast', 'paired_change')]:
            m = a[key]['overall24']; pixel_rows.append([label, mode, pp(m['difference'], True), interval(m)])

    source = {'format': 'v2-document-source-1', 'kind': 'main',
        'title': 'Geographic allocation and visual coverage for data efficient land cover segmentation',
        'authors': [],
        'keywords': ['land cover segmentation', 'training image selection', 'geographic diversity',
                     'facility location', 'supervision budget', 'OpenEarthMap'],
        'abstract': (
            'Geographic source information offers a simple way to allocate a small image budget across diverse training regions. '
            'We evaluate how this information complements visual coverage in land cover segmentation, using common DINOv2 descriptors, '
            'actual and size-preserving permuted source groups, and a fixed evaluation panel of 72 images from 24 regions. '
            'The main comparison comprises 90 end-to-end ResNet18 segmentation fits and 486 frozen-feature head fits across three source allocations. '
            f'With 12 images from a skewed candidate pool, geographic quota k-center improves equal-region mean intersection over union (mIoU) over visual k-center by {pp(quota["difference"])} percentage points '
            f'(95% region-bootstrap interval {interval(quota)}). Geographic weighted facility location improves on ordinary coverage by {pp(wfl["difference"])} points. '
            'Quota random and geographic weighted facility location achieve 21.41% and 21.24% mIoU, respectively, showing the value of source allocation with simple selection rules. '
            f'An additional 27 fits with exactly 2.30 million available processed supervision pixels retain a {pp(pq["thinned"]["overall24"]["difference"])}-point quota advantage over k-center, '
            f'while the actual-versus-permuted quota contrast decreases from {pp(real["difference"])} to {pp(pr["thinned"]["overall24"]["difference"])} points. '
            'The frozen-feature comparison shows the largest quota gains at the intermediate image budget. '
            'Together, these results identify geographic allocation as a useful complement to visual coverage and show how its coverage and membership comparisons respond differently to supervision matching.'),
        'sections': [
            {'title': '1 Introduction', 'blocks': [
                p('Training-image selection determines the environments represented in a land cover segmentation model. '
                  'A small subset may cover visually distinctive scenes while leaving several source regions unrepresented. '
                  'This choice matters in geographically varied datasets such as OpenEarthMap, where models are evaluated across different landscapes and acquisition conditions {cite:xia2023openearthmap}. '
                  'Source-region identifiers provide information alongside image appearance. Understanding how to use both can help allocate limited labeling and training resources.'),
                p('Visual subset selection supports several forms of coverage. Farthest-first selection prioritizes the largest remaining distance to the selected set, '
                  'whereas facility location maximizes aggregate similarity to selected representatives {cite:sener2018coreset,wei2015submodularity}. '
                  'Nogueira et al. study image-based, label-based and hybrid core-set selection for land cover segmentation with U-Net and SegFormer {cite:nogueira2026coreset}. '
                  'Their results establish training-subset selection as a direct remote-sensing problem. Geographic allocation adds a further choice: how much of the image budget should each source group receive once visual descriptors are available?'),
                p('Geographic diversity and spatial sampling have also received direct attention. Al-Emadi et al. compare geographic source configurations with controlled training quantity in satellite-image classification {cite:alemadi2025spatialshift}. '
                  'Lu et al. combine prior thematic information and boundary criteria for cropland-parcel segmentation, while He et al. develop geocomplexity-based sampling for remote-sensing segmentation {cite:lu2025strategicsampling,he2024geocomplexity}. '
                  'Spatially explicit active learning further incorporates spatial structure into crop classification {cite:kaijage2024spatialal}. '
                  'The present study focuses on complete source images selected once from image descriptors and source identifiers. This setting allows geographic allocation to be compared across coverage rules with a common information set.'),
                p('Two allocation mechanisms are especially relevant when source regions contribute unequal numbers of candidates. '
                  'A count quota restricts which groups can supply the next image. Geographic weighted facility location instead gives each source group the same total weight in the coverage objective. '
                  'The distinction between selected-object quotas and group-average utility is established in group-aware coverage, and weighted sums of submodular objectives provide the corresponding formulation {cite:wang2024utilityfairness,rafiey2024decomposable}. '
                  'Actual and size-preserving permuted groups make the role of regional membership measurable within each mechanism.'),
                p('We evaluate geographic allocation with 576 fits spanning a complete spatial segmentation model and a frozen-feature control, three source allocations, '
                  'and a permanent 24-region evaluation panel. The experiments answer four questions: how quota k-center compares with visual k-center; '
                  'how actual and permuted grouping differ; how effects vary with image budget, source allocation and model recipe; '
                  'and how geographic weighting changes facility-location performance. An additional 27 fits equalize available processed supervision pixels for the quota comparisons.'),
                p('The results show a 1.68-point quota gain over visual k-center in the complete model and a 2.00-point gain after pixel matching. '
                  'Geographic weighted facility location improves on its unweighted counterpart, while quota random achieves the highest mean score in the complete-model comparison. '
                  'The actual-versus-permuted quota contrast decreases under pixel matching, while the gain over visual coverage persists. '
                  'Across the frozen-feature controls, quota gains concentrate at the intermediate budget. These findings provide practical evidence for choosing source allocation and coverage together in data-limited mapping.')
            ]},
            {'title': '2 Materials and methods', 'blocks': [
                sub('2.1 Data and geographic evaluation',
                    p('We use 192 image-mask pairs from 48 OpenEarthMap regions and its eight land cover classes {cite:xia2023openearthmap}. '
                      'The development collection contains 120 images from 24 regions, with five images per region. '
                      'Three cyclic allocations assign 12 regions to source training, four to source validation and eight to unused development data. '
                      'A separate panel contains three filename-sampled images from each of 24 other regions, giving 72 evaluation images. '
                      'Its region list and sampling seed were fixed before acquisition. Images evaluated during earlier development are assigned to development data in this study.'),
                    p('Each allocation offers 60 source-training images. We construct two 36-image candidate pools containing all 12 source regions. '
                      'The balanced pool contains three images per region; the skewed pool contains five images from each of six high-frequency regions and one from each remaining region. '
                      'Pool membership is fixed within each allocation. Images are bilinearly resized to 448 × 448 and masks by nearest-neighbor interpolation. '
                      'Raw label 0 is void and labels 1–8 map to prediction classes. Source-specific attribution accompanies the data, including the upstream SpaceNet citation where applicable {cite:vanetten2018spacenet}.'),
                    p('The data screen checks file identities, decoded duplicates and georeference-supported envelope overlap. '
                      'The checks identify no decoded duplicates or overlap candidates among supported records. '
                      'Two CRS area-of-use cautions are retained for Aachen and Monrovia; a fixed 23-region sensitivity excludes Monrovia. '
                      'Supplementary material lists region roles, image identities and metadata checks. Selection uses image descriptors, identifiers, group labels, budget and seed; candidate masks and evaluation outcomes are outside its inputs.')),
                sub('2.2 Visual coverage and geographic allocation',
                    p('All descriptor-based policies use L2-normalized DINOv2-S/14 class-token (CLS) descriptors {cite:oquab2024dinov2}. '
                      'Visual distance is one minus cosine similarity. Uniform random samples candidates without replacement. '
                      'Visual k-center starts from a random image and repeatedly selects the candidate farthest from its nearest selected image {cite:sener2018coreset}. '
                      'A seeded candidate order resolves ties. The k-means++ baseline uses D-squared seeding on normalized descriptors and returns the sampled candidate images {cite:arthur2007kmeanspp}.'),
                    p('Geographic quota selection restricts each step to candidates in non-exhausted source groups with the smallest selected count. '
                      'Quota random samples from this eligible candidate union; quota k-center chooses its farthest candidate after the initial random selection. '
                      'At budget 12, actual-region quotas select one image from every source region. A permuted-group quota control reassigns membership while preserving group sizes, with one fixed reassignment for each selection seed.'),
                    p('Facility location greedily maximizes F(S) = Σᵢ wᵢ maxⱼ∈S sᵢⱼ, with clipped shifted-cosine similarity sᵢⱼ = (cosᵢⱼ + 1)/2 {cite:wei2015submodularity}. '
                      'Ordinary coverage uses equal candidate weights. Geographic weighting assigns a covered candidate in region r the weight 1/(R nᵣ), '
                      'where R is the number of source regions and nᵣ their candidate count. Each regional mean coverage then contributes equally {cite:wang2024utilityfairness,rafiey2024decomposable}. '
                      'Permuted weighting preserves group sizes and the weight multiset while changing membership. Weighted policies are evaluated in skewed pools; equal weights in balanced pools give the ordinary objective.'),
                    p('The feature-diversity adaptation clusters the same DINO descriptors into 12 groups and samples candidates in random round-robin cluster order, skipping exhausted clusters. '
                      'It uses k-means++ initialization, up to 100 Lloyd iterations and empty-cluster repair. '
                      'This common-representation adaptation follows the feature-diversity selection approach of Nogueira et al.; their published implementation uses ResNet18 descriptors and a Vendi-based adaptive cluster count {cite:nogueira2026coreset}.')),
                sub('2.3 Segmentation models and source calibration',
                    p('The complete model combines an ImageNet-pretrained ResNet18 encoder with a U-Net-style skip decoder {cite:he2016resnet,ronneberger2015unet}. '
                      'Four decoder blocks resize and concatenate skip features and apply two 3 × 3 convolutions with group normalization and rectified linear units (ReLU). '
                      'Block output widths are 128, 64, 32 and 16, followed by an eight-class 1 × 1 output layer. All 12,456,328 trainable parameters are optimized. '
                      'Encoder BatchNorm running statistics remain fixed with batch size two, while affine parameters are trained.'),
                    p('Training draws selected images uniformly with replacement and extracts random 224 × 224 crops. '
                      'Horizontal and vertical flips each have probability 0.5, followed by a uniformly sampled quarter rotation. '
                      'Up to 16 crop proposals are attempted for each image to obtain valid labels. Inputs use ImageNet normalization. '
                      'Cross entropy excludes void pixels. AdamW uses β₁ = 0.9, β₂ = 0.999, ε = 1 × 10⁻⁸ and weight decay 1 × 10⁻⁴ {cite:loshchilov2019adamw}. '
                      'The decoder learning rate is ten times the encoder rate; both remain constant. Evaluation uses complete 448 × 448 images.'),
                    p('For each allocation, calibration uses a fixed 24-image random balanced-pool sample and the 20 source-validation images. '
                      'Image budget B counts the retained training images in each fit; calibration and validation use additional shared development labels. '
                      'The grid compares encoder rates 1 × 10⁻⁴ and 3 × 10⁻⁴ at 300, 600 and 1200 steps, choosing the largest equal-region mean intersection over union (mIoU) on validation data; ties favor fewer steps and then the lower rate. '
                      'The resulting source0/source1/source2 settings are respectively 3 × 10⁻⁴ for 600 steps, 1 × 10⁻⁴ for 1200 steps and 1 × 10⁻⁴ for 600 steps. '
                      'These settings are shared by all policies within an allocation.'),
                    p('The frozen-feature control fits a multilayer perceptron (MLP) with 128 ReLU units and 50,312 parameters to 384-channel DINOv2 patch features on a 32 × 32 grid. '
                      'Targets are adaptive-average-pooled class-indicator maps from native source masks, normalized over valid classes; cells with valid coverage below 0.5 are excluded. '
                      'Each of 600 AdamW steps samples 4096 retained cells with replacement, using learning rate 1 × 10⁻³ and weight decay 1 × 10⁻⁴. '
                      'Evaluation logits are bilinearly expanded to the same 448 grid. This control spans budgets of 6, 12 and 24 images in both candidate pools.')),
                sub('2.4 Experimental matrix and computation',
                    p('Every condition uses three paired selection/optimization seeds, (0, 0), (1, 1) and (2, 2), in each of three source allocations. '
                      'The resulting nine fits per condition yield 90 complete-model and 486 frozen-head fits (Table 1). '
                      'The complete-model comparison uses budget 12 in the skewed pool. '
                      'Complete models run on the RTX4060 Laptop GPU with PyTorch CUDA; frozen heads use CuPy on the same GPU. '
                      'Feature extraction and the original source calibration use CPU PyTorch. Source-calibrated settings are inherited by CUDA execution.'),
                    p('The data partition, selected subsets, comparison and metric were fixed before panel evaluation. '
                      'After initial panel evaluation, a backend amendment moved the complete-model comparison to CUDA; the unified 90-fit series forms the descriptive complete-model analysis. '
                      'The 72 completed CPU fits remain a separate reference series. Supplementary Section S1 records the execution sequence and preserved configuration.'),
                    table('T1', 'Table 1. Experimental matrix.',
                          ['Model or analysis', 'Pools', 'Image budgets', 'Policies', 'Fits'],
                          [['Complete spatial model', 'Skewed', '12', '10', '90'],
                           ['Frozen DINOv2 head', 'Balanced', '6, 12, 24', '8', '216'],
                           ['Frozen DINOv2 head', 'Skewed', '6, 12, 24', '10', '270'],
                           ['Main matrix total', 'Both', 'As above', '64 conditions', '576'],
                           ['Matched-pixel supplement', 'Skewed', '12', '3', '27']],
                          ['Each policy–pool–budget–model condition has three source allocations × three paired fit seeds. The separate 72-fit CPU reference is retained with the execution records.'],
                          [2.5, 1, 1.2, 1.2, .65])),
                sub('2.5 Matched supervision pixel experiment',
                    p('The matched-pixel experiment repeats visual k-center, actual-group quota k-center and permuted-group quota k-center for all nine source–seed pairs. '
                      'Each selected subset retains exactly 2,300,000 available valid pixels on its processed 448 grid. '
                      'The common target is below the source-only minimum of 2,303,273 valid pixels across the complete-model selections. '
                      'A seeded uniform sample removes excess valid labels, assigning them to ignore; selected images, original files, source-calibrated settings and training steps remain fixed.'),
                    p('The experiment matches unique available processed labels. Crop proposals and validity retries follow the full original masks, while the loss uses the retained labels. '
                      'Full masks are restored for validation and evaluation. We summarize both quota contrasts and their paired changes from the full-label CUDA results. '
                      'This supplementary experiment was specified after panel exposure; its plan, mask counts and 27 fits are recorded separately.')),
                sub('2.6 Regional scores and uncertainty',
                    p('For each evaluation region and fit, we sum the confusion matrices of its three images. '
                      'Class IoU is the diagonal count divided by the row sum plus column sum minus that count. '
                      'Union-class mIoU averages classes appearing in truth or prediction, giving prediction-only classes a zero term and omitting classes absent from both. '
                      'An additional truth-present convention averages classes present in regional truth. Equal-region mIoU averages the 24 regional scores.'),
                    p('For policy differences, the nine fit values are first averaged within each region. '
                      'We form 24 paired regional differences and obtain 95% percentile intervals from 10,000 paired region-bootstrap samples, with seed 2026101805. '
                      'Regions are the geographic uncertainty units, consistent with structured-data validation {cite:roberts2017crossvalidation}. '
                      'The intervals describe this fixed panel and its recorded source allocations. Allocation-specific, leave-one-region-out, metric-convention and Monrovia-excluded summaries accompany the estimates. '
                      'Matched-pixel change intervals bootstrap the regional differences of contrasts.'))
            ]},
            {'title': '3 Results', 'blocks': [
                sub('3.1 Geographic allocation improves the complete model comparison',
                    p(f'Geographic quota k-center reaches 19.52% equal-region union-class mIoU, compared with 17.84% for visual k-center (Table 2). '
                      f'The paired difference is {pp(quota["difference"], True)} percentage points, with a 95% region-bootstrap interval of {interval(quota)} (Table 3). '
                      'The difference is positive in 20 of the 24 evaluation regions. Leaving out one region at a time gives mean gains of 1.50–1.89 points. '
                      'The fixed Monrovia-excluded analysis gives +1.58 points, with an interval of [+0.75, +2.41].'),
                    table('T2', 'Table 2. Complete-model performance with 12 images from skewed pools.',
                          ['Selection policy', 'mIoU (%)', 'Fit SD (pp)', 'Source regions selected'], result_rows,
                          ['mIoU is equal-region union-class mIoU. Means and fit standard deviations summarize nine fits per policy. Fit SD summarizes variation across source allocations and paired fit seeds; regional intervals are reported in Table 3.'],
                          [3.6, 1, 1.2, 1.5]),
                    p('The complete ranking also favors simple geographic allocation. Quota random achieves the highest mean score, 21.41%, followed by geographic weighted facility location at 21.24%. '
                      'Ordinary facility location reaches 19.89%, and the feature-diversity adaptation reaches 19.21%. '
                      'Actual-group quotas represent all 12 source regions, whereas visual k-center represents 7.67 on average. '
                      'Geographic weighting represents 11.33 regions on average while retaining a coverage-based objective.'),
                    p('Allocation-specific quota k-center gains over visual k-center are +3.48, −0.54 and +2.09 points for source0, source1 and source2, respectively. '
                      'Figure 1 shows the regional estimates alongside these source-specific comparisons. '
                      'The truth-present metric gives an overall gain of +2.28 points, with a 95% region-bootstrap interval of [+1.34, +3.23].'),
                    fig('F1', 'figures/v2/results/primary_union.png',
                        'Figure 1. Quota k-center relative to visual k-center in the complete model. Regional differences average three source allocations and three paired fit seeds. The allocation summaries use the same 24 regions. Intervals are paired region-bootstrap intervals.',
                        'Regional quota k-center minus visual k-center differences and three source-allocation summaries for union-class mIoU.')),
                sub('3.2 Actual group membership contributes within both allocation mechanisms',
                    p(f'With full processed labels, actual-group quota k-center exceeds its size-preserving permuted-group control by {pp(real["difference"], True)} points '
                      f'(95% interval {interval(real)}). Geographic weighted facility location exceeds ordinary facility location by {pp(wfl["difference"], True)} points '
                      f'and permuted weighting by {pp(wfake["difference"], True)} points (Table 3). '
                      'The actual-versus-permuted weighted comparison retains the same candidate pool, similarity and weight multiset while changing the assignment of those weights to images.'),
                    table('T3', 'Table 3. Paired geographic allocation contrasts for the complete model.',
                          ['Contrast', 'Difference (pp)', '95% regional interval (pp)'], contrast_rows,
                          ['Nine fits are averaged within each region before forming 24 paired differences. FL denotes facility location. Intervals use 10,000 paired region-bootstrap samples.'],
                          [3.9, 1, 1.8]),
                    p('The weighted improvement over ordinary facility location is positive in all three source allocations: +2.43, +0.77 and +0.85 points. '
                      'The actual-versus-permuted weighted differences are +0.67, +1.91 and +3.82 points. '
                      'Quota k-center and weighted facility location therefore provide two distinct ways for source metadata to change the selected training set and its downstream performance.')),
                sub('3.3 Pixel matching retains allocation gains and reduces the membership contrast',
                    p(f'At exactly 2.30 million available processed supervision pixels, quota k-center exceeds visual k-center by {pp(pq["thinned"]["overall24"]["difference"], True)} points '
                      f'(95% interval {interval(pq["thinned"]["overall24"])}). '
                      'The corresponding full-label gain is +1.68 points. Their paired change is +0.32 points, with an interval of [−0.13, +0.74] (Table 4). '
                      'The allocation advantage thus remains visible when the total available valid processed labels is held constant.'),
                    p('Pixel matching changes the actual-versus-permuted quota comparison more strongly. '
                      'Its difference decreases from +0.90 to +0.25 points; the matched-pixel interval is [−0.19, +0.69]. '
                      'The paired reduction is −0.65 points, with an interval of [−1.05, −0.26]. '
                      'The matched-supervision results show a persistent quota-versus-coverage gain alongside a smaller actual-versus-permuted membership contrast. '
                      'Source-specific changes are reported in the supplementary material.'),
                    table('T4', 'Table 4. Available supervision pixel matching and paired contrast changes.',
                          ['Contrast', 'Supervision condition', 'Difference (pp)', '95% interval (pp)'], pixel_rows,
                          ['Both image policies retain 12 selected images. The matched condition supplies exactly 2,300,000 available valid processed labels per fit. Change rows compare matched-pixel and full-label regional contrasts directly.'],
                          [2.5, 2, 1, 1.6])),
                sub('3.4 Frozen-feature gains depend on the image budget',
                    p('The frozen DINOv2 control extends the comparison across two pool profiles and three image budgets (Figure 2). '
                      'At budget 12 in the skewed pool, quota k-center reaches 26.23% mIoU, geographic weighted facility location 26.13%, and quota random 25.82%. '
                      'Across all ten policies in this condition, the frozen recipe scores 4.40–7.06 points above the complete-model recipe. '
                      'Quota k-center minus visual k-center differences are −0.24, +0.90 and +0.17 points at balanced-pool budgets of 6, 12 and 24. '
                      'The corresponding skewed-pool differences are +0.17, +1.33 and +0.32 points. '
                      'The intermediate budget is the most favorable in both profiles: with 12 images, geographic quotas allocate one image to each of the 12 source regions.'),
                    p('Actual-group quota k-center exceeds permuted grouping by +0.73 points in the balanced 12-image condition and +1.27 points in its skewed counterpart. '
                      'For skewed pools, geographic weighted facility location exceeds ordinary facility location by +0.32, +0.45 and +0.03 points at budgets 6, 12 and 24, respectively. '
                      'Its differences from permuted weighting are +0.93, +0.76 and +0.12 points. '
                      'The effects taper as the selected subset covers a larger share of the 36-image candidate pool.'),
                    fig('F2', 'figures/v2/results/frozen_pools_budgets.png',
                        'Figure 2. Frozen-feature selection comparisons across pool profiles and image budgets. Each mean summarizes nine fits evaluated on the same 24 regions. The complete policy matrix is supplied in the supplementary tables and machine-readable results.',
                        'Frozen DINOv2 head performance across balanced and skewed pools at image budgets 6, 12 and 24.'))
            ]},
            {'title': '4 Discussion', 'blocks': [
                sub('4.1 Source allocation complements descriptor coverage',
                    p('Geographic allocation improves several directly matched coverage comparisons. '
                      'The complete-model gain of quota k-center over visual k-center persists after available-pixel matching, '
                      'and source-mean weighting improves facility location in each source allocation. '
                      'These results support using source identifiers alongside visual descriptors when a few images must represent many regions. '
                      'The quota-random result gives a useful operational reference: distributing a small budget across sources can be competitive with more elaborate descriptor-based rules.'),
                    p('The observed ranking connects to earlier work on geographic diversity and data selection. '
                      'Al-Emadi et al. show the relevance of source geography under controlled training quantity, and Nogueira et al. evaluate representative image subsets for segmentation {cite:alemadi2025spatialshift,nogueira2026coreset}. '
                      'Our comparison adds actual-versus-permuted grouping within a common representation and follows the resulting effects through a supervision-pixel intervention. '
                      'The empirical contribution is a controlled comparison of geographic allocation, regional membership and supervision amount in the same land cover selection problem.'),
                    p('Hard quotas and source-mean weighting offer different allocation options. '
                      'At budget 12, the quota ensures one selected image per source region. '
                      'Weighted facility location gives every region the same total weight in the coverage objective while allowing unequal selected counts. '
                      'The latter reaches 21.24% mIoU with 11.33 represented sources on average. '
                      'This flexibility provides a practical alternative when rare source groups should influence selection but exact selected counts are unnecessary. '
                      'Group-average utility and weighted coverage have established formulations {cite:wang2024utilityfairness,rafiey2024decomposable}; '
                      'the segmentation results show how those allocation choices behave under the present image budgets.')),
                sub('4.2 Supervision budgets distinguish two benefits',
                    p('The pixel-matched experiment reveals different responses in the allocation and actual-membership comparisons. '
                      'Quota k-center retains a +2.00-point gain over visual k-center, while its advantage over arbitrary size-matched groups decreases to +0.25 points. '
                      'The −0.65-point paired change quantifies this attenuation directly. '
                      'Consequently, the full-label actual-group contrast and the broader quota-versus-coverage contrast capture different aspects of the selected subsets.'),
                    p('Available pixel counts are one measurable component of supervision. '
                      'The intervention holds their processed total fixed while preserving selected image identities, source-calibrated steps and crop proposals. '
                      'Image content, class composition and spatial arrangement remain part of the selected subsets. '
                      'This design makes a precise budget comparison possible without introducing candidate semantic labels into selection. '
                      'For future collection campaigns, both image count and usable labeled area provide relevant planning quantities; annotation time would require a separate measurement.')),
                sub('4.3 Budget and training recipe guide policy choice',
                    p('The frozen-feature matrix places the largest quota gains at budget 12 in both pool profiles. '
                      'This budget aligns with the number of source regions and makes source coverage an immediate allocation decision. '
                      'At budget 24, visual coverage already selects two thirds of the candidate pool, leaving less room for the allocation rules to alter the subset. '
                      'The pattern suggests that source balancing is especially useful where a restricted budget can omit whole source environments.'),
                    p('The two training recipes provide complementary views of selection. The spatial model updates a ResNet18 encoder and decoder, '
                      'whereas the frozen control trains a small head on DINOv2 patch features. They also use different supervision aggregation and augmentation. '
                      'Their results describe the combined recipes. Within each recipe, a shared descriptor and matched policy conditions keep the allocation comparison interpretable. '
                      'Source-specific effects further combine source composition with the allocation-specific calibration settings. '
                      'Reporting those effects helps practitioners identify whether a favorable panel mean is shared across their available source configurations.'),
                    p('Training conditions and budgets also matter in iterative active learning {cite:mittal2025realistic}. '
                      'The one-shot source-image setting studied here is most directly useful when a fixed batch must be selected before downstream fitting. '
                      'Its quota and weighting controls can be incorporated into larger selection studies that add uncertainty updates, additional source realizations or annotation-time budgets.')),
                sub('4.4 Scope and next evaluations',
                    p('The evidence covers 48 dataset regions, with 24 purposively selected regions in a fixed evaluation panel and three overlapping source allocations. '
                      'Scores refer to processed 448 × 448 labels under short, source-calibrated training schedules. '
                      'The two pool profiles can contain different image identities, so their comparison includes candidate composition. '
                      'The pixel-matched supplement controls available processed labels rather than cumulative crop exposure or annotation labor. '
                      'These features define a focused low-budget transfer setting. Larger source collections, repeated independent panels and stronger segmentation recipes are natural next evaluations of the allocation patterns.')
                )
            ]},
            {'title': '5 Conclusions', 'blocks': [
                p('Geographic allocation complements visual coverage in low-budget land cover segmentation. '
                  'Across a fixed 24-region panel, quota k-center improves on visual k-center by 1.68 mIoU percentage points in the complete model and by 2.00 points with matched available supervision pixels. '
                  'Source-mean weighting improves facility location, and quota random provides a strong simple reference. '
                  'Pixel matching reduces the actual-versus-permuted quota contrast while retaining the gain over visual k-center. '
                  'The frozen-feature matrix locates the largest quota gains at the intermediate image budget. '
                  'Together, the findings support selecting source allocation and visual coverage jointly, with image and supervision budgets made explicit.')
            ]}
        ],
        'back_matter': [
            {'title': 'Supplementary materials', 'blocks': [p('The accompanying supplement provides the source and evaluation inventories, calibration details, selection rules, execution sequence, complete condition tables, regional sensitivities and pixel-matching results.')]},
            {'title': 'Data and code availability', 'blocks': [p('The accompanying research folder contains processed image-mask pairs and provenance sidecars, selected image identities, configurations, analysis code, per-image confusion matrices, training records, machine-readable tables and editable figures. OpenEarthMap and its upstream image sources retain their respective licenses and attribution requirements. A preserved CPU-reference checkpoint supports an independent reload check.')]},
            {'title': 'Use of generative AI', 'blocks': [p('OpenAI Codex assisted with study planning, software implementation, experiment execution, analysis and manuscript drafting. The accompanying records document the generated code, executed experiments and reported numerical outputs.')]}
        ], 'reference_order': [], 'evidence_binding': {}}
    source = bind(source)
    destination = ROOT / 'paper/v2'; destination.mkdir(exist_ok=True, parents=True)
    path = destination / 'manuscript_source.json'
    path.write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    text = '\n\n'.join(source_texts(source)) + '\n'
    (ROOT / 'paper/v2_working/manuscript_candidate.txt').write_text(text, encoding='utf-8')
    print(json.dumps({'source': str(path), 'words': len(text.split()), 'citations': len(source['reference_order']),
                      'source_sha256': sha('paper/v2/manuscript_source.json')}))


if __name__ == '__main__': main()
