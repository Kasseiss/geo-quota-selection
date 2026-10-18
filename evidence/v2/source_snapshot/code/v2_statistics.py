"""Reanalyse audited v2 per-image confusion matrices, without feature/model reads.

Only held-out geographic regions are bootstrap units. --self-test is entirely
synthetic/in-memory and does not read panel scores or create formal evidence.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import unittest

import numpy as np
from core import scores
from v2_audit_runs import (ROOT, KEYS, ADDITIONAL_STRATEGIES, assert_same, complete_aggregate, expected_matrix, paired_fit_matrix,
                           read_json, require, run_key, safe_path, sha_file,
                           validate_cm, write_json)

CONDITION_KEYS = ("model", "pool", "budget", "strategy")
FAMILY_KEYS = ("model", "pool", "budget")
METRICS = {"union_class_miou": "equal_region_union_miou", "truth_present_miou": "equal_region_miou"}
FIT_METRICS = ("equal_region_union_miou", "equal_region_miou", "pooled_union_miou",
               "pooled_truth_present_miou", "worst_region_union_miou", "worst_region_miou",
               "selected_region_count", "mean_candidate_cosine_distance", "maximum_candidate_cosine_distance",
               "equal_region_mean_candidate_cosine_distance",
               "selected_valid_original_pixels", "selection_seconds", "total_seconds")
CONTRASTS = (("region_kcenter", "kcenter"),
             ("region_kcenter", "permuted_region_kcenter"),
             ("region_kcenter", "facility_location"), ("region_kcenter", "fd_roundrobin"))
EXTENSION_CONTRASTS = (("region_weighted_facility_location", "facility_location"),
                       ("region_weighted_facility_location", "permuted_region_weighted_facility_location"))


def condition_key(identity):
    return tuple(identity[key] for key in CONDITION_KEYS)


def grouped_identities(design, extension=None):
    """Expected source-condition/family counts, derived rather than hand listed."""
    all_conditions, by_source = set(), set()
    for identity in expected_matrix(design, extension).values():
        key = condition_key(identity)
        all_conditions.add(key)
        by_source.add((*key, identity["source_split"]))
    return all_conditions, by_source


def describe(values):
    valid = [float(v) for v in values if v is not None]
    require(all(math.isfinite(v) for v in valid), "Nonfinite descriptive metric")
    return {"mean": float(np.mean(valid)) if valid else None,
            "sd": float(np.std(valid, ddof=1)) if len(valid) > 1 else None,
            "n": len(valid), "raw": values}


def paired_region_summary(a, b, *, repetitions=None, seed=None):
    require(set(a) == set(b) and len(a) >= 3, "At least three exactly matched geographic regions required")
    regions = sorted(a)
    differences = np.asarray([a[r] - b[r] for r in regions], dtype=float)
    require(np.isfinite(differences).all(), "Nonfinite paired geographic differences")
    result = {"difference": float(differences.mean()), "region_count": len(regions),
              "unit": "held-out geographic region; source allocations and fitting seeds averaged first",
              "regional_differences": [{"region": r, "a": float(a[r]), "b": float(b[r]),
                                         "difference": float(d)} for r, d in zip(regions, differences)],
              "leave_one_region_out": [{"omitted_region": r,
                    "difference": float((differences.sum() - d) / (len(regions) - 1))}
                    for r, d in zip(regions, differences)]}
    if repetitions is not None:
        require(isinstance(repetitions, int) and repetitions > 0 and isinstance(seed, int), "Invalid bootstrap specification")
        rng = np.random.default_rng(seed)
        boot = differences[rng.integers(0, len(regions), (repetitions, len(regions)))].mean(axis=1)
        result["bootstrap"] = {"method": "paired percentile region bootstrap",
            "repetitions": repetitions, "seed": seed, "lower": float(np.quantile(boot, .025)),
            "upper": float(np.quantile(boot, .975)), "level": .95}
    return result


def geographic_sensitivity_summary(a, b, config):
    """Filter whole regions after fit averaging; never alter primary support."""
    excluded = config.get("exclude_entire_regions")
    require(config.get("primary_unchanged") is True and
            config.get("purpose") == "descriptive_geographic_metadata_sensitivity" and
            isinstance(excluded, list) and bool(excluded) and
            all(isinstance(region, str) and region for region in excluded) and
            len(excluded) == len(set(excluded)), "Invalid descriptive geographic sensitivity")
    require(set(a) == set(b) and set(excluded) <= set(a),
            "Sensitivity exclusions must be present in both matched region sets")
    removed = set(excluded)
    result = paired_region_summary({r: value for r, value in a.items() if r not in removed},
                                   {r: value for r, value in b.items() if r not in removed},
                                   repetitions=config["repetitions"], seed=config["bootstrap_seed"])
    result.update(excluded_regions=sorted(removed),
                  role="descriptive_geographic_metadata_sensitivity_not_additional_confirmatory_test")
    return result


def make_fit(result):
    """Reconstruct every metric from CMs, not saved aggregate scalar scores."""
    identity = result["identity"]
    entries = result["test"]["images"]
    require(len(entries) == len({entry["id"] for entry in entries}), "Repeated image in fit")
    regional_cm = defaultdict(lambda: np.zeros((8, 8), dtype=np.int64))
    for entry in entries:
        regional_cm[entry["region"]] += validate_cm(entry["confusion"])
    aggregate = complete_aggregate(entries)
    assert_same(result["test"]["aggregate"], aggregate, "analysis aggregate")
    selection = result["selection"]
    metric = {"equal_region_union_miou": aggregate["equal_region_union_miou"],
              "equal_region_miou": aggregate["equal_region_miou"],
              "pooled_union_miou": aggregate["pooled_pixel_scores"]["union_class_miou"],
              "pooled_truth_present_miou": aggregate["pooled_pixel_scores"]["miou"],
              "worst_region_union_miou": min(v["union_class_miou"] for v in aggregate["regions"].values()),
              "worst_region_miou": aggregate["worst_region_miou"],
              "selected_region_count": len(selection["selected_regions"]),
              **{key: selection[key] for key in ("mean_candidate_cosine_distance", "maximum_candidate_cosine_distance",
                                                  "equal_region_mean_candidate_cosine_distance",
                                                  "selected_valid_original_pixels", "selection_seconds")},
              "total_seconds": result["total_seconds"]}
    return {"identity": identity, "metrics": metric, "regional": aggregate["regions"],
            "regional_cm": dict(regional_cm), "pooled_cm": sum(regional_cm.values())}


def average_regional(fits, metric):
    require(bool(fits), "No fits in condition")
    regions = set(fits[0]["regional"])
    require(all(set(f["regional"]) == regions for f in fits), "Mismatched regional support across fits")
    return {r: float(np.mean([f["regional"][r][metric] for f in fits])) for r in sorted(regions)}


def summary_rows(fits, group_keys):
    groups = defaultdict(list)
    for fit in fits:
        groups[tuple(fit["identity"][k] for k in group_keys)].append(fit)
    rows = []
    for key, members in sorted(groups.items()):
        members = sorted(members, key=lambda f: run_key(f["identity"]))
        row = dict(zip(group_keys, key))
        row.update(fits=len(members), source_allocations=len({f["identity"]["source_split"] for f in members}),
                   held_out_regions=len(members[0]["regional"]),
                    selection_seed_count=len({f["identity"]["selection_seed"] for f in members}),
                    initialization_seed_count=len({f["identity"]["initialization_seed"] for f in members}),
                    fit_seed_pairs=json.dumps(sorted({(f["identity"]["selection_seed"],
                        f["identity"]["initialization_seed"]) for f in members}), separators=(",", ":")),
                   fit_identities=json.dumps([{k: f["identity"][k] for k in
                       ("source_split", "selection_seed", "initialization_seed")} for f in members], separators=(",", ":")))
        for metric in FIT_METRICS:
            d = describe([f["metrics"][metric] for f in members])
            row[metric + "_mean"], row[metric + "_fit_sd"] = d["mean"], d["sd"]
            row[metric + "_raw_fits"] = json.dumps(d["raw"], separators=(",", ":"), allow_nan=False)
        rows.append(row)
    return rows


def detail_rows(groups):
    regions, classes = [], []
    for key, members in sorted(groups.items()):
        members = sorted(members, key=lambda f: run_key(f["identity"]))
        base = dict(zip(CONDITION_KEYS, key))
        for region in sorted(members[0]["regional"]):
            row = {**base, "region": region, "fits": len(members),
                   "images_per_fit": 3,
                   "evaluated_pixels": int(members[0]["regional"][region]["evaluated_pixels"])}
            for metric in ("union_class_miou", "miou"):
                values = [f["regional"][region][metric] for f in members]
                d = describe(values)
                row[metric + "_mean"], row[metric + "_fit_sd"] = d["mean"], d["sd"]
                row[metric + "_raw_fits"] = json.dumps(values, separators=(",", ":"))
            row["fit_identities"] = json.dumps([{k: f["identity"][k] for k in
                ("source_split", "selection_seed", "initialization_seed")} for f in members], separators=(",", ":"))
            regions.append(row)
        for cls in range(8):
            row = {**base, "class_index": cls, "fits": len(members)}
            pooled, regional_union, regional_truth, supports = [], [], [], []
            for fit in members:
                cm = fit["pooled_cm"]
                pooled.append(scores(cm)["class_iou"][cls])
                values_union, values_truth = [], []
                for cm_region in fit["regional_cm"].values():
                    class_iou = scores(cm_region)["class_iou"][cls]
                    if class_iou is not None:
                        values_union.append(class_iou)
                    if cm_region[cls].sum() > 0:
                        values_truth.append(class_iou)
                regional_union.append(float(np.mean(values_union)) if values_union else None)
                regional_truth.append(float(np.mean(values_truth)) if values_truth else None)
                supports.append(int(cm[cls].sum()))
            for name, values in (("pooled_class_iou", pooled), ("region_union_class_iou", regional_union),
                                 ("region_truth_present_class_iou", regional_truth), ("truth_pixels", supports)):
                d = describe(values)
                row[name + "_mean"], row[name + "_fit_sd"], row[name + "_defined_fits"] = d["mean"], d["sd"], d["n"]
                row[name + "_raw_fits"] = json.dumps(values, separators=(",", ":"), allow_nan=False)
            classes.append(row)
    return regions, classes


def fit_randomization(fits):
    pairs = sorted({(f["identity"]["selection_seed"], f["identity"]["initialization_seed"])
                    for f in fits})
    paired = pairs == [(0, 0), (1, 1), (2, 2)]
    return {"fit_seed_pairs": [list(pair) for pair in pairs],
            "policy": "Three paired selection/optimization seeds; not a Cartesian factorial" if paired else
                      "Historical selection repetitions at fixed initialization0",
            "selection_and_optimization_factors_separable": False,
            "randomization_amended_before_new_panel_scores": paired,
            "calibration_initialization_seed": 0}


def _build_analysis(fits, design, expected, geographic_sensitivity=None):
    """Pure analysis over an explicit matrix, also used by like-for-like tests."""
    expected_conditions = {condition_key(identity) for identity in expected.values()}
    expected_by_source = {(*condition_key(identity), identity["source_split"])
                          for identity in expected.values()}
    has_supplement = any(identity["strategy"] in ADDITIONAL_STRATEGIES for identity in expected.values())
    require(len(fits) == len(expected) and len({run_key(f["identity"]) for f in fits}) == len(expected),
            f"Analysis needs{len(expected)} unique fits")
    require({run_key(f["identity"]) for f in fits} == set(expected), "Fit matrix differs from design and supplement")
    groups = defaultdict(list)
    for fit in fits:
        groups[condition_key(fit["identity"])].append(fit)
    by_source = summary_rows(fits, (*CONDITION_KEYS, "source_split"))
    conditions = summary_rows(fits, CONDITION_KEYS)
    condition_count = 64 if has_supplement else 56
    require(len(conditions) == len(expected_conditions) == condition_count and
            len(by_source) == len(expected_by_source) == condition_count * 3,
            f"Expected{condition_count} conditions and{condition_count * 3} source conditions")
    require(all(row["fits"] == 9 for row in conditions) and all(row["fits"] == 3 for row in by_source),
            "Each condition must contain3 source allocations x3 fit-seed pairs")
    region_rows, class_rows = detail_rows(groups)
    primary_spec = design["primary"]
    primary_family = tuple(primary_spec[k] for k in FAMILY_KEYS)
    require(primary_family == (design["full_model"]["name"], "skewed5_1", 12) and
            primary_spec["contrast"] == ["region_kcenter", "kcenter"] and
            primary_spec["repetitions"] == 10000 and primary_spec["bootstrap_seed"] == 2026101805,
            "Primary specification differs from locked planned contrast")
    primary = {"format": "v2-primary-1", "specification": primary_spec,
               "interpretation": "Primary union-class result plus truth-present convention sensitivity; no equivalence or publication decision.",
               "fits_per_strategy": 9, "source_allocations": 3, "selection_seeds": 3,
               "initialization_seeds": len({f["identity"]["initialization_seed"] for f in fits}),
               "randomization": fit_randomization(fits),
               "geographic_replicates": 24, "metrics": {}}
    if geographic_sensitivity is not None:
        primary["geographic_sensitivity"] = {
            "purpose": "descriptive_geographic_metadata_sensitivity",
            "primary_unchanged": True, "configuration": geographic_sensitivity,
            "averaging_order": "Average all9 paired fits within each region, then exclude entire named regions",
            "metrics": {}}
    contrasts = []
    families = sorted({key[:3] for key in groups})
    for family in families:
        for a, b in (*CONTRASTS, *(EXTENSION_CONTRASTS if has_supplement else ())):
            # Only contrast strategies actually present in the reviewed sparse
            # matrix. In particular no balanced weighted-FL fits are invented.
            if (*family, a) not in expected_conditions or (*family, b) not in expected_conditions:
                continue
            left, right = groups[(*family, a)], groups[(*family, b)]
            row = {**dict(zip(FAMILY_KEYS, family)), "a": a, "b": b,
                   "role": "primary" if family == primary_family and [a, b] == primary_spec["contrast"] else "descriptive_secondary",
                   "origin": "prospective_weighted_fl_supplement" if (a, b) in EXTENSION_CONTRASTS else "original_design",
                   "metrics": {}}
            for name in METRICS:
                regional_metric = "union_class_miou" if name == "union_class_miou" else "miou"
                aa, bb = average_regional(left, regional_metric), average_regional(right, regional_metric)
                summary = paired_region_summary(aa, bb)
                summary["source_allocation_sensitivity"] = []
                for source in sorted({f["identity"]["source_split"] for f in left}):
                    source_a = [f for f in left if f["identity"]["source_split"] == source]
                    source_b = [f for f in right if f["identity"]["source_split"] == source]
                    require(len(source_a) == len(source_b) == 3, "Source sensitivity requires3 matched fit-seed pairs")
                    sensitivity = paired_region_summary(average_regional(source_a, regional_metric),
                                                        average_regional(source_b, regional_metric))
                    summary["source_allocation_sensitivity"].append({"source_split": source, **sensitivity})
                row["metrics"][name] = summary
                if row["role"] == "primary":
                    require(set(aa) == set(design["new_test_regions"]) and len(aa) == 24, "Primary needs exact24 regions")
                    primary["metrics"][name] = paired_region_summary(aa, bb,
                        repetitions=primary_spec["repetitions"], seed=primary_spec["bootstrap_seed"])
                    primary["metrics"][name]["role"] = "prespecified_primary_metric" if name == "union_class_miou" else "metric_convention_sensitivity"
                    if geographic_sensitivity is not None:
                        primary["geographic_sensitivity"]["metrics"][name] = geographic_sensitivity_summary(
                            aa, bb, geographic_sensitivity)
            contrasts.append(row)
    require(len(contrasts) == (36 if has_supplement else 28), "Unexpected sparse contrast inventory")
    return {"conditions_by_source": by_source, "conditions": conditions, "regions": region_rows,
            "classes": class_rows, "contrasts": {"format": "v2-contrasts-1", "contrasts": contrasts,
                "policy": "Original four contrasts cover all seven model/pool/budget families. The prospective weighted-FL contrasts occur only in the four skewed5_1 families present in the supplement. All secondary comparisons and source sensitivities are descriptive, without additional confirmatory claims.",
                "fit_sd_policy": "Raw fit SD describes fitting/source variability; it is not a geographic confidence interval."},
            "primary": primary}


def build_analysis(fits, design, extension=None, geographic_sensitivity=None):
    return _build_analysis(fits, design, expected_matrix(design, extension), geographic_sensitivity)


def load_audited(root):
    root = Path(root).resolve()
    audit_path = root / "evidence/v2/run_completeness.json"
    audit = read_json(audit_path)
    design = read_json(root / "configs/v2_design.json")
    extension = read_json(root / "configs/v2_extension.json")
    expected_total = len(expected_matrix(design, extension))
    require(audit.get("passed") is True and audit.get("expected_total") == expected_total == 576 and
            audit.get("validated_runs") == expected_total and audit.get("observed_result_files") == expected_total and
            len(audit.get("results", {})) == expected_total,
            "Complete576-run passed audit required before analysis")
    require(not audit.get("missing") and not audit.get("extra") and not audit.get("duplicates") and not audit.get("errors"),
            "Audit contains unresolved matrix/evidence errors")
    require(audit["audit_code_sha256"] == sha_file(root / "code/v2_audit_runs.py"), "Run audit code changed; rerun audit")
    for relative in ("configs/v2_design.json", "configs/v2_extension.json", "configs/v2_geographic_sensitivity.json",
                     "code/v2_weighted_selection.py"):
        require(relative in audit["inputs"], "Audit misses required design/supplement/dispatcher binding: " + relative)
    actual = {p.relative_to(root).as_posix() for p in (root / "evidence/v2/runs").rglob("result.json")}
    require(actual == set(audit["results"]), "Result inventory changed since audit")
    for category in ("inputs", "artifacts", "results"):
        for relative, checksum in audit[category].items():
            require(sha_file(safe_path(root, relative)) == checksum, "Audited file changed: " + relative)
    fits = [make_fit(read_json(safe_path(root, relative))) for relative in sorted(audit["results"])]
    return design, extension, audit, fits, sha_file(audit_path)


def write_csv(path, rows):
    require(bool(rows), "Cannot write an empty analysis table")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    temporary.replace(path)


def analyse(root=ROOT):
    root = Path(root).resolve()
    design, extension, audit, fits, audit_sha = load_audited(root)
    geographic_path = root / "configs/v2_geographic_sensitivity.json"
    geographic = read_json(geographic_path)
    require(geographic.get("exclude_entire_regions") == ["monrovia"] and
            geographic.get("primary_unchanged") is True and
            geographic.get("purpose") == "descriptive_geographic_metadata_sensitivity" and
            geographic.get("repetitions") == 10000 and geographic.get("bootstrap_seed") == 2026101805,
            "Expected frozen Monrovia-only descriptive sensitivity")
    analysis = build_analysis(fits, design, extension, geographic)
    out = root / "tables/v2"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("conditions_by_source", "conditions", "regions", "classes"):
        write_csv(out / (name + ".csv"), analysis[name])
    for name in ("contrasts", "primary"):
        write_json(out / (name + ".json"), analysis[name])
    names = [name + ".csv" for name in ("conditions_by_source", "conditions", "regions", "classes")]
    names += ["contrasts.json", "primary.json"]
    identity = {"format": "v2-analysis-identity-1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "audit_sha256": audit_sha, "analysis_code_sha256": sha_file(__file__),
                "geographic_sensitivity_config_sha256": sha_file(geographic_path),
                "audit_code_sha256": audit["audit_code_sha256"], "audited_input_sha256": audit["inputs"],
                "result_sha256": audit["results"], "audited_artifact_sha256": audit["artifacts"],
                "output_sha256": {"tables/v2/" + name: sha_file(out / name) for name in names},
                "counts": {"fits": len(fits), "conditions_by_source": len(analysis["conditions_by_source"]),
                           "conditions": len(analysis["conditions"]), "regions_rows": len(analysis["regions"]),
                           "classes_rows": len(analysis["classes"])},
                "metric_scale": "IoU fractions0..1; full float precision, no observed values hardcoded",
                "uncertainty_unit": "24 held-out regions, after averaging3 source allocations x3 paired fit seeds per strategy",
                "randomization": fit_randomization(fits),
                "interpretation_limits": ["Source allocations and training/selection seeds are not independent geographic replicates.",
                    "Selection and optimization seeds are paired0/1/2, not independently crossed; their variance components are not separately identified.",
                    "Fit sample SD is descriptive, not a geographic confidence interval.",
                    "Secondary families and source sensitivities do not constitute additional confirmatory tests.",
                    "A zero-crossing interval establishes neither equivalence nor absence of a useful effect.",
                    "These tables make no publication, acceptance or equivalence decision.",
                    "Processed-pixel verification scope and geographic data-audit cautions remain applicable."],
                "class_table_policy": "Pooled class IoU is computed per fit before averaging fits. Regional class means exclude undefined unions; truth-present regional means require positive true support. Defined-fit counts are explicit."}
    write_json(out / "analysis_identity.json", identity)
    return identity


class SyntheticStatisticsTests(unittest.TestCase):
    def test_paired_region_metric_and_leave_one_out(self):
        a = dict(a=.6, b=.3, c=.8); b = dict(a=.5, b=.5, c=.5)
        result = paired_region_summary(a, b, repetitions=10000, seed=2026101805)
        self.assertAlmostEqual(result["difference"], 1 / 15)
        np.testing.assert_allclose([v["difference"] for v in result["leave_one_region_out"]], [.05, .2, -.05])
        self.assertEqual(result, paired_region_summary(a, b, repetitions=10000, seed=2026101805))
        with self.assertRaises(ValueError): paired_region_summary(a, dict(a=.5, b=.5, d=.5))

    def test_average_fits_before_geography(self):
        fits = [{"regional": {"r1": {"miou": .2}, "r2": {"miou": .8}}},
                {"regional": {"r1": {"miou": .6}, "r2": {"miou": .4}}}]
        averaged = average_regional(fits, "miou")
        self.assertAlmostEqual(averaged["r1"], .4)
        self.assertAlmostEqual(averaged["r2"], .6)
        d = describe([.2, .6]); self.assertAlmostEqual(d["sd"], math.sqrt(.08))

    def test_condition_counts_from_cartesian_design(self):
        design = {"source_splits": [{"id": f"s{i}"} for i in range(3)],
                  "selection_seeds": [0, 1, 2], "strategies": [f"policy{i}" for i in range(8)],
                  "full_model": {"name": "full", "pools": ["skewed"], "budgets": [12], "initialization_seeds": [0]},
                  "frozen_control": {"name": "frozen", "pools": ["balanced", "skewed"], "budgets": [6, 12, 24], "initialization_seeds": [0]}}
        conditions, by_source = grouped_identities(design)
        self.assertEqual(len(expected_matrix(design)), 504)
        self.assertEqual((len(conditions), len(by_source)), (56, 168))

    def test_full_synthetic_analysis_matrix_in_memory(self):
        # This deliberately never creates result.json files or uses real scores.
        design = {"source_splits": [{"id": f"s{i}"} for i in range(3)],
                  "selection_seeds": [0, 1, 2],
                  "strategies": ["random", "kcenter", "region_random", "region_kcenter",
                                 "permuted_region_kcenter", "kmeanspp", "facility_location", "fd_roundrobin"],
                  "full_model": {"name": "synthetic_full", "pools": ["skewed5_1"], "budgets": [12], "initialization_seeds": [0]},
                  "frozen_control": {"name": "synthetic_frozen", "pools": ["balanced3", "skewed5_1"], "budgets": [6, 12, 24], "initialization_seeds": [0]},
                  "new_test_regions": [f"synthetic_region{i}" for i in range(24)],
                  "primary": {"model": "synthetic_full", "pool": "skewed5_1", "budget": 12,
                              "contrast": ["region_kcenter", "kcenter"], "repetitions": 10000,
                              "bootstrap_seed": 2026101805}}
        def synthetic_fit(identity):
            cm = np.zeros((8, 8), dtype=int)
            # Seed-dependent synthetic outcomes ensure the amended paired-base
            # primary cannot accidentally be compared with the init0 reference.
            cm[0, 0] = 8 - identity["initialization_seed"] if identity["strategy"] == "region_kcenter" else 5
            cm[0, 1] = 10 - cm[0, 0]
            regional = {r: scores(cm) for r in design["new_test_regions"]}
            metrics = {key: .1 for key in FIT_METRICS}
            metrics["equal_region_miou"] = scores(cm)["miou"]
            metrics["equal_region_union_miou"] = scores(cm)["union_class_miou"]
            return {"identity": identity, "metrics": metrics, "regional": regional,
                    "regional_cm": {r: cm for r in regional}, "pooled_cm": 24 * cm}
        fits = [synthetic_fit(identity) for identity in expected_matrix(design).values()]
        result = build_analysis(fits, design)
        self.assertEqual((len(result["conditions_by_source"]), len(result["conditions"])), (168, 56))
        self.assertEqual((len(result["regions"]), len(result["classes"])), (56 * 24, 56 * 8))
        self.assertEqual(len(result["contrasts"]["contrasts"]), 7 * 4)
        primary = result["primary"]["metrics"]
        self.assertAlmostEqual(primary["union_class_miou"]["difference"], .15)
        self.assertAlmostEqual(primary["truth_present_miou"]["difference"], .3)
        self.assertEqual(primary["union_class_miou"]["region_count"], 24)

        extension = {"status": "PROSPECTIVE_SUPPLEMENT_BEFORE_NEW_PANEL_EVALUATION",
                     "additional_strategies": list(ADDITIONAL_STRATEGIES), "pools": ["skewed5_1"],
                     "expected_additional_full_runs": 18, "expected_additional_frozen_runs": 54,
                     "expected_additional_total_runs": 72, "expected_total_runs": 576,
                     "initialization_seed_by_selection_seed": {"0": 0, "1": 1, "2": 2},
                     "randomization_amendment_before_new_panel_scores": True}
        # Compare with the SAME amended paired-fit base, not the historical
        # init0-only base. All objects remain synthetic and in memory.
        paired_base_matrix = paired_fit_matrix(expected_matrix(design), extension)
        paired_base_fits = [synthetic_fit(identity) for identity in paired_base_matrix.values()]
        geographic = {"exclude_entire_regions": ["synthetic_region0"], "primary_unchanged": True,
                      "purpose": "descriptive_geographic_metadata_sensitivity",
                      "repetitions": 10000, "bootstrap_seed": 2026101805}
        paired_base = _build_analysis(paired_base_fits, design, paired_base_matrix, geographic)
        self.assertAlmostEqual(paired_base["primary"]["metrics"]["union_class_miou"]["difference"], .1)
        self.assertNotEqual(paired_base["primary"], result["primary"])
        extended_fits = list(paired_base_fits)
        for identity in expected_matrix(design, extension).values():
            if identity["strategy"] in ADDITIONAL_STRATEGIES:
                extended_fits.append(synthetic_fit(identity))
        extended = build_analysis(extended_fits, design, extension, geographic)
        self.assertEqual(len(extended_fits), 576)
        self.assertEqual(len({run_key(f["identity"]) for f in extended_fits}), 576)
        self.assertTrue(all(f["identity"]["initialization_seed"] == f["identity"]["selection_seed"]
                            for f in extended_fits))
        self.assertTrue(all(row["initialization_seed_count"] == row["selection_seed_count"] == 3
                            for row in extended["conditions_by_source"]))
        self.assertEqual((len(extended["conditions_by_source"]), len(extended["conditions"])), (192, 64))
        self.assertEqual((len(extended["regions"]), len(extended["classes"])), (64 * 24, 64 * 8))
        self.assertEqual(len(extended["contrasts"]["contrasts"]), 36)
        supplemental = [row for row in extended["contrasts"]["contrasts"]
                        if row["origin"] == "prospective_weighted_fl_supplement"]
        self.assertEqual(len(supplemental), 8)
        self.assertTrue(all(row["pool"] == "skewed5_1" and row["role"] == "descriptive_secondary" for row in supplemental))
        self.assertFalse(any(row["pool"] == "balanced3" and row["strategy"] in ADDITIONAL_STRATEGIES
                             for row in extended["conditions"]))
        self.assertEqual(extended["primary"], paired_base["primary"])
        self.assertEqual(extended["primary"]["randomization"]["fit_seed_pairs"], [[0, 0], [1, 1], [2, 2]])
        self.assertFalse(extended["primary"]["randomization"]["selection_and_optimization_factors_separable"])
        self.assertEqual(extended["primary"]["geographic_replicates"], 24)
        self.assertEqual(extended["primary"]["metrics"]["union_class_miou"]["region_count"], 24)
        self.assertEqual(extended["primary"]["geographic_sensitivity"]["metrics"]["union_class_miou"]["region_count"], 23)
        wrong = list(extended_fits)
        wrong[-1] = {**wrong[-1], "identity": {**wrong[-1]["identity"], "pool": "balanced3"}}
        with self.assertRaisesRegex(ValueError, "matrix differs"):
            build_analysis(wrong, design, extension)
        old_init = list(extended_fits)
        position = next(i for i, fit in enumerate(old_init) if fit["identity"]["selection_seed"] == 1)
        old_init[position] = {**old_init[position], "identity": {**old_init[position]["identity"], "initialization_seed": 0}}
        with self.assertRaisesRegex(ValueError, "matrix differs"):
            build_analysis(old_init, design, extension)

    def test_descriptive_geographic_filter_preserves_primary_inputs(self):
        a = dict(r0=.1, r1=.5, r2=.9, r3=.2, r4=.4)
        b = dict.fromkeys(a, 0.)
        original_a, original_b = dict(a), dict(b)
        config = {"exclude_entire_regions": ["r2"], "primary_unchanged": True,
                  "purpose": "descriptive_geographic_metadata_sensitivity",
                  "repetitions": 10000, "bootstrap_seed": 2026101805}
        primary = paired_region_summary(a, b)
        sensitivity = geographic_sensitivity_summary(a, b, config)
        self.assertEqual(primary["region_count"], 5)
        self.assertEqual(sensitivity["region_count"], 4)
        self.assertAlmostEqual(sensitivity["difference"], .3)
        self.assertEqual(sensitivity["excluded_regions"], ["r2"])
        self.assertEqual({r["region"] for r in sensitivity["regional_differences"]}, {"r0", "r1", "r3", "r4"})
        self.assertEqual((a, b), (original_a, original_b))
        self.assertEqual(primary, paired_region_summary(a, b))
        self.assertIn("not_additional_confirmatory_test", sensitivity["role"])
        for exclusion in (["missing"], ["r2", "r2"]):
            with self.subTest(exclusion=exclusion), self.assertRaises(ValueError):
                geographic_sensitivity_summary(a, b, {**config, "exclude_entire_regions": exclusion})

    def test_metric_convention_from_synthetic_confusion(self):
        # True class0 has half its pixels predicted as a nonexistent class1.
        # Truth-present IoU=.5; union-class mean=(.5+0)/2=.25.
        cm = np.zeros((8, 8), dtype=int); cm[0, 0] = 5; cm[0, 1] = 5
        entries = [dict(id="synthetic", region="r", confusion=cm.tolist())]
        result = {"identity": {}, "test": {"images": entries, "aggregate": complete_aggregate(entries)},
                  "selection": {"selected_regions": ["s"], "mean_candidate_cosine_distance": .1,
                      "equal_region_mean_candidate_cosine_distance": .15,
                      "maximum_candidate_cosine_distance": .2, "selected_valid_original_pixels": 10, "selection_seconds": .01},
                  "total_seconds": .5}
        fit = make_fit(result)
        self.assertEqual(fit["metrics"]["equal_region_miou"], .5)
        self.assertEqual(fit["metrics"]["equal_region_union_miou"], .25)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticStatisticsTests))
        return 0 if result.wasSuccessful() else 1
    identity = analyse(args.root)
    print(json.dumps(identity["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
