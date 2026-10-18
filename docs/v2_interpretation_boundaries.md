# V2 interpretation boundaries for final manuscript review

Compiled while the frozen formal matrix was running, from its existing protocol and execution code. This is an explanatory checklist, not a new prospective analysis plan. It changes no execution, metric, sampling rule, contrast or release criterion, and contains no new-panel performance conclusion.

## What the budget measures

The matched budget is the number of complete source images used in one formal fit:6/12/24 for frozen heads and12 for the complete spatial model. It is not measured annotation time, equal native ground area, equal valid-pixel count or the total label cost of the study. Native image dimensions, valid coverage and class composition can differ. Selected native valid-pixel and class counts are recorded after selection in each result; none is supplied to the selector.

All120 historical images are development data in V2. Each source allocation has12 training regions with5 images each, four validation regions with5 images each and eight unused development regions. Each formal candidate pool has36 of the60 training images. Complete-model calibration uses a24-image balanced-pool sample and all20 source-validation images; these shared resources are outside the formal per-fit budget. The earlier experiments already used these labels. The study therefore compares subsets of an existing labelled benchmark, rather than demonstrating an end-to-end annotation campaign costing only12 images. DINOv2 and ImageNet pretraining are also external resources.

## What the two model recipes compare

Both recipes receive the same descriptor-based selected image IDs within a fixed condition. The complete model optimizes12,456,328 parameters with448-grid hard masks and224 random crops, spatial augmentation and source-calibrated constant learning rates/step counts. Its encoder BatchNorm affine parameters train while pretrained running statistics stay fixed. The common complete-model recipe is calibrated on a24-image balanced sample for each allocation and then held fixed across its formal B12 skewed-pool policies; it is not tuned independently for each policy. Recipes differ across source allocations, so full-model source heterogeneity combines source composition and the recorded source-specific calibration rule, rather than identifying a pure causal source-composition effect. No convergence beyond the finite calibration grid is established.

The frozen control uses normalized32x32 DINOv2 patch features of384 channels and a128-unit ReLU MLP with50,312 trainable parameters. Its source soft targets are native-mask class fractions adaptively pooled to32x32, normalized over valid classes. Cells with valid coverage below0.5 are excluded. Each of600 AdamW steps samples4096 retained cells with replacement; there is no crop augmentation. Test logits are bilinearly expanded to448 before argmax and are scored against the same448 nearest-resampled hard panel labels as the complete model.

Thus supervision aggregation, effective training observations, decoder, encoder family/pretraining, optimization and augmentation differ alongside encoder trainability. A cross-recipe contrast is a recorded sensitivity to the combined recipes, and cannot isolate a fine-tuning effect. Complete-image class availability in the source-only diagnostic neither guarantees appearance in actual224 crops nor measures retained DINO-cell target mass.

## What group and coverage controls identify

The groups are dataset source-region identifiers, not an inferred geographic distance metric. Sequential quota procedures need not yield equal final counts when a small group has exhausted its candidates; describe the implemented capacity-aware allocation and report actual selected counts. A fixed12-cluster feature-diversity adaptation is not a reproduction of an adaptive Vendi-selected-cluster baseline.

Real versus size-preserving permuted groups compares geographic alignment within the same quota procedure. Weighted real versus weighted permuted facility location additionally holds the weight multiset and coverage objective fixed. Weighted FL versus quota k-center changes the objective as well as the allocation rule, so it cannot by itself establish a causal effect of hard quotas versus soft weighting. Better source-feature coverage and target segmentation accuracy are different quantities. Each permuted policy uses one fixed size-preserving assignment per selection seed within its candidate pool. The three paired seed settings are negative-control fits, not an inferential permutation test or a sampled null distribution sufficient for a permutation p-value. Their group assignment and optimization variation are coupled by the recorded seed mapping.

## What uncertainty and geography support

The24 fixed panel regions, not the216 source-by-fit-by-region observations, define the primary paired bootstrap units after averaging nine fits within each region. The three cyclic source allocations overlap, and the three randomization repeats pair selection and optimization seeds. These do not supply independent draws of all possible source sets or separate variance components. The interval remains conditional on this purposive panel and recorded recipes.

The primary keeps24 regions. The prospectively fixed23-region Monrovia-excluded analysis addresses a specific metadata caution and is descriptive. No detected envelope overlaps or exact decoded duplicates proves only the checks performed; full upstream mosaic/provider/pretraining independence is unresolved. Resampling to448 changes the task relative to the native-resolution official benchmark.

## What may be claimed after completion

The primary contrast and all controls must be assessed together against the closest selection and geographic-transfer literature. Neither576 fits, a zero-crossing interval, a strong random baseline nor a well-formatted draft alone establishes a substantive contribution. A zero-crossing interval is not evidence of equivalence; no externally justified practical margin has been supplied. Any final positive, negative or heterogeneous claim must be bound to the actual completed evidence and its scope. Algorithms, backbone families and weighted objectives remain existing methods.

Source authorities: `docs/v2_protocol.md`; `configs/v2_design.json`; `configs/v2_extension.json`; `code/v2_run.py`; `code/cache_features.py`; `code/v2_segmentation.py`; `code/v2_selection.py`; `code/v2_weighted_selection.py`; `docs/v2_literature_matrix.md`. This register is not itself a substitute for reviewing those authorities or the final numerical outputs.
