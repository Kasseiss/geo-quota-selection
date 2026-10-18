"""Manuscript text for v3. Citations are written as [@key] and numbered by first appearance when the document is built.

Every number below was checked against tables/v2/*.json, tables/v2_pixel_budget/*.json, paper/v3/figures/v3_numbers.json
or the configuration files; tables are generated from those files directly.
"""

TITLE = ('When Diversity Means Outliers: Geographic Allocation for Selecting Training Images in Low-Budget Land Cover '
         'Segmentation')

AUTHORS = 'Author names, affiliations and the corresponding author are to be supplied by the authors.'

ABSTRACT = (
    'When only a dozen images can be labeled, the usual advice is to pick images that differ as much as possible. In a '
    'pretrained feature space, however, the image farthest from those already chosen is often just the most unusual '
    'one. We tested whether source-region metadata offers a better kind of diversity. Ten label-free rules chose 12 '
    'images from 36-image pools spanning 12 OpenEarthMap regions to train a ResNet18 U-Net, and every fit was scored '
    'on 24 regions never used for selection, fitting or calibration. Farthest-point (k-center) selection was the '
    'weakest of eight base rules in two complete executions on different hardware, and its picks were the most '
    'atypical in the candidate pool. Requiring one image per region before any second pick raised equal-region '
    'mean intersection over union by 1.68 points (95% region-bootstrap interval 0.86 to 2.51) and by 2.24 points in '
    'the re-execution, and region-balanced facility location gained 1.35 points over its unweighted form. Equalizing '
    'label counts left the quota gain intact. Placebo groups showed that much of the benefit comes from interrupting '
    'the search for extremes. At small budgets, images should be spread across places first and chosen to be typical '
    'within them.')

HIGHLIGHTS_FINDINGS = [
    'With 12 training images, farthest-point (k-center) selection picked the most atypical images and was the weakest '
    'of eight label-free rules in two complete executions.',
    'A per-region quota raised mIoU on 24 unseen regions by 1.68 and 2.24 points; the gain did not depend on '
    'labeled-pixel counts.',
]
HIGHLIGHTS_IMPLICATIONS = [
    'Source-region metadata is a free and effective guide for spending very small annotation budgets.',
    'At small budgets, spread images across places first and choose typical images within each place.',
]

KEYWORDS = ('land cover segmentation; training image selection; geographic diversity; low-budget active learning; '
            'k-center; facility location; placebo control; OpenEarthMap')

INTRO = [
    'Every land cover map that is trained rather than handcrafted begins with a small decision that is easy to '
    'underrate: which images to label first. Annotation of high-resolution imagery is slow, and the first round of '
    'labels often has to serve a model that will be used far from where those labels were made. OpenEarthMap shows the '
    'scale of the problem. Its 5000 images come from 97 regions in 44 countries, and the same eight classes look very '
    'different in Kampala, Paris and the Peruvian Andes [@xia2023]. With a budget of a dozen images, a team can afford '
    'roughly one image per city it has data for, and the choice of that dozen shapes what the model learns about the '
    'world.',

    'The standard answer is to choose a diverse subset. Core-set selection makes this concrete: embed every candidate '
    'with a pretrained network and repeatedly add the candidate farthest from those already chosen, so that the chosen '
    'set covers feature space with the smallest possible radius [@sener2018]. Related objectives, such as facility '
    'location, reward representativeness rather than reach [@wei2015], and Nogueira et al. recently showed that '
    'image-based core-set rules can be competitive for land cover segmentation [@nogueira2026]. There is, however, a '
    'quiet assumption in the farthest-point idea. Far from everything else is not the same as informative. At very '
    'small budgets, the candidates that lie farthest from the rest are often the unusual ones: a container port among '
    'suburbs, a scene dominated by water, a tile with a different sensor or sun angle. Hacohen et al. made a related '
    'observation in image classification and argued that low budgets call for typical examples, whereas large budgets '
    'reward unusual ones [@hacohen2022]. Whether this reversal matters for remote-sensing segmentation, where the '
    'unusual images also tend to cluster in particular source regions, has not been examined.',

    'Remote-sensing archives offer a second notion of diversity at no cost: we usually know where each image came from. '
    'Source-region metadata can be used to spread a budget across places, either with a hard quota that admits a second '
    'image from a region only after every region has supplied one, or with a soft objective that gives each region '
    'equal weight. Geographic composition is known to matter when models move between regions [@alemadi2025], spatial '
    'structure has been built into sampling and active learning for segmentation and crop mapping [@cai2021; '
    '@kaijage2024], and sampling designs based on geocomplexity or prior maps have improved operational mapping '
    '[@he2024; @lu2025]. Group-balanced objectives are also standard in submodular selection [@wang2024; @rafiey2024]. '
    'What is missing is a controlled test of whether geographic allocation helps when it is the only extra information '
    'a label-free selector receives, and, if it helps, why.',

    'The why is the difficult part, because at least three unremarkable explanations compete with the interesting one. '
    'First, any constraint that interrupts farthest-point selection might help, whether or not the groups it balances '
    'have anything to do with geography. Second, a rule may win simply because its images contain more labeled pixels. '
    'Third, with a few dozen fits, one lucky source split or one noisy training run can produce a convincing-looking '
    'difference. We designed the study around these alternatives. Each geographic rule has a placebo twin that applies '
    'the same mechanism to size-matched groups with shuffled membership. A separate experiment holds the number of '
    'available training labels fixed. Three source allocations rotate 24 development regions through training, '
    'validation and disuse, all scores come from 24 further regions that played no other role, and the eight base '
    'rules were executed twice, once on a CPU and once on a GPU.',

    'The results tell a consistent story about where diversity goes wrong and a more cautious one about why geography '
    'helps. Our contributions are as follows:',
]

CONTRIBUTIONS = [
    'We show that farthest-point coverage is the weakest of eight label-free rules for training a segmentation network '
    'from 12 images, in two complete executions, and that its picks are the most atypical of the candidate pool.',
    'We show that a geographic quota repairs most of this weakness (+1.68 and +2.24 mIoU points in the two executions) '
    'and that region-balanced facility location improves on its unweighted form; in a frozen-feature control, the '
    'quota’s gain peaks where the budget equals the number of source regions.',
    'We separate allocation from region identity with size-matched placebo groups and from label quantity with an '
    'equal-label experiment, and we report which effects survive these controls and which do not.',
    'We release the complete record of 576 main fits, 72 re-executed fits and 27 equal-label fits, with per-image '
    'confusion matrices, so that every number in this paper can be recomputed.',
]

M21 = [
    'We used 192 image–mask pairs from 48 OpenEarthMap regions with the dataset’s eight land cover classes: '
    'bareland, rangeland, developed space, road, tree, water, agriculture and building [@xia2023]. The regions play two '
    'roles that never overlap (Figure 2). Twenty-four development regions contribute five images each (120 images). They '
    'supply candidate pools, calibration data and validation data. Twenty-four panel regions contribute three images '
    'each (72 images) and are used only to score fitted models. Panel regions and their image identities were fixed '
    'by a seeded filename rule before any panel image was opened. The development regions had served in an earlier '
    'frozen-feature round of this project, in which eight of them were test regions and the quota effect was '
    'inconclusive. We therefore retired all of them to development and drew the new panel, so that no image that had '
    'informed an earlier judgement is used for scoring here.',

    'Three cyclic source allocations assign each development region to source training, source validation or disuse '
    '(Figure 2b). Each allocation has 12 training regions (60 images), four validation regions (20 images) and eight '
    'unused regions. Repeating the study over three allocations means that a result cannot rest on one fortunate '
    'choice of source regions. RGB images were resized bilinearly and masks by nearest neighbor to 448 × 448 '
    'pixels; mask value 0 (void) was ignored throughout. A data screen checked file hashes, decoded-image duplicates '
    'and, where GeoTIFF metadata allowed, overlap between the WGS84 envelopes of images in different roles. It found no '
    'duplicates and no overlap among 8449 supported comparisons. Two images carry a coordinate-system caution '
    '(one in Aachen, one in Monrovia), and we report a sensitivity analysis without the Monrovia panel region. Source '
    'attribution and licence status for every region are listed in the Supplementary Material.',
]

M22 = [
    'Each allocation defines two 36-image candidate pools drawn from its 12 training regions. The balanced pool has '
    'three images per region. The skewed pool has five images from each of six regions and a single image from each of '
    'the other six, which mimics an archive in which some places are well documented and others barely. Pool '
    'membership was drawn once per allocation with a fixed seed, without reference to masks. The main comparison uses '
    'the skewed pool and a budget of B = 12 whole images, so that one image per region is possible but not automatic. '
    'A frozen-feature control adds budgets of 6 and 24 and the balanced pool.',

    'The budget counts the images whose masks enter each fit. It does not count the labels that every rule shares: '
    'the 24-image calibration sample and the 20 validation images of each allocation. Our comparisons are therefore '
    'relative comparisons among selection rules under shared development resources, not estimates of what a complete '
    'workflow could achieve with 12 labels.',
]

M23 = [
    'All rules receive the same inputs: unit-normalized DINOv2-S/14 class-token descriptors of the candidate images '
    '[@oquab2024], their source-region labels, the budget and a seed. No rule sees a mask, a class count, a validation '
    'score or a panel image. Table 1 lists the ten rules, and Figure 3 shows on simulated data how the four central '
    'ones behave.',

    'Five rules use the descriptors only. Random selection samples without replacement. Visual k-center starts from a '
    'seeded random image and then repeatedly adds the candidate whose cosine distance to its nearest chosen image is '
    'largest [@sener2018]. k-means++ seeding draws each new image with probability proportional to its squared '
    'distance to the chosen set and therefore prefers distant images without insisting on them [@arthur2007]. '
    'Facility location greedily maximizes the summed similarity of every candidate to its closest chosen image, with '
    'similarity (cos + 1)/2, so that it favors images that represent many others [@wei2015]. A feature-cluster round '
    'robin forms 12 k-means clusters and draws from them in turn; it adapts the feature-diversity rule of Nogueira et '
    'al. to our common descriptors [@nogueira2026].',

    'Three rules add the region labels. Geo-quota random and geo-quota k-center restrict each step to the regions with '
    'the fewest picks so far among those with candidates left; the first then draws at random and the second takes the '
    'farthest eligible image. At B = 12 both therefore take exactly one image from every training region. '
    'Geo-weighted facility location keeps the facility-location objective but weights each covered candidate by '
    '1/(R nᵣ), where R is the number of regions and nᵣ the number of candidates from region r, so that every '
    'region contributes equally to the objective whatever its size [@wang2024; @rafiey2024]. It balances influence, '
    'not counts.',

    'The last two rules are placebos. Placebo-quota k-center and placebo-weighted facility location run exactly the '
    'same procedures after the region labels have been shuffled across candidates in a way that preserves every group '
    'size; each selection seed uses one fixed shuffle. A placebo keeps the mechanism, the group sizes and, for the '
    'weighted rule, the multiset of weights, but breaks the link to real places. If a geographic rule beats visual '
    'k-center only because any grouping interrupts the farthest-point search, its placebo should do almost as well.',
]

M24 = [
    'The main model is a trainable segmentation network: an ImageNet-pretrained ResNet18 encoder [@he2016] with a '
    'U-Net-style decoder [@ronneberger2015] of four blocks (128, 64, 32 and 16 channels, two 3 × 3 convolutions with '
    'group normalization and ReLU each) and an eight-class output layer. All 12,456,328 parameters are trained, with '
    'encoder batch-normalization statistics frozen at their pretrained values. Each step draws two random 224 × '
    '224 crops from the selected images, with horizontal and vertical flips and a random quarter rotation, and '
    'minimizes cross-entropy over non-void pixels with AdamW (β = 0.9, 0.999; weight decay 10⁻⁴) '
    '[@loshchilov2019]. The decoder learning rate is ten times that of the encoder.',

    'Learning rate and step count were calibrated separately for each allocation on its own 24-image random sample and '
    '20 validation images, over encoder rates of 1 × 10⁻⁴ and 3 × 10⁻⁴ and 300, 600 or '
    '1200 steps. The chosen settings (source0: 3 × 10⁻⁴, 600 steps; source1: 1 × 10⁻⁴, '
    '1200 steps; source2: 1 × 10⁻⁴, 600 steps) are shared by every rule within an allocation, so no rule '
    'receives a recipe tuned for it. These short schedules are deliberate: they reflect the small-data regime and keep '
    'the 90 complete-model fits affordable on a laptop GPU, but they also cap absolute accuracy.',

    'The frozen-feature control fits a 128-unit MLP head (50,312 parameters) to 384-channel DINOv2 patch features on a '
    '32 × 32 grid [@oquab2024]. Targets are the class fractions of each grid cell computed from the native masks; '
    'cells with less than half valid coverage are skipped. The head is trained for 600 AdamW steps of 4096 sampled '
    'cells at a learning rate of 10⁻³. Because it is cheap, this control can cover both pools and budgets of '
    '6, 12 and 24. The two recipes differ in encoder, pretraining, decoder, targets and augmentation, so we compare '
    'selection rules within each recipe and never treat the recipe difference as a controlled effect.',
]

M25 = [
    'Every condition was fitted for three source allocations and three paired selection and initialization seeds, '
    '(0, 0), (1, 1) and (2, 2), giving nine fits per condition (Table 2). The main matrix contains 90 complete-model '
    'fits (ten rules, skewed pool, B = 12) and 486 frozen-feature fits, 576 in total. The weighted rules exist only in '
    'skewed pools, because with equal region sizes their objective is identical to ordinary facility location.',

    'The execution history matters for interpretation, so we state it plainly. The data partition, panel, candidate '
    'pools, selections, calibrated settings, main contrast and metric were all fixed before any panel score was '
    'computed; the geo-weighted rule and its placebo were added to the plan at the same stage. The complete-model '
    'fits were first run on a CPU. When 72 of the 90 fits, all eight base rules for all nine allocation–seed '
    'pairs, had finished and their panel scores had been seen, the remaining work was moved to an NVIDIA RTX 4060 '
    'laptop GPU for speed, and all 90 identities were executed there with the same selections, seeds and settings. We '
    'use the GPU series as the main analysis because it is the only complete one. Because the switch happened after '
    'panel exposure, we present the main contrast as a descriptive estimate rather than a confirmatory test. The 72 '
    'CPU fits are an unplanned but useful asset: a second complete execution of the eight base rules. GPU training is '
    'not bit-reproducible, and the same identity scored on the two backends differed by 1.7 points (standard '
    'deviation over 72 identities), which gives a direct measure of run-to-run noise.',
]

M26 = [
    'In the full-label fits, rules can differ in how many valid labels their 12 images contain. To remove this '
    'difference, we refitted visual k-center, geo-quota k-center and placebo-quota k-center for all nine '
    'allocation–seed pairs with exactly 2,300,000 available training labels per fit, a value just below the '
    'smallest count among all 90 complete-model selections (2,303,273). For each fit, the excess labels were hidden '
    'by a seeded uniform draw without regard to class, and everything else (images, order, crops, augmentation stream, '
    'steps and evaluation masks) was kept as in the full-label fit. This equal-label experiment (27 fits) was '
    'specified after panel exposure and is descriptive. As Section 3.4 shows, it turned out to be a very small '
    'intervention, and we interpret it as such.',
]

M27 = [
    'For each fit and panel region we summed the confusion matrices of the region’s three images and computed '
    'class intersection over union (IoU). The main metric is union-class mIoU, which averages over every class present '
    'in the reference or the prediction and so penalizes classes that are predicted but absent. The equal-region score '
    'averages the 24 regional values, so that a region counts the same whatever its pixel count. A truth-present '
    'variant, which averages only over classes present in the reference, is reported as a sensitivity analysis.',

    'Regions are the units of geographic uncertainty [@roberts2017]. For a contrast between two rules, we averaged '
    'the nine fits within each region, formed 24 paired regional differences and computed a 95% percentile interval '
    'from 10,000 paired bootstrap resamples of regions (seed 2026101805). The interval describes variation across '
    'this fixed panel of regions given the recorded fits; it does not include run-to-run training noise. To show '
    'that noise, we also report how many of the nine allocation–seed pairs favor each rule, the three '
    'allocation-specific means, leave-one-region-out ranges and the CPU re-execution. Contrasts other than the main '
    'one are secondary and are not corrected for multiplicity, and an interval that includes zero is not read as '
    'evidence of no effect. Intervals for secondary contrasts were computed with the same procedure and seed.',

    'To describe what the rules selected, we recorded three properties of every complete-model selection: the number '
    'of the 12 training regions represented, the number of picks taken from one-image regions, and the excess '
    'atypicality of the picks. The atypicality of a candidate is its mean cosine distance to the other 35 candidates '
    'of its pool, in the descriptor space the rules used; excess atypicality is the mean over the 12 picks minus the '
    'mean over the pool. These diagnostics were defined after the results were known and are used only to describe '
    'the selections.',
]

R31 = [
    'The clearest result is negative and concerns the rule that is most often recommended for diversity. Visual '
    'k-center reached 17.84% equal-region mIoU in the main GPU series and 16.86% in the CPU re-execution, the lowest '
    'value among the eight base rules in both (Table 3 and Figure 4a). Even random selection did better (18.91% and '
    '19.77%), and so did k-means++ seeding, which draws distant images only probabilistically, and facility '
    'location, which rewards representativeness instead of reach (Table 4). The rest of the ranking was less stable. Geo-quota random was highest in the GPU series (21.41%), '
    'whereas k-means++ was highest on the CPU (20.82%, against 20.58% for geo-quota random); the two executions differ '
    'by about as much as these rules differ from each other.',

    'Absolute scores are low, between 16.9% and 21.4%. Three features of the design explain this: each model learns from '
    '12 images with a short calibrated schedule, every score comes from regions the model never saw, and the '
    'union-class metric charges a full zero for every class that is predicted but absent. The scores are not '
    'comparable with OpenEarthMap benchmark results, and the comparison between rules, not the level, is the object '
    'of the study. Fixed qualitative examples are shown in the Supplementary Materials (Figure S3).',
]

R32 = [
    'Requiring one image per region before any second pick lifted visual k-center from last place to the middle of '
    'the GPU ranking (fifth of ten); on the CPU, where the other rules lay closer together, it moved up but stayed '
    'below random selection. Geo-quota k-center exceeded visual k-center by 1.68 points (95% region-bootstrap interval 0.86 '
    'to 2.51; Table 4 and Figure 4b). The gain was positive in 20 of the 24 panel regions (Figure 4c) and in seven of '
    'the nine allocation–seed pairs, and it stayed between 1.50 and 1.89 points when any one region was left '
    'out. It held without Monrovia (+1.58; 0.75 to 2.41) and under the truth-present metric (+2.28; 1.34 to 3.23). '
    'The CPU re-execution gave +2.24 (1.39 to 3.16; 21 of 24 regions).',

    'The gain did depend on the source allocation. It was +3.48 points in source0 and +2.09 in source2 but '
    '−0.54 in source1, where visual k-center was unusually strong. We therefore read the result as a reliable '
    'average advantage over regions rather than a guarantee for every set of source regions.',

    'The soft form of allocation showed the same pattern. Geo-weighted facility location exceeded ordinary facility '
    'location by 1.35 points (0.59 to 2.10), in all three allocations (+2.43, +0.77 and +0.85) and in 18 of 24 '
    'regions. It reached 21.24% while drawing images from 11.3 of the 12 regions on average, without a hard count '
    'constraint. Geography did not, however, make k-center better than facility location: geo-quota k-center '
    'remained 0.37 points below ordinary facility location on the GPU (−1.01 to 0.25) and 0.71 points below it on '
    'the CPU.',
]

R33 = [
    'The placebo twins ask what the geographic labels contribute beyond the act of grouping. For the soft rule, the '
    'answer is clear. Geo-weighted facility location exceeded its placebo by 2.13 points (1.26 to 2.98; 21 of 24 '
    'regions), and the placebo fell below ordinary facility location (19.11% against 19.89%). Equal weight for real '
    'places helped; equal weight for arbitrary groups did not.',

    'For the hard quota, the answer is less clear. Geo-quota k-center exceeded placebo-quota k-center by 0.90 points '
    'on the GPU (0.34 to 1.45; 18 of 24 regions), but only by 0.13 points on the CPU (−0.33 to 0.60; 13 of 24). '
    'Meanwhile, the placebo quota itself beat visual k-center in both executions (+0.78 and +2.12 points), although it '
    'represented no more real regions than random selection (7.6 of 12). A shuffled quota cannot spread picks across '
    'real places, so its gain must come from somewhere else. Section 3.5 shows where: any quota interrupts the '
    'farthest-point chain and so stops k-center from taking the most extreme images.',
]

R34 = [
    'Labeled pixel counts are an unlikely explanation for differences between rules, because the selections hardly '
    'differed in them: across all 90 complete-model selections, valid processed labels ranged only from 2.30 to 2.41 '
    'million. Across the 27 selections in the equal-label experiment, the available training labels ranged from 2.30 to 2.41 million, '
    'and the rule means differed by less than 0.01 million (Figure 5a). Reaching exactly 2.30 million therefore '
    'required hiding only 1.2–3.5% of the labels for visual k-center, 1.4–3.9% for geo-quota k-center and '
    '0.1–4.5% for the placebo quota.',

    'After this small change, geo-quota k-center still exceeded visual k-center by 2.00 points (1.19 to 2.83; 23 of '
    '24 regions), and the paired change from the full-label contrast was +0.32 points (−0.13 to 0.74; Table 4 and '
    'Figure 5c). The gap between real and placebo quotas, in contrast, fell from 0.90 to 0.25 points (−0.19 to '
    '0.69), a paired change of −0.65 (−1.05 to −0.26). Hiding a few percent of labels cannot plausibly '
    'remove a real effect of region identity of that size, so we read this as a third sign, after the CPU '
    're-execution and the source-specific estimates, that the quota’s advantage over its placebo is fragile, '
    'whereas its advantage over visual k-center is not. The interval for the paired change excludes zero although the '
    'intervention was minimal, which also shows that region-bootstrap intervals understate the total uncertainty when '
    'training noise is ignored.',
]

R35 = [
    'Figure 6 describes what each rule actually picked. Two properties separate the rules. The first is breadth. Only '
    'the three geographic rules reached all, or nearly all, of the 12 training regions (12.0, 12.0 and 11.3), and all '
    'three took an image from each of the six one-image regions. The other rules represented 7.3 to 8.0 regions. The '
    'second is typicality. The 12 images chosen by visual k-center were, on average, 0.059 cosine units more atypical '
    'than an average candidate. That was the largest excess of all rules and twice that of geo-quota k-center '
    '(0.029). The placebo quota lay in between (0.040), which is consistent with the account above: a quota of any kind '
    'removes some of the extreme picks, but only a quota on real regions adds breadth. Geo-quota random combined '
    'breadth with essentially no excess atypicality (−0.0004).',

    'Across the ten rules, mean mIoU fell as excess atypicality rose (Spearman ρ = −0.55; Figure 6c). With ten '
    'rules that were not chosen to vary along this axis, this is a description rather than a test, but it matches the '
    'direction seen in the CPU re-execution (ρ = −0.76 over its eight rules). It is not a strict ordering: '
    'facility location had the third-largest excess atypicality yet scored well. The two highest-scoring rules in the '
    'GPU series are the two that combine full or near-full geographic breadth with low atypicality.',
]

R36 = [
    'The frozen-feature control shows when allocation matters (Figure 7). In both pools, geo-quota k-center gained '
    'most over visual k-center at B = 12, the budget at which the quota assigns exactly one image per region: +0.90 '
    'points in the balanced pool and +1.33 in the skewed pool, with region-bootstrap intervals excluding zero in both. '
    'At B = 6 the quota can cover only half of the regions and the differences were small (−0.24 and +0.17). At '
    'B = 24 visual k-center already takes two thirds of the pool, so there is little left for any rule to change '
    '(+0.17 and +0.32). Weighted facility location gained little in the frozen skewed pool (+0.32, +0.45 and '
    '+0.03 over ordinary facility location), but none of these intervals excluded zero.',

    'Two differences from the complete model are worth stating. With frozen features, visual k-center was never worse '
    'than random selection by more than 0.3 points (Figure 7b), so the penalty for atypical picks appears to depend on the training recipe: a '
    'network that updates its encoder on 12 images may be more easily misled by a few unusual ones than a small head on '
    'fixed features. Frozen scores were also 4.4 to 7.1 points higher than complete-model scores for the same rules, '
    'which reflects the stronger fixed representation and the coarser target grid rather than anything about selection.',
]

D41 = [
    'Diversity is usually treated as an unqualified good in data selection. Our results suggest that at a budget of a '
    'dozen images, what farthest-point selection actually delivers is unusualness. Visual k-center chose the most '
    'atypical images and scored lowest in both executions, below random selection, whereas rules that soften the '
    'farthest-point criterion (k-means++ seeding) or replace it with representativeness (facility location) did '
    'markedly better. This is the low-budget '
    'regime described by Hacohen et al. for classification [@hacohen2022], now observed for segmentation of aerial '
    'imagery evaluated in unseen regions. It also fits a broader lesson from realistic evaluations of active learning: '
    'which selection rule is best depends on the budget and training setup [@mittal2025].',

    'Geography helps because it changes what "diverse" means. A quota defines diversity over places rather than over '
    'descriptor distance. Visual k-center did reach some one-image regions, which tend to be visually isolated, but it '
    'also stacked several picks into some regions and left others out, representing 7.7 of 12 regions on average. '
    'Forcing one image per region addresses both problems at once: it guarantees breadth, and it limits how many '
    'extreme images any single region can contribute. '
    'The placebo results show that the second part does not need real geography; the first part does.',
]

D42 = [
    'We set out to ask whether the identity of the regions matters, and the honest answer has two parts. For the soft '
    'rule, it clearly does: geo-weighted facility location beat both ordinary facility location and its placebo, and '
    'it did so in every allocation. For the hard quota, real regions beat placebo groups in the main GPU series, but '
    'the margin shrank to near zero on the CPU and after a minimal label change. Much of what the quota adds over '
    'visual k-center can therefore be explained by interrupting the farthest-point search: about half of the gain in '
    'the GPU series (0.78 of 1.68 points) and nearly all of it on the CPU (2.12 of 2.24). The rest, less certain, '
    'may come from covering real places. More panel regions or more seeds would be needed to settle it.',

    'The asymmetry between the two contrasts is itself informative. A contrast against a weak baseline (visual '
    'k-center) survived every check we could apply. A contrast between two reasonable rules (real versus placebo '
    'quota, or geo-quota k-center versus facility location) was of the same order as the run-to-run noise of 1.7 points '
    'per fit. Studies of selection rules with few fits should expect this and should report re-executions or fit-level '
    'agreement alongside region-level intervals. Region bootstraps capture geographic variation but are blind to the '
    'noise of training itself.',
]

D43 = [
    'For a team that must choose a first batch of images for a new mapping task, our results support three simple '
    'practices. First, do not use farthest-point coverage alone at very small budgets. If it is used, put a geographic '
    'allocation in front of it. Second, when source regions are known, allocate the budget across them first and then '
    'choose representative images within each region. The plainest version, one random image per region, was among the '
    'best rules in both executions and needs no descriptors at all; geo-weighted facility location is a good choice '
    'when exact counts per region are not required. Third, the benefit is largest when the budget is close to the '
    'number of regions. When the budget is much smaller, it matters which regions are left out; when it is much '
    'larger, most rules converge.',

    'These recommendations are cheap to follow. Source identifiers are part of almost every remote-sensing archive, '
    'and the rules take milliseconds. They also fit naturally in front of iterative active learning, where the first '
    'batch must be chosen before any model exists.',
]

D44 = [
    'Several limits apply. The panel has 24 purposively chosen regions with three images each, and the development '
    'side has three allocations of one 24-region set with one candidate pool per allocation and profile. The '
    'intervals describe this panel and these recorded fits, not a population of regions. The complete-model analysis '
    'became descriptive when the execution backend changed after panel exposure, and the equal-label experiment and the '
    'selection diagnostics were added after results were known. The budget counts only the images in each fit; '
    'calibration and validation labels were shared resources. Equal label counts are not equal annotation effort, '
    'which we did not measure. All scores refer to 448 × 448 resampled images and short training schedules, so we '
    'make no claim about boundary quality at native resolution, long training or larger networks. Finally, "unseen" '
    'means unseen during selection, fitting and calibration; the images may still overlap with the data used to '
    'pretrain ResNet18 or DINOv2.',

    'The most useful next steps follow directly from these limits: more panel regions to narrow the real-versus-placebo '
    'question, several candidate pools per allocation, budgets measured in annotation time, and tests with stronger '
    'segmentation networks and longer schedules.',
]

CONCLUSION = [
    'When a land cover model must be trained from a dozen images, diversity in feature space mostly buys outliers. In '
    'our study, farthest-point selection chose the most atypical images and was the weakest of eight label-free rules '
    'in two complete executions. Spreading the budget across source regions repaired most of that loss: geo-quota '
    'k-center gained 1.68 and 2.24 mIoU points in the two executions, region-balanced facility location gained 1.35 '
    'points over its unweighted form, and the quota gain survived an equal-label test. Placebo groups showed '
    'that part of the benefit of a hard quota comes simply from interrupting the search for extremes, while equal '
    'weight for real regions clearly helped the facility-location objective. The practical message is short: at small '
    'budgets, visit every region first, and choose typical images when you get there.',
]

SUPP = ('The following supporting information accompanies this article: execution sets and backend history; region '
        'roles and panel image identities; candidate pools and selection objectives; training recipes and '
        'calibration; regional estimand and metric sensitivity; source-specific contrasts for all 64 conditions; the '
        'equal-label control; complementary figures; data attribution and licences; and the complete condition '
        'matrix; and fixed qualitative examples (Tables S1–S11, Figures S1–S3).')

BACK = [
    ('Author Contributions', 'To be completed by the authors using the CRediT taxonomy. No roles are inferred here.'),
    ('Funding', 'To be completed by the authors.'),
    ('Data Availability Statement',
     'OpenEarthMap is available from https://doi.org/10.5281/zenodo.7223446 under the licences of its individual '
     'sources. The accompanying research archive is openly available at '
     'https://github.com/Kasseiss/geo-quota-selection and contains the image identities, provenance records, '
     'configurations, selection and training code, per-image confusion matrices, training logs, all result tables '
     'and the code that draws every figure in this article. Raw RGB imagery and label masks are not redistributed '
     'under a single licence; retrieval scripts, a per-region attribution register and a manifest identifying every '
     'image are provided instead. No new primary data were collected.'),
    ('Use of Generative AI',
     'OpenAI Codex assisted with study planning, software, experiment execution and analysis, and Anthropic Claude '
     'assisted with figure preparation and manuscript editing. All numerical results come from recorded experiment '
     'outputs. The authors reviewed all content and take full responsibility for it.'),
    ('Conflicts of Interest', 'To be completed by the authors.'),
]

CAPTIONS = {
    'fig1': ('The study in one picture, drawn from recorded data. (a) The 36-image skewed candidate pool of source0 '
             'placed by the first two principal components of the DINOv2 descriptors the rules use; frame colours '
             'mark the 12 source regions, and the squares below show that six regions offer five candidates and six '
             'offer one. (b) The recorded 12-image selections of visual k-center, geo-quota k-center and placebo-quota '
             'k-center for source0 and seeds (0, 0); lines follow the pick order and the bars count picks per region. '
             '(c) Only after a list is fixed are its masks released for training the ResNet18 U-Net. (d) Every fit is '
             'scored on 24 panel regions; bars under the tiles give the nine-fit regional difference of the main '
             'contrast.'),
    'fig2': ('Geographic design. (a) Locations of the 24 development regions (wedge glyphs) and the 24 panel regions '
             '(stars). Development locations are centres of supported tile envelopes; panel locations average the '
             'WGS84 envelopes of their three images. Land outline: Natural Earth. (b) The roles of the development '
             'regions in the three source allocations (T, training; V, validation; U, unused).'),
    'fig3': ('How the four central rules behave, on simulated two-dimensional descriptors (illustration only, not '
             'experimental data). Four regions offer five images and four offer one; dashed rings mark three visually '
             'extreme images; numbers give the pick order at a budget of eight. Visual k-center chases the extremes and '
             'piles picks into the large regions. The geographic quota reaches every region but, being a k-center rule, '
             'still takes the extremes within the eligible regions. The placebo quota spreads picks over a shuffled '
             'partition and misses real regions. Geo-weighted facility location reaches every region with '
             'representative images.'),
    'fig4': ('Complete-model results at B = 12 in skewed pools. (a) Equal-region union-class mIoU of the ten rules: '
             'open markers are the nine GPU fits (shape by source allocation), diamonds their mean, bars ± one fit '
             'standard deviation, and black stars the mean of the CPU re-execution of the eight base rules. The '
             'right-hand columns give the mean and the mean number of training regions represented. (b) Paired '
             'contrasts with 95% region-bootstrap intervals, allocation-specific means (grey) and, where available, '
             'the CPU re-execution (black). (c) The main contrast in each of the 24 panel regions, sorted, with the '
             'three allocation-specific values.'),
    'fig5': ('The equal-label experiment. (a) Valid processed training labels in each of the 27 selections, with the '
             'share that had to be hidden to reach 2.30 million. (b) Rule means with all labels and with 2.30 million '
             'labels; thin lines join the nine paired fits. (c) Contrasts with all labels (open) and with 2.30 '
             'million labels (filled), with the paired change. The bottom row is computed post hoc with the same '
             'bootstrap.'),
    'fig6': ('What the rules picked, described post hoc for the 90 complete-model selections. (a) Number of training '
             'regions represented against excess atypicality of the picks (mean cosine distance of a pick to the rest '
             'of its pool, minus the pool mean); fill shows mIoU. (b) Picks from five-image regions (grey) and from '
             'one-image regions (colour). (c) mIoU against excess atypicality across the ten rules.'),
    'fig7': ('When allocation matters. (a) Paired contrasts (mIoU points) with 95% region-bootstrap intervals for the '
             'frozen-feature control in both pools and all budgets, and for the complete model; outlined cells have '
             'intervals that exclude zero. (b) Frozen-control rule means relative to random selection; the shaded '
             'budget assigns exactly one image per source region.'),
}

TABLE_NOTES = {
    'policies': 'All rules receive the same DINOv2 descriptors, region labels, budget and seed, and no masks, class '
                'counts or scores. Placebo rules use size-preserving shuffles of the region labels.',
    'matrix': 'Each condition has three source allocations × three paired seeds. The CPU re-execution and the '
              'equal-label fits are separate series and are never pooled with the main matrix.',
    'results': 'Means over nine fits; SD is the fit standard deviation (not a geographic interval). Worst region: mean '
               'of each fit’s lowest regional score. Regions: training regions represented among the 12 picks. '
               'One-image: picks from the six one-image regions. Atypicality: mean excess cosine distance of the picks. '
               'The weighted rules were not part of the CPU execution.',
    'contrasts': 'Differences in mIoU points with 95% paired region-bootstrap intervals; "regions" counts the 24 panel '
                 'regions favouring the first rule. The main contrast is the first row; the rest are secondary. Intervals '
                 'not stored in the result tables were recomputed with the same procedure and seed.',
}
