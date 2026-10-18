"""Render fixed v2 summaries only after the exact576 evidence freshness gate.

--self-test uses temporary synthetic objects, never formal results or evidence.
No tests, confidence intervals, model predictions or numerical tables are made.
"""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NUMERIC = tuple("tables/v2/" + name for name in (
    "conditions_by_source.csv", "conditions.csv", "regions.csv", "classes.csv",
    "contrasts.json", "primary.json"))
CONFIGS = ("configs/v2_design.json", "configs/v2_extension.json",
           "configs/v2_geographic_sensitivity.json")
ACTIVE_AMENDMENT = "configs/v2_active_gpu_amendment.json"
ACTIVE_TOOL = "code/v2_active_gpu_results.py"
ACTIVE_AUDIT = "evidence/v2/active_run_completeness.json"
ACTIVE_ROLE = "descriptive_main_display_after_post_exposure_user_backend_amendment"
METRICS = (("union_class_miou", "equal_region_union_miou", "Union-class mIoU"),
           ("truth_present_miou", "equal_region_miou", "Truth-present mIoU"))
LABELS = {"random": "Random", "kcenter": "Visual k-center",
    "region_random": "Region random", "region_kcenter": "Region k-center",
    "permuted_region_kcenter": "Permuted region k-center", "kmeanspp": "k-means++",
    "facility_location": "Facility location", "fd_roundrobin": "FD adaptation",
    "region_weighted_facility_location": "Region-weighted FL",
    "permuted_region_weighted_facility_location": "Permuted weighted FL"}
# Okabe-Ito core, with distinct marker/line styles for the ten series.
COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
          "#56B4E9", "#000000", "#AA4499", "#117733", "#882255")
MARKERS = ("o", "s", "^", "D", "v", "P", "X", "<", ">", "h")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative,
            "Expected project-relative POSIX path")
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, "Unsafe project path")
    path = (root / part).resolve()
    require(path.is_relative_to(root.resolve()), "Path escapes project")
    return path


def inventory_sha(results):
    return hashlib.sha256(json.dumps(results, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def evidence_gate(root):
    """Check metadata first, then hash every audited input/artifact/result.

    Result JSONs are hashed as bytes, never opened as prediction/score objects.
    No table values are read before the full gate succeeds.
    """
    if safe_path(root, ACTIVE_AMENDMENT).exists():
        return active_evidence_gate(root)
    audit_path = safe_path(root, "evidence/v2/run_completeness.json")
    analysis_path = safe_path(root, "tables/v2/analysis_identity.json")
    audit, analysis = read_json(audit_path), read_json(analysis_path)
    freeze_sha = sha_file(safe_path(root, "configs/v2_freeze.json"))
    freeze = read_json(root / "configs/v2_freeze.json")
    require(audit.get("passed") is True and audit.get("expected_total") ==
        audit.get("validated_runs") == audit.get("observed_result_files") == 576 and
        len(audit.get("results", {})) == 576, "Passed exact576 audit required")
    require(not any(audit.get(k) for k in ("errors", "missing", "extra", "duplicates")),
            "Unresolved audit errors")
    require(freeze.get("status") == "FROZEN_BEFORE_NEW_PANEL_EVALUATION", "Invalid freeze status")
    audit_sha = sha_file(audit_path)
    require(analysis.get("counts", {}).get("fits") == 576 and
        analysis.get("audit_sha256") == audit_sha, "Analysis must bind current exact576 audit")
    require(analysis.get("audited_input_sha256") == audit.get("inputs") and
        audit.get("inputs", {}).get("configs/v2_freeze.json") == freeze_sha,
        "Analysis/audit/current frozen inputs differ")
    require(analysis.get("result_sha256") == audit["results"] and
        analysis.get("audited_artifact_sha256") == audit.get("artifacts"),
        "Analysis/audit result or artifact inventory differs")
    numeric = analysis.get("output_sha256")
    require(isinstance(numeric, dict) and set(numeric) == set(NUMERIC),
            "Exactly six numerical output SHA bindings required")
    for relative, checksum in numeric.items():
        require(sha_file(safe_path(root, relative)) == checksum, "Stale numeric file: " + relative)
    observed = {p.relative_to(root).as_posix() for p in
                (root / "evidence/v2/runs").rglob("result.json")}
    require(observed == set(audit["results"]), "Result inventory changed after audit")
    for category in ("inputs", "artifacts", "results"):
        mapping = audit.get(category)
        require(isinstance(mapping, dict) and mapping, "Missing audited " + category)
        for relative, checksum in mapping.items():
            require(isinstance(checksum, str) and len(checksum) == 64 and
                sha_file(safe_path(root, relative)) == checksum,
                "Stale audited " + category + ": " + relative)
    require(analysis.get("audit_code_sha256") == audit.get("audit_code_sha256") ==
        sha_file(root / "code/v2_audit_runs.py"), "Audit code changed")
    require(analysis.get("analysis_code_sha256") == sha_file(root / "code/v2_statistics.py"),
            "Analysis code changed")
    for relative in CONFIGS:
        require(relative in audit["inputs"], "Configuration absent from audited inputs: " + relative)
    return {"run_completeness_sha256": audit_sha,
        "analysis_identity_sha256": sha_file(analysis_path), "freeze_sha256": freeze_sha,
        "audited_result_inventory_sha256": inventory_sha(audit["results"]),
        "numeric_file_sha256": numeric,
        "configuration_sha256": {p: sha_file(root / p) for p in CONFIGS}}


def active_evidence_gate(root):
    """Use the target's read-only active GPU90+frozen486 bundle validator."""
    tool = safe_path(root, ACTIVE_TOOL)
    spec = importlib.util.spec_from_file_location("_v2_plot_active_gate", tool)
    require(spec is not None and spec.loader is not None, "Active validator unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(tool.parent))
    try:
        spec.loader.exec_module(module)
        checked = module.validate_bundle(root)
    finally:
        sys.path.pop(0)
    require(checked.get("passed") is True and not checked.get("errors"),
            "Passed active576 bundle required: " + str(checked.get("errors")))
    audit, analysis = checked["audit"], checked["analysis"]
    require(audit.get("expected_total") == audit.get("validated_runs") ==
        audit.get("observed_result_files") == len(audit.get("results", {})) == 576 and
        analysis.get("counts", {}).get("fits") == 576 and
        analysis.get("counts", {}).get("conditions") == 64, "Active exact576/64 required")
    require(audit.get("role") == analysis.get("role") == ACTIVE_ROLE and
        analysis.get("new_confirmatory_evidence") is False and
        analysis.get("original_CPU90_completed") is False,
        "Active display must retain post-exposure descriptive scope")
    require(audit.get("audit_code_sha256") == analysis.get("audit_code_sha256") ==
        analysis.get("analysis_code_sha256") == sha_file(tool) and
        analysis.get("statistical_reference_code_sha256") ==
        sha_file(safe_path(root, "code/v2_statistics.py")), "Active code bindings changed")
    audit_sha = sha_file(safe_path(root, ACTIVE_AUDIT))
    require(analysis.get("audit_sha256") == audit_sha and
        analysis.get("result_sha256") == audit["results"] and
        analysis.get("audited_input_sha256") == audit.get("inputs") and
        analysis.get("audited_artifact_sha256") == audit.get("artifacts"),
        "Active analysis/audit bindings differ")
    numeric = checked.get("output_sha256")
    require(isinstance(numeric, dict) and set(numeric) == set(NUMERIC) and
        numeric == analysis.get("output_sha256"), "Active six-output bindings required")
    for relative, checksum in numeric.items():
        require(sha_file(safe_path(root, relative)) == checksum, "Stale numeric file: " + relative)
    for relative in (*CONFIGS, ACTIVE_AMENDMENT, "configs/v2_freeze.json"):
        require(audit.get("inputs", {}).get(relative) == sha_file(safe_path(root, relative)),
                "Active configuration binding changed: " + relative)
    return {"run_completeness_sha256": audit_sha,
        "analysis_identity_sha256": sha_file(safe_path(root, "tables/v2/analysis_identity.json")),
        "freeze_sha256": sha_file(safe_path(root, "configs/v2_freeze.json")),
        "audited_result_inventory_sha256": inventory_sha(audit["results"]),
        "numeric_file_sha256": numeric,
        "configuration_sha256": {p: sha_file(root / p) for p in CONFIGS},
        "active_amendment_sha256": sha_file(safe_path(root, ACTIVE_AMENDMENT)),
        "audit_code_sha256": sha_file(tool), "analysis_scope": ACTIVE_ROLE,
        "statistical_reference_code_sha256": analysis["statistical_reference_code_sha256"],
        "active_fits": {"GPU_full": 90, "frozen_head": 486, "CPU_reference_included": 0},
        "new_confirmatory_evidence": False}


def expected_conditions(design, extension):
    result = set()
    for group in ("full_model", "frozen_control"):
        spec = design[group]
        for pool in spec["pools"]:
            strategies = design["strategies"] + (extension["additional_strategies"]
                if pool in extension["pools"] else [])
            for budget in spec["budgets"]:
                result.update((spec["name"], pool, budget, strategy) for strategy in strategies)
    return result


def finite(value, scope):
    require(not isinstance(value, bool), "Boolean numeric value: " + scope)
    value = float(value)
    require(math.isfinite(value), "Nonfinite " + scope)
    return value


def region_summary(summary, regions, scope):
    entries = summary.get("regional_differences", [])
    require(len(entries) == len(regions) and len({r["region"] for r in entries}) == len(entries)
        and {r["region"] for r in entries} == set(regions), "Wrong regional support: " + scope)
    values = {}
    for row in entries:
        a, b, diff = (finite(row[k], scope) for k in ("a", "b", "difference"))
        require(0 <= a <= 1 and 0 <= b <= 1 and abs(a - b - diff) < 1e-12,
                "Invalid regional difference: " + scope)
        values[row["region"]] = diff
    require(summary.get("region_count") == len(regions) and
        abs(finite(summary["difference"], scope) - sum(values.values()) / len(values)) < 1e-12,
        "Invalid regional mean: " + scope)
    boot = summary.get("bootstrap")
    if boot is not None:
        require(boot.get("level") == .95 and finite(boot["lower"], scope) <=
            finite(boot["upper"], scope), "Invalid stored CI: " + scope)
    return values


def validate_data(design, extension, sensitivity, conditions, primary, contrasts):
    regions = design["new_test_regions"]
    require(len(regions) == len(set(regions)) == 24, "Expected fixed24 region design")
    expected, rows = expected_conditions(design, extension), {}
    for row in conditions:
        key = (row["model"], row["pool"], int(row["budget"]), row["strategy"])
        require(key not in rows, "Duplicate condition")
        require(int(row["fits"]) == 9 and int(row["source_allocations"]) == 3 and
            int(row["held_out_regions"]) == 24, "Expected nine fits and24 regions per condition")
        for _, metric, _ in METRICS:
            value = finite(row[metric + "_mean"], metric)
            raw = json.loads(row[metric + "_raw_fits"]) if isinstance(row[metric + "_raw_fits"], str) else row[metric + "_raw_fits"]
            require(len(raw) == 9 and all(0 <= finite(v, metric) <= 1 for v in raw) and
                abs(sum(map(float, raw)) / 9 - value) < 1e-12, "Invalid raw-fit mean")
        rows[key] = row
    require(set(rows) == expected and len(rows) == 64, "Incomplete/extra condition families")
    require(primary.get("specification") == design["primary"] and
        primary.get("fits_per_strategy") == 9 and primary.get("geographic_replicates") == 24,
        "Primary specification differs from design")
    spec = design["primary"]
    matched = [c for c in contrasts["contrasts"] if (c["model"], c["pool"], c["budget"], c["a"], c["b"]) ==
        (spec["model"], spec["pool"], spec["budget"], *spec["contrast"])]
    require(len(matched) == 1, "Expected one primary contrast")
    source_ids = [s["id"] for s in design["source_splits"]]
    for metric, _, _ in METRICS:
        overall = region_summary(primary["metrics"][metric], regions, metric)
        boot = primary["metrics"][metric].get("bootstrap")
        if boot is not None:
            require(boot.get("repetitions") == spec["repetitions"] and
                boot.get("seed") == spec["bootstrap_seed"], "Stored primary CI configuration differs")
        contrast = matched[0]["metrics"][metric]
        require(region_summary(contrast, regions, metric) == overall, "Primary and contrasts differ")
        sources = contrast["source_allocation_sensitivity"]
        require(len(sources) == 3 and {s["source_split"] for s in sources} == set(source_ids),
                "Wrong source allocation support")
        source_values = [region_summary(s, regions, metric) for s in sources]
        require(all(abs(sum(v[r] for v in source_values) / 3 - overall[r]) < 1e-12 for r in regions),
                "Sources do not average to primary regional difference")
    geo = primary.get("geographic_sensitivity")
    if geo is not None:
        require(geo.get("configuration") == sensitivity and geo.get("primary_unchanged") is True,
                "Geographic sensitivity specification changed")
        retained = [r for r in regions if r not in sensitivity["exclude_entire_regions"]]
        require(len(retained) == sensitivity["target_retained_regions"] == 23,
                "Wrong fixed sensitivity support")
        for metric, _, _ in METRICS:
            summary = geo["metrics"][metric]
            require(set(summary["excluded_regions"]) == set(sensitivity["exclude_entire_regions"]),
                    "Sensitivity exclusions changed")
            filtered = region_summary(summary, retained, metric)
            complete = {r["region"]: r["difference"] for r in primary["metrics"][metric]["regional_differences"]}
            require(all(abs(filtered[r] - complete[r]) < 1e-12 for r in retained),
                    "Sensitivity must filter the fixed primary regional differences")
            boot = summary.get("bootstrap")
            if boot is not None:
                require(boot.get("repetitions") == sensitivity["repetitions"] and
                    boot.get("seed") == sensitivity["bootstrap_seed"], "Stored sensitivity CI configuration differs")
    return {"design": design, "extension": extension, "sensitivity": sensitivity,
            "rows": rows, "primary": primary, "primary_contrast": matched[0]}


def plotting():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required for plotting/self-test; --help needs only stdlib") from exc
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5,
        "axes.titlesize": 10.5, "axes.labelsize": 9.5, "xtick.labelsize": 9,
        "ytick.labelsize": 9, "legend.fontsize": 9, "figure.titlesize": 11,
        "svg.fonttype": "none", "pdf.fonttype": 42, "axes.spines.top": False,
        "axes.spines.right": False, "savefig.dpi": 300})
    return plt


def interval_point(ax, summary, y, color, marker="D"):
    """Use only stored bounds; no inferred CI or sign-based interpretation."""
    boot = summary.get("bootstrap")
    if boot is not None:
        ax.plot([100 * boot["lower"], 100 * boot["upper"]], [y, y], color=color, lw=1.5)
        ax.plot([100 * boot["lower"], 100 * boot["upper"]], [y, y], "|", color=color, ms=7)
    ax.plot(100 * summary["difference"], y, marker=marker, color=color, ms=5, linestyle="none")


def primary_figure(data, metric, title, plt):
    fig, (ax, summary_ax) = plt.subplots(1, 2, figsize=(6.5, 7.5),
        gridspec_kw={"width_ratios": [1.7, 1]}, layout="constrained")
    regions = data["design"]["new_test_regions"]
    overall = data["primary"]["metrics"][metric]
    by_region = {r["region"]: r["difference"] for r in overall["regional_differences"]}
    sources = data["primary_contrast"]["metrics"][metric]["source_allocation_sensitivity"]
    source_ids = [s["id"] for s in data["design"]["source_splits"]]
    sources = sorted(sources, key=lambda s: source_ids.index(s["source_split"]))
    y = list(range(len(regions)))
    for j, source in enumerate(sources):
        vals = {r["region"]: r["difference"] for r in source["regional_differences"]}
        ax.plot([100 * vals[r] for r in regions], [i + (j - 1) * .17 for i in y],
            linestyle="none", marker=MARKERS[j], ms=3.2, alpha=.8,
            color=COLORS[j], label=source["source_split"])
    ax.plot([100 * by_region[r] for r in regions], y, "kD", ms=3.8, label="All 9 fits")
    ax.set_yticks(y, [r.replace("_", " ") for r in regions]); ax.invert_yaxis()
    ax.set_title("Fixed design region order")
    labels = ["All 24 regions"]
    interval_point(summary_ax, overall, 0, "#000000")
    if "bootstrap" not in overall: labels[0] += "\nCI unavailable"
    next_y = 1
    geo = data["primary"].get("geographic_sensitivity")
    if geo is not None:
        interval_point(summary_ax, geo["metrics"][metric], next_y, "#666666", "s")
        excluded = ", ".join(r.replace("_", " ").title() for r in data["sensitivity"]["exclude_entire_regions"])
        label = "23 regions\nexcluding " + excluded
        if "bootstrap" not in geo["metrics"][metric]: label += "\nCI unavailable"
        labels.append(label); next_y += 1
    for j, source in enumerate(sources):
        interval_point(summary_ax, {"difference": source["difference"]}, next_y,
                       COLORS[j], MARKERS[j])
        labels.append(source["source_split"]); next_y += 1
    summary_ax.set_yticks(range(next_y), labels); summary_ax.invert_yaxis()
    summary_ax.yaxis.tick_right()
    summary_ax.set_ylim(next_y - .5, -.5); summary_ax.set_title("Overall and source means\nStored 95% region CI")
    for axis in (ax, summary_ax):
        axis.axvline(0, color="#999999", lw=.7, zorder=0)
        axis.grid(axis="x", alpha=.2); axis.set_xlabel("Region k-center −\nvisual k-center\n(percentage points)")
    ax.legend(loc="lower left", bbox_to_anchor=(-.1, 1.015), ncol=2,
              handletextpad=.3, columnspacing=.6, frameon=False)
    fig.suptitle(title + " comparison")
    fig.supxlabel("Region means average 3 source allocations × 3 paired fit seeds.\n"
        "CI: stored paired-region bootstrap; source points have no geographic CI.", fontsize=9)
    return fig


def model_figure(data, plt):
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 7.4), sharex=True, layout="constrained")
    strategies = data["design"]["strategies"] + data["extension"]["additional_strategies"]
    for ax, group in zip(axes, ("full_model", "frozen_control")):
        model = data["design"][group]["name"]
        for j, (_, metric, label) in enumerate(METRICS):
            vals = [100 * float(data["rows"][(model, "skewed5_1", 12, s)][metric + "_mean"])
                    for s in strategies]
            ax.plot(vals, [i + (j - .5) * .22 for i in range(10)], linestyle="none",
                    marker=MARKERS[j], color=COLORS[j], ms=4, label=label)
        ax.set_yticks(range(10), [LABELS[s] for s in strategies]); ax.invert_yaxis()
        ax.set_title(model + " | skewed 5:1 pool | budget 12")
        ax.grid(axis="x", alpha=.2); ax.set_xlim(0, 100)
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.08), ncol=2, frameon=False)
    axes[-1].set_xlabel("Equal-region mIoU (%) — mean of 9 fits; no CI inferred")
    fig.supxlabel("Models also differ in pretraining, encoder, decoder, grid and augmentation.\n"
                  "The comparison does not isolate the causal effect of fine-tuning.", fontsize=9)
    return fig


def frozen_figure(data, plt):
    fig, axes = plt.subplots(2, 2, figsize=(6.5, 7.6), sharex=True, sharey=True)
    model = data["design"]["frozen_control"]["name"]
    strategies = data["design"]["strategies"] + data["extension"]["additional_strategies"]
    for row_i, (_, metric, label) in enumerate(METRICS):
        for col, pool in enumerate(data["design"]["frozen_control"]["pools"]):
            ax = axes[row_i, col]
            for i, strategy in enumerate(strategies):
                keys = [(model, pool, b, strategy) for b in (6, 12, 24)]
                if not all(k in data["rows"] for k in keys): continue
                ax.plot((6, 12, 24), [100 * float(data["rows"][k][metric + "_mean"]) for k in keys],
                    color=COLORS[i], marker=MARKERS[i], ms=4, lw=1,
                    linestyle="--" if i >= 8 else "-", label=LABELS[strategy])
            ax.set_xticks((6, 12, 24)); ax.set_ylim(0, 100); ax.grid(alpha=.2)
            ax.set_title(pool + (" (8 policies)" if pool == "balanced3" else " (10 policies)"))
            if col == 0: ax.set_ylabel(label + " (%)")
            if row_i == 1: ax.set_xlabel("Whole-image annotation budget")
    handles, labels = axes[0, 1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(.5, .045), columnspacing=1, handlelength=2)
    fig.suptitle(model + ": all planned pool–budget conditions")
    fig.text(.5, .012, "Each point averages 9 fits; no interval inferred.\nBalanced weighted-FL duplicates were not fitted.",
             ha="center", fontsize=9)
    fig.subplots_adjust(left=.12, right=.98, bottom=.30, top=.92, wspace=.15, hspace=.3)
    return fig


def make_figures(data, output_dir):
    plt = plotting()
    figures = {"primary_union": primary_figure(data, "union_class_miou", "Union-class mIoU", plt),
        "primary_truth_present": primary_figure(data, "truth_present_miou", "Truth-present mIoU", plt),
        "models_skewed_b12": model_figure(data, plt), "frozen_pools_budgets": frozen_figure(data, plt)}
    outputs = []
    try:
        from matplotlib.text import Text
        for name, fig in figures.items():
            require(all(t.get_fontsize() >= 9 for t in fig.findobj(Text) if t.get_text()),
                    "Figure contains text below9pt")
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            for text in fig.findobj(Text):
                if not text.get_visible() or not text.get_text(): continue
                box = text.get_window_extent(renderer)
                require(box.x0 >= -2 and box.y0 >= -2 and
                    box.x1 <= fig.bbox.width + 2 and box.y1 <= fig.bbox.height + 2,
                    "Text extends beyond physical canvas: " + name + ": " + text.get_text())
            for suffix in ("svg", "pdf", "png"):
                path = output_dir / (name + "." + suffix)
                # Keep the specified physical canvas; do not auto-crop to oversized labels.
                fig.savefig(path, dpi=300, metadata={"Creator": "v2_plot_results"})
                outputs.append(path)
    finally:
        for fig in figures.values(): plt.close(fig)
    return outputs


def synthetic_data():
    """Invented values are confined to temporary mechanical checks."""
    strategies = list(LABELS)[:8]
    design = {"new_test_regions": ["region%02d" % i for i in range(24)],
        "strategies": strategies, "source_splits": [{"id": "source%d" % i} for i in range(3)],
        "full_model": {"name": "resnet18_unet", "pools": ["skewed5_1"], "budgets": [12]},
        "frozen_control": {"name": "dinov2_mlp128", "pools": ["balanced3", "skewed5_1"], "budgets": [6,12,24]},
        "primary": {"model": "resnet18_unet", "pool": "skewed5_1", "budget": 12,
                    "contrast": ["region_kcenter", "kcenter"], "repetitions": 10000,
                    "bootstrap_seed": 2026101805}}
    extension = {"additional_strategies": list(LABELS)[8:], "pools": ["skewed5_1"]}
    sensitivity = {"exclude_entire_regions": ["region13"], "target_retained_regions": 23,
                   "repetitions":10000, "bootstrap_seed":2026101805}
    rows = []
    for model, pool, budget, strategy in sorted(expected_conditions(design, extension)):
        row = dict(model=model, pool=pool, budget=budget, strategy=strategy,
                   fits=9, source_allocations=3, held_out_regions=24)
        for _, metric, _ in METRICS:
            row[metric + "_mean"] = .45
            row[metric + "_raw_fits"] = json.dumps([.45] * 9)
        rows.append(row)
    def summary(regions, shift=0, ci=False):
        entries = [{"region": r, "a": .5 + (i - 12) / 1000 + shift, "b": .5,
            "difference": (i - 12) / 1000 + shift} for i, r in enumerate(design["new_test_regions"]) if r in regions]
        result = {"regional_differences": entries, "region_count": len(entries),
                  "difference": sum(r["difference"] for r in entries) / len(entries)}
        if ci: result["bootstrap"] = {"level": .95, "lower": -.008, "upper": .009,
                                      "repetitions":10000, "seed":2026101805}
        return result
    primary = {"specification": design["primary"], "fits_per_strategy": 9,
        "geographic_replicates":24, "metrics": {}, "geographic_sensitivity": {
            "configuration": sensitivity, "primary_unchanged": True, "metrics": {}}}
    contrast = {**{k: design["primary"][k] for k in ("model", "pool", "budget")},
                "a": "region_kcenter", "b": "kcenter", "metrics": {}}
    for metric, _, _ in METRICS:
        primary["metrics"][metric] = summary(design["new_test_regions"], ci=True)
        contrast["metrics"][metric] = summary(design["new_test_regions"])
        contrast["metrics"][metric]["source_allocation_sensitivity"] = [
            {"source_split": "source%d" % i, **summary(design["new_test_regions"], (i - 1) / 1000)} for i in range(3)]
        retained = [r for r in design["new_test_regions"] if r != "region13"]
        primary["geographic_sensitivity"]["metrics"][metric] = {
            **summary(retained, ci=True), "excluded_regions": ["region13"]}
    return design, extension, sensitivity, rows, primary, {"contrasts": [contrast]}


def active_gate_self_test():
    """Test the adapter with a synthetic validator; not the scientific auditor."""
    with tempfile.TemporaryDirectory(prefix="v2_plot_active_gate_") as temporary:
        root = Path(temporary)
        def write(relative, value):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        for relative in (*CONFIGS, ACTIVE_AMENDMENT, "configs/v2_freeze.json", *NUMERIC):
            write(relative, {})
        (root / "code").mkdir()
        (root / "code/v2_statistics.py").write_text("# synthetic reference\n", encoding="utf-8")
        (root / ACTIVE_TOOL).write_text(
            "import json\nfrom pathlib import Path\ndef validate_bundle(root):\n"
            "    return json.loads((Path(root)/'gate_fixture.json').read_text())\n", encoding="utf-8")
        tool_sha = sha_file(root / ACTIVE_TOOL)
        audit = {"passed": True, "expected_total": 576, "validated_runs": 576,
            "observed_result_files": 576, "results": {"synthetic/run%d/result.json" % i: "0" * 64 for i in range(576)},
            "inputs": {p: sha_file(root / p) for p in (*CONFIGS, ACTIVE_AMENDMENT, "configs/v2_freeze.json")},
            "artifacts": {}, "role": ACTIVE_ROLE, "audit_code_sha256": tool_sha}
        write(ACTIVE_AUDIT, audit)
        numeric = {p: sha_file(root / p) for p in NUMERIC}
        analysis = {"counts": {"fits": 576, "conditions": 64}, "role": ACTIVE_ROLE,
            "new_confirmatory_evidence": False, "original_CPU90_completed": False,
            "audit_code_sha256": tool_sha, "analysis_code_sha256": tool_sha,
            "statistical_reference_code_sha256": sha_file(root / "code/v2_statistics.py"),
            "audit_sha256": sha_file(root / ACTIVE_AUDIT), "result_sha256": audit["results"],
            "audited_input_sha256": audit["inputs"], "audited_artifact_sha256": audit["artifacts"],
            "output_sha256": numeric}
        write("tables/v2/analysis_identity.json", analysis)
        checked = {"passed": True, "errors": [], "audit": audit, "analysis": analysis, "output_sha256": numeric}
        write("gate_fixture.json", checked)
        # No legacy audit exists: success proves the amendment dispatches only to active.
        binding = evidence_gate(root)
        require(binding["analysis_scope"] == ACTIVE_ROLE and
                binding["active_fits"]["CPU_reference_included"] == 0, "Active descriptive scope missing")
        for mutation in ("failed_bundle", "wrong_count", "confirmatory", "wrong_code", "stale_binding"):
            changed = copy.deepcopy(checked)
            if mutation == "failed_bundle": changed.update(passed=False, errors=["synthetic refused"])
            elif mutation == "wrong_count": changed["audit"]["validated_runs"] = 575
            elif mutation == "confirmatory": changed["analysis"]["new_confirmatory_evidence"] = True
            elif mutation == "wrong_code": changed["analysis"]["analysis_code_sha256"] = "1" * 64
            else: changed["analysis"]["audit_sha256"] = "1" * 64
            write("gate_fixture.json", changed)
            try: evidence_gate(root)
            except ValueError: pass
            else: raise AssertionError("Active adapter accepted " + mutation)
        write("gate_fixture.json", checked)
        write(NUMERIC[0], {"mutated": True})
        try: evidence_gate(root)
        except ValueError: pass
        else: raise AssertionError("Active adapter accepted stale numeric file")


def self_test():
    fixture = synthetic_data()
    data = validate_data(*fixture)
    require(len(data["rows"]) == 64, "Synthetic condition count")
    for mutation in ("missing", "duplicate", "balanced_weighted", "nonfinite"):
        changed = copy.deepcopy(fixture)
        if mutation == "missing": changed[3].pop()
        elif mutation == "duplicate": changed[3].append(copy.deepcopy(changed[3][0]))
        elif mutation == "balanced_weighted":
            row = copy.deepcopy(changed[3][0]); row.update(pool="balanced3", strategy=list(LABELS)[8]); changed[3].append(row)
        else: changed[3][0]["equal_region_union_miou_mean"] = float("nan")
        try: validate_data(*changed)
        except ValueError: pass
        else: raise AssertionError("Did not reject " + mutation)
    with tempfile.TemporaryDirectory(prefix="v2_plot_synthetic_") as temporary:
        data["post_exposure_descriptive"] = True
        files = make_figures(data, Path(temporary))
        require(len(files) == 12 and all(p.stat().st_size > 100 for p in files), "Missing plot outputs")
        for p in files:
            if p.suffix == ".svg": require(ET.parse(p).getroot().tag.endswith("svg"), "Invalid SVG")
            if p.suffix == ".pdf": require(p.read_bytes().startswith(b"%PDF"), "Invalid PDF")
            if p.suffix == ".png": require(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG")
        missing_ci = copy.deepcopy(data)
        for summary in missing_ci["primary"]["metrics"].values(): summary.pop("bootstrap")
        plt = plotting(); fig = primary_figure(missing_ci, "union_class_miou", "Synthetic no-CI check", plt)
        require(any("CI unavailable" in t.get_text() for t in fig.axes[1].get_yticklabels()), "Missing-CI label")
        require(fig._suptitle.get_text() == "Synthetic no-CI check comparison", "Metric comparison title missing")
        require(all("descriptive" not in t.get_text() for t in fig.axes[1].get_yticklabels()),
                "Repeated scope qualifiers in display labels")
        plt.close(fig)
    require(inventory_sha({"a": "1"}) == inventory_sha(dict(a="1")) and
            inventory_sha({"a": "1"}) != inventory_sha({"a": "2"}), "Inventory digest")
    with tempfile.TemporaryDirectory(prefix="v2_plot_rejection_") as temporary:
        root = Path(temporary)
        for relative, value in (("evidence/v2/run_completeness.json", {"passed": False}),
                ("tables/v2/analysis_identity.json", {}), ("configs/v2_freeze.json", {})):
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        try: evidence_gate(root)
        except ValueError as exc: require("exact576" in str(exc), "Unexpected incomplete-audit failure")
        else: raise AssertionError("Incomplete audit accepted")
    active_gate_self_test()
    print("PASS: synthetic64-condition schema, four invalid schemas,12 temporary formats, font/canvas bounds, missing-CI handling, inventory digest, incomplete-audit rejection, active bundle dispatch/SHA/scope rejection. No formal results read/written.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root; formal outputs have fixed project-relative paths")
    parser.add_argument("--self-test", action="store_true", help="Temporary synthetic schema/plot mechanics only; no formal data/evidence")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return
    root = args.root.resolve()
    binding = evidence_gate(root)
    design, extension, sensitivity = [read_json(root / p) for p in CONFIGS]
    with (root / "tables/v2/conditions.csv").open(encoding="utf-8", newline="") as stream:
        conditions = list(csv.DictReader(stream))
    data = validate_data(design, extension, sensitivity, conditions,
        read_json(root / "tables/v2/primary.json"), read_json(root / "tables/v2/contrasts.json"))
    data["post_exposure_descriptive"] = binding.get("analysis_scope") == ACTIVE_ROLE
    output_dir = safe_path(root, "figures/v2/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = make_figures(data, output_dir)
    # Recheck all evidence after rendering, so concurrent changes cannot produce a valid manifest.
    require(evidence_gate(root) == binding, "Evidence changed during rendering; no manifest issued")
    report = {"format": "v2-result-figures-1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "generated_requires_visual_review", "visual_review_performed": False,
        "scientific_interpretation_generated": False, "input_binding": binding,
        "plot_code_sha256": sha_file(Path(__file__)),
        "output_sha256": {p.relative_to(root).as_posix(): sha_file(p) for p in outputs},
        "statistics_unit": "24 held-out regions;3 source allocations and3 paired fitting seeds averaged first",
        "analysis_scope": binding.get("analysis_scope", "original_frozen_design"),
        "descriptive_panels": ["23-region fixed sensitivity", "three source allocations", "all condition means"],
        "interval_policy": "Only stored bootstrap intervals; no CI constructed from fit SD or condition means",
        "metric_policy": "Union includes truth-or-prediction-present classes; truth-present excludes classes absent from truth. Void excluded. Fractions multiplied by100 only for display.",
        "limitations": ["Source allocations and fitting seeds are not independent geographic replicates",
            "Full/frozen comparison does not isolate encoder fine-tuning", "No significance stars or automatic interval-sign conclusion"]}
    path = safe_path(root, "evidence/v2/result_figures.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print("Generated12 figure assets; visual review required. Manifest: " + str(path))


if __name__ == "__main__":
    main()
