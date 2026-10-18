"""Secondary equal-available-processed-label ablation; explicit --run only.

No existing scientific code or raster is changed. --self-test uses synthetic
temporary fixtures. Two OS workers run independent fits only after CUDA90 ends.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import warnings

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import v2_cuda_parallel_v2 as common

ROOT = Path(__file__).resolve().parents[1]
PLAN = "configs/v2_pixel_budget_plan.json"
PROTOCOL = "docs/v2_pixel_budget_protocol.md"
SOURCE_PLAN = "configs/v2_cuda_execution_plan.json"
SOURCE_SHA = "15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545"
HELPER = "code/v2_cuda_parallel_v2.py"
OUT = "evidence/v2/pixel_budget_execution"
CUDA_OUT = "evidence/v2/cuda_execution"
CAP = 2_000_000_000
EXTERNAL_RESERVE = 55_000_000
WORKER_RESERVE = 4_000_000
BUDGET = 2_300_000
MASK_SEED = 2026101811
STRATEGIES = {"kcenter", "region_kcenter", "permuted_region_kcenter"}
require, safe, sha, read = common.require, common.safe, common.sha, common.read
raw, bare_new, bare_replace = common.raw, common.bare_new, common.bare_replace


def utc():
    return datetime.now(timezone.utc).isoformat()


def run_key(identity):
    return common.run_key(identity)


def load_plan(root, expected_sha=None):
    path = safe(root, PLAN)
    digest = sha(path)
    require(expected_sha is None or digest == expected_sha, "Pixel plan changed")
    plan = read(path)
    require(plan["format"] == "v2-pixel-budget-plan-1" and
            plan["status"] == "LOCKED_BEFORE_PIXEL_BUDGET_FITS_AFTER_PANEL_EXPOSURE" and
            plan["prior_target_exposure"] is True, "Expected explicit post-exposure secondary plan")
    require(plan["runner_code_sha256"] == sha(Path(__file__)), "Pixel runner SHA differs")
    require(plan["helper_code_sha256"] == {HELPER: sha(safe(root, HELPER))} and
            sha(Path(common.__file__)) == plan["helper_code_sha256"][HELPER], "Helper code SHA differs")
    require(plan["protocol_sha256"] == sha(safe(root, PROTOCOL)), "Pixel protocol SHA differs")
    require(plan["source_cuda_plan"] == SOURCE_PLAN and plan["source_cuda_plan_sha256"] == SOURCE_SHA ==
            sha(safe(root, SOURCE_PLAN)), "Original CUDA plan changed")
    source = read(safe(root, SOURCE_PLAN))
    freeze = read(safe(root, "configs/v2_freeze.json"))
    require(plan["original_freeze_sha256"] == source["original_freeze_sha256"] ==
            sha(safe(root, "configs/v2_freeze.json")), "Original freeze changed")
    require(plan["original_frozen_file_sha256"] == source["original_frozen_file_sha256"] ==
            freeze["file_sha256"] and len(freeze["file_sha256"]) == 53, "Original53 bindings differ")
    for name, checksum in freeze["file_sha256"].items():
        require(sha(safe(root, name)) == checksum, "Frozen input changed: " + name)
    expected = [r for r in source["runs"] if r["identity"]["strategy"] in STRATEGIES]
    require(plan["runs"] == expected and plan["expected_runs"] == len(expected) == 27 and
            len({run_key(s["identity"]) for s in expected}) == 27, "Must retain exact27 ordered source specs")
    require(all(s["identity"]["model"] == "resnet18_unet" and s["identity"]["pool"] == "skewed5_1" and
                s["identity"]["budget"] == 12 and s["identity"]["initialization_seed"] ==
                s["identity"]["selection_seed"] in (0, 1, 2) for s in expected), "Unexpected fit identity")
    require(plan["runtime"] == source["runtime"] and plan["runtime"]["threads"] == 2 and
            plan["new_panel_image_ids"] == source["new_panel_image_ids"], "Runtime/panel must remain locked")
    supervision = plan["supervision"]
    require(supervision == {"processed_grid": [448, 448], "available_valid_pixel_budget": BUDGET,
        "mask_seed_base": MASK_SEED, "mask_order": "ordered_selected_ids_then_row_major_original_valid_positions",
        "sampling": "uniform_remove_without_replacement", "original_void_remains_ignored": True},
        "Supervision rule differs from fixed ablation")
    require(plan.get("workers", 2) == 2 and plan.get("external_growth_reserve_bytes", EXTERNAL_RESERVE) == EXTERNAL_RESERVE and
            plan.get("per_worker_output_reserve_bytes", WORKER_RESERVE) == WORKER_RESERVE, "Fixed scheduling/reserves differ")
    return plan, digest


def thin_masks(masks, ids, budget, seed):
    """Uniformly remove positions across the ordered union, without class access.

    Sampling uses only validity. Class counts are calculated after sampling.
    Input arrays are never modified; only original0..7 positions become255.
    """
    import numpy as np
    require(len(masks) == len(ids) == len(set(ids)) and masks, "Empty/duplicate selected masks")
    source = [np.asarray(a) for a in masks]
    require(all(a.ndim == 2 and np.isin(a, [*range(8), 255]).all() for a in source), "Invalid internal class mapping")
    positions = [np.flatnonzero(a.ravel(order="C") != 255) for a in source]
    counts = [len(a) for a in positions]
    total = sum(counts)
    require(isinstance(budget, int) and 0 < budget <= total, "Pixel budget exceeds original valid supervision")
    removed = np.sort(np.random.default_rng(seed).choice(total, total - budget, replace=False))
    result, summaries, digest = [], [], hashlib.sha256()
    start = 0
    for identifier, original, valid in zip(ids, source, positions):
        output = original.copy(order="C")
        lo, hi = np.searchsorted(removed, [start, start + len(valid)])
        output.ravel(order="C")[valid[removed[lo:hi] - start]] = 255
        kept = output != 255
        packed = np.packbits(kept.ravel(order="C"), bitorder="little").tobytes()
        digest.update(packed)
        before = np.bincount(original[original != 255].astype(int), minlength=8).tolist()
        after = np.bincount(output[kept].astype(int), minlength=8).tolist()
        summaries.append({"id": identifier, "shape": list(output.shape), "original_valid_pixels": len(valid),
            "retained_valid_pixels": int(kept.sum()), "removed_pixels": int(len(valid) - kept.sum()),
            "original_class_counts": before, "retained_class_counts": after,
            "classes_removed_entirely": [i for i in range(8) if before[i] and not after[i]],
            "keep_bitmap_sha256": hashlib.sha256(packed).hexdigest(),
            "training_mask_uint8_row_major_sha256": hashlib.sha256(output.astype("uint8").tobytes(order="C")).hexdigest()})
        result.append(output)
        start += len(valid)
    require(sum(r["retained_valid_pixels"] for r in summaries) == budget, "Incorrect retained pixel budget")
    return result, {"seed": seed, "generator": "numpy.default_rng/PCG64", "numpy": np.__version__,
        "sampling": "uniform_remove_without_replacement", "order": "ordered_selected_ids_then_row_major_original_valid_positions",
        "class_conditioned_sampling": False, "available_valid_pixels_before": total, "available_valid_pixels_after": budget,
        "removed_pixels": total - budget, "ordered_selected_ids": list(ids), "images": summaries,
        "combined_keep_bitmap_sha256": digest.hexdigest(),
        "keep_bitmap_encoding": "Per-image full-grid row-major booleans, numpy.packbits(bitorder=little); concatenate in selected-ID order",
        "budget_scope": "unique available processed-grid training labels; not repeated crop consumption, native annotation effort or time"}


@contextmanager
def training_masks(segmentation, selected, base, budget, seed):
    """Patch this worker's training loader only, restoring it on every exit."""
    original = segmentation.load_pair
    original_batch = segmentation.make_batch
    ids = [r["id"] for r in selected]
    loaded = [original(record, base) for record in selected]
    masks, metadata = thin_masks([y.numpy() for _, y in loaded], ids, budget, seed)
    pairs = {identifier: (x, y.new_tensor(mask)) for identifier, (x, y), mask in zip(ids, loaded, masks)}
    originals = {id(pairs[identifier][1]): y for identifier, (_, y) in zip(ids, loaded)}
    metadata["source_processed_file_sha256"] = [{"id": r["id"], "rgb": r["rgb"]["sha256"],
                                                "label": r["label"]["sha256"]} for r in selected]
    calls = []
    def loader(record, requested_base):
        require(Path(requested_base).resolve() == Path(base).resolve() and record["id"] in pairs,
                "Training-only mask override cannot load validation/panel/unknown records")
        calls.append(record["id"])
        return pairs[record["id"]]
    segmentation.load_pair = loader
    def batch(images, rng, batch_size=2, crop=224):
        return masked_batch(images, rng, originals, segmentation.MEAN, segmentation.STD, batch_size, crop)
    segmentation.make_batch = batch
    try:
        yield metadata, calls
    finally:
        segmentation.load_pair = original
        segmentation.make_batch = original_batch


def masked_batch(images, rng, originals, mean, std, batch_size=2, crop=224):
    """Frozen sampler draws/augmentations; eligibility uses full original y.

    No extra random draw is permitted because supervision was thinned. A chosen
    thin all-ignored crop fails after the same augmentation draws, without retry.
    """
    import torch
    xs, ys = [], []
    for _ in range(batch_size):
        index = int(rng.integers(len(images)))
        x, y = images[index]
        require(id(y) in originals, "Unknown training-mask tensor")
        original = originals[id(y)]
        for attempt in range(16):
            top, left = rng.integers(0, 449-crop, size=2)
            xx, yy = x[:, top:top+crop, left:left+crop], y[top:top+crop, left:left+crop]
            full = original[top:top+crop, left:left+crop]
            if torch.any(full != 255): break
        if not torch.any(full != 255): raise ValueError("Repeated all-void crops in a selected training image")
        if rng.random() < .5: xx, yy = xx.flip(-1), yy.flip(-1)
        if rng.random() < .5: xx, yy = xx.flip(-2), yy.flip(-2)
        rotations = int(rng.integers(4))
        xx, yy = xx.rot90(rotations, [-2, -1]), yy.rot90(rotations, [-2, -1])
        if not torch.any(yy != 255):
            raise ValueError("Fixed original-valid crop has no thinned supervision; fail closed without resampling")
        xs.append(xx); ys.append(yy)
    x = torch.stack(xs).float().div_(255)
    return (x - mean) / std, torch.stack(ys)


def require_cuda_terminal(root):
    """Reject live/unknown CUDA90 writers; no score field is consulted."""
    writer = safe(root, CUDA_OUT + "/writer.lock")
    if writer.exists():
        record = read(writer)
        require(not common.same_live_process(record) and
                not any(common.same_live_process(c) for c in record.get("children", [])), "CUDA90 writer/child is still live")
        raise RuntimeError("CUDA90 stale writer lease remains; recover it through its own supervisor first")
    leases = safe(root, CUDA_OUT + "/parallel")
    if leases.exists():
        for path in leases.glob("*/worker_*.lease.json"):
            record = read(path)
            require(not (record.get("state") == "reserved" and not record.get("pid")) and
                    not common.same_live_process(record), "CUDA90 live/unknown worker blocks pixel execution")
    source = read(safe(root, SOURCE_PLAN))
    expected = {safe(root, CUDA_OUT + "/" + run_key(s["identity"]) + "/result.json"): s for s in source["runs"]}
    actual = set(safe(root, CUDA_OUT).rglob("result.json"))
    require(len(expected) == 90 and actual == set(expected), "CUDA90 must have exact90 terminal result files first")
    for path, spec in expected.items():
        value = read(path)
        require(value.get("status") == "complete" and value.get("plan_sha256") == SOURCE_SHA and
                value.get("identity") == spec["identity"] and value.get("selection") == spec["selection"],
                "CUDA90 terminal result identity differs")
        require(sha(safe(root, value["log_file"])) == value["log_sha256"], "CUDA90 terminal log differs")


class Storage:
    """Own output scope/reserves; common Storage/constants are never changed."""
    def __init__(self, root, generation):
        self.root, self.generation = Path(root), generation
        self.base = safe(root, OUT + "/parallel/" + generation)
        self.state, self.lock = self.base / "budget.json", self.base / "budget.guard"

    def charge(self, count, refresh=False):
        observed = common.logical_bytes(self.root) if refresh or not self.state.exists() else 0
        with common.os_guard(self.lock):
            prior = read(self.state).get("accounted_bytes", 0) if self.state.exists() else 0
            estimate = max(prior, observed) + count + 4096
            require(estimate + EXTERNAL_RESERVE + 2 * WORKER_RESERVE < CAP, "Whole-project2GB pixel output reserve refused")
            bare_replace(self.state, {"accounted_bytes": estimate, "last_observed_bytes": observed,
                                     "generation": self.generation, "utc": utc()})

    def new(self, path, value):
        self.charge(len(raw(value))); bare_new(path, value)

    def replace(self, path, value):
        self.charge(len(raw(value))); bare_replace(path, value)

    def append(self, path, value):
        data = (json.dumps(value, allow_nan=False) + "\n").encode()
        self.charge(len(data))
        with path.open("ab") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())


def validate_existing(root, spec, plan, plan_sha):
    path = safe(root, OUT + "/" + run_key(spec["identity"]) + "/result.json")
    if not path.exists():
        return False
    value = read(path)
    require(value.get("status") == "complete" and value.get("plan_sha256") == plan_sha and
            value.get("identity") == spec["identity"] and value.get("selection") == spec["selection"] and
            value.get("runner_code_sha256") == plan["runner_code_sha256"] and
            value.get("helper_code_sha256") == plan["helper_code_sha256"], "Existing pixel result provenance differs; never overwrite")
    require(sha(safe(root, value["log_file"])) == value["log_sha256"], "Existing pixel log missing/changed")
    masking = value["pixel_supervision"]
    require(value.get("pixel_supervision_sha256") == hashlib.sha256(raw(masking)).hexdigest(),
            "Existing supervision metadata SHA differs")
    require(masking["available_valid_pixels_after"] == BUDGET and masking["seed"] == MASK_SEED + spec["identity"]["selection_seed"] and
            masking["ordered_selected_ids"] == spec["selection"]["selected_ids"] and
            sum(m["retained_valid_pixels"] for m in masking["images"]) == BUDGET, "Existing supervision budget differs")
    training = value["training"]
    require(training["steps"] == spec["steps"] and training["encoder_lr"] == spec["encoder_lr"] and
            training["seed"] == spec["identity"]["initialization_seed"] and
            training["identity"]["selected_ids"] == spec["selection"]["selected_ids"] and
            training["all_final_parameters_finite"] is True, "Existing training recipe differs")
    return True


class Backend:
    def __init__(self, runtime, weight_sha):
        import platform
        import numpy as np
        import torch
        import v2_segmentation as segmentation
        require(torch.cuda.is_available(), "CUDA required; no CPU fallback")
        require((torch.__version__, np.__version__, platform.python_version(), torch.version.cuda, torch.cuda.get_device_name(0)) ==
                (runtime["torch"], runtime["numpy"], runtime["cuda_python"], runtime["cuda_build"], runtime["device"]),
                "Exact source CUDA runtime mismatch")
        torch.set_num_threads(runtime["threads"])
        self.weight = Path(torch.hub.get_dir()) / "checkpoints/resnet18-f37072fd.pth"
        self.weight_sha = weight_sha
        require(self.weight.is_file() and sha(self.weight) == weight_sha, "Existing official weights required; no downloads")
        original_seed = segmentation.seed_all
        def cuda_seed(seed):
            original_seed(seed); torch.use_deterministic_algorithms(True, warn_only=True)
        segmentation.seed_all = cuda_seed
        self.torch, self.segmentation = torch, segmentation

    def execute(self, selected, validation, panel, base, spec, callback):
        require(sha(self.weight) == self.weight_sha, "Pretrained weight changed")
        torch, segmentation = self.torch, self.segmentation
        torch.cuda.reset_peak_memory_stats(); started = time.monotonic(); model = None
        original_loader = segmentation.load_pair
        original_batch = segmentation.make_batch
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("default")
                with training_masks(segmentation, selected, base, BUDGET,
                                    MASK_SEED + spec["identity"]["selection_seed"]) as (masking, calls):
                    model, training = segmentation.fit(selected, base, seed=spec["identity"]["initialization_seed"],
                        encoder_lr=spec["encoder_lr"], steps=spec["steps"], device="cuda:0", batch_size=2, crop=224, log_callback=callback)
                    require(calls == spec["selection"]["selected_ids"], "Frozen fit training-loader call order differs")
                require(segmentation.load_pair is original_loader and segmentation.make_batch is original_batch,
                        "Original loader/sampler not restored before evaluation")
                test = segmentation.evaluate(model, panel, base, "cuda:0")
                val = segmentation.evaluate(model, validation, base, "cuda:0")
                torch.cuda.synchronize()
            return {"training": training, "pixel_supervision": masking, "test": test, "validation": val,
                    "evaluation_original_loader_restored": True, "evaluation_original_batch_sampler_restored": True,
                    "crop_eligibility": "original_full_mask; identical optimization RNG draws; thin-empty crop fails without resampling",
                    "deterministic_warn_only": True,
                    "warnings": sorted(set(str(w.message) for w in caught)),
                    "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                    "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(), "total_seconds": time.monotonic() - started}
        finally:
            segmentation.load_pair = original_loader
            segmentation.make_batch = original_batch
            del model; gc.collect(); torch.cuda.empty_cache()


def current_lease(root, generation, plan_sha):
    lease = read(safe(root, OUT + "/writer.lock"))
    require(lease["generation"] == generation and lease["plan_sha256"] == plan_sha and
            lease["runner_code_sha256"] == sha(Path(__file__)) and common.same_live_process(lease), "Supervisor lease changed/died")
    return lease


def execute_partition(root, plan, plan_sha, generation, worker, storage, backend):
    manifest, design = read(safe(root, "v2/data/manifest.json")), read(safe(root, "configs/v2_design.json"))
    by_id = {r["id"]: r for r in manifest["pairs"]}
    splits = {s["id"]: s for s in design["source_splits"]}
    panel = [by_id[k] for k in plan["new_panel_image_ids"]]
    summary = {"worker": worker, "assigned_indices": list(range(worker, len(plan["runs"]), 2)),
               "executed_indices": [], "skipped_existing": [], "status": "running"}
    try:
        for index in summary["assigned_indices"]:
            if (storage.base / "stop.request.json").exists():
                summary["status"] = "cooperative_stop"; break
            current_lease(root, generation, plan_sha)
            spec = plan["runs"][index]
            if validate_existing(root, spec, plan, plan_sha):
                summary["skipped_existing"].append(index); continue
            load_plan(root, plan_sha)
            storage.charge(0, refresh=True)
            selected = [by_id[k] for k in spec["selection"]["selected_ids"]]
            source = splits[spec["identity"]["source_split"]]
            validation = [r for r in manifest["pairs"] if r["region"] in source["validation"]]
            require(len(selected) == len({r['id'] for r in selected}) == 12 and
                    all(r["region"] in source["train"] for r in selected) and len(validation) == 20 and len(panel) == 72 and
                    not {r['id'] for r in selected} & {r['id'] for r in validation + panel}, "Train/evaluation identity isolation differs")
            folder = safe(root, OUT + "/" + run_key(spec["identity"])); folder.mkdir(parents=True, exist_ok=True)
            claim = folder / "fit.lock"
            # Even dead fit claims are preserved; explicit manual inspection is required.
            storage.new(claim, {**common.process_info(), "generation": generation, "worker": worker,
                                "index": index, "plan_sha256": plan_sha})
            attempt = str(time.time_ns()); log = folder / ("training_" + attempt + ".jsonl")
            storage.new(folder / ("attempt_" + attempt + ".json"), {"plan_sha256": plan_sha, "identity": spec["identity"],
                        "runner_code_sha256": plan["runner_code_sha256"], "generation": generation, "worker": worker})
            try:
                log_size = 0
                def callback(entry):
                    nonlocal log_size
                    log_size += len(raw(entry))
                    require(log_size < WORKER_RESERVE // 2, "Unexpected training log growth")
                    storage.append(log, entry)
                    if entry["step"] == 1 or entry["step"] % 300 == 0:
                        print(json.dumps({"phase": "pixel_budget_training", "worker": worker, "index": index, "step": entry["step"]}), flush=True)
                payload = backend.execute(selected, validation, panel, safe(root, "v2/data"), spec, callback)
                value = {"format": "v2-pixel-budget-result-1", "status": "complete", "identity": spec["identity"],
                    "plan_sha256": plan_sha, "runner_code_sha256": plan["runner_code_sha256"],
                    "helper_code_sha256": plan["helper_code_sha256"], "source_cuda_plan_sha256": SOURCE_SHA,
                    "original_freeze_sha256": plan["original_freeze_sha256"],
                    "original_frozen_file_sha256": plan["original_frozen_file_sha256"], "protocol_sha256": plan["protocol_sha256"],
                    "selection": spec["selection"], "log_file": log.relative_to(root).as_posix(), "log_sha256": sha(log),
                    "scheduling": {"generation": generation, "worker": worker, "workers": 2, **common.process_info()},
                    "interpretation": "Post-panel-exposure descriptive secondary; original primary unchanged; no new holdout or annotation-cost equivalence",
                    "created_utc": utc(), **payload}
                value["pixel_supervision_sha256"] = hashlib.sha256(raw(value["pixel_supervision"])).hexdigest()
                require(len(raw(value)) + log_size < WORKER_RESERVE, "Per-fit output exceeds reserved4MB")
                storage.new(folder / "result.json", value)
                summary["executed_indices"].append(index)
            except BaseException as exc:
                storage.new(folder / ("failure_" + attempt + ".json"), {"plan_sha256": plan_sha,
                    "identity": spec["identity"], "error": type(exc).__name__ + ": " + str(exc)})
                raise
            finally:
                if claim.exists(): claim.rename(folder / ("claim_" + attempt + ".closed.json"))
        if summary["status"] == "running": summary["status"] = "complete"
    except BaseException as exc:
        summary.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        with common.os_guard(storage.base / "stop.guard"):
            if not (storage.base / "stop.request.json").exists():
                storage.new(storage.base / "stop.request.json", {"worker": worker, "utc": utc()})
    finally:
        summary.update(process=common.process_info(), utc=utc())
        storage.new(storage.base / f"worker_{worker}.summary.json", summary)
    return summary


def worker_main(args):
    root = Path(args.root).resolve(); plan, plan_sha = load_plan(root, args.plan_sha)
    storage = Storage(root, args.generation)
    leasepath = storage.base / f"worker_{args.worker_id}.lease.json"
    deadline = time.monotonic() + 30
    while True:
        parent = current_lease(root, args.generation, plan_sha)
        if any(c.get("worker") == args.worker_id and c.get("pid") == os.getpid() and common.same_live_process(c)
               for c in parent["children"]): break
        require(time.monotonic() < deadline, "Child PID not registered by supervisor")
        time.sleep(.1)
    own = read(leasepath)
    require(own["state"] == "reserved" and own["worker"] == args.worker_id and own["generation"] == args.generation,
            "Worker lease already claimed or mismatched")
    own.update(**common.process_info(), state="initializing"); storage.replace(leasepath, own)
    try:
        calibration = read(safe(root, "evidence/v2/calibration/calibration.json"))
        backend = Backend(plan["runtime"], calibration["environment"]["pretrained_weight_sha256"])
        own["state"] = "ready"; storage.replace(leasepath, own)
        deadline = time.monotonic() + 180
        while not (storage.base / "start.json").exists():
            current_lease(root, args.generation, plan_sha)
            if (storage.base / "stop.request.json").exists(): return 1
            require(time.monotonic() < deadline, "Launch barrier timed out")
            time.sleep(.2)
        summary = execute_partition(root, plan, plan_sha, args.generation, args.worker_id, storage, backend)
        return 0 if summary["status"] == "complete" else 1
    except BaseException as exc:
        summary = storage.base / f"worker_{args.worker_id}.summary.json"
        if not summary.exists(): storage.new(summary, {"status": "failed_initialization", "error": str(exc)})
        return 1
    finally:
        own.update(state="terminal", terminal_utc=utc()); storage.replace(leasepath, own)


def supervise(args):
    root = Path(args.root).resolve(); plan, plan_sha = load_plan(root)
    require(args.workers == 2, "Exactly two independent OS workers required")
    common.check_memory(2)
    require(common.logical_bytes(root) + EXTERNAL_RESERVE + 2 * WORKER_RESERVE < CAP, "Initial whole-project2GB reserve unavailable")
    generation = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
    out = safe(root, OUT); out.mkdir(parents=True, exist_ok=True)
    # Hold CUDA's admission mutex for the entire ablation to exclude restarts.
    with common.os_guard(safe(root, CUDA_OUT + "/parallel_admission.guard")):
        require_cuda_terminal(root)
        with common.os_guard(out / "admission.guard"):
            writer = out / "writer.lock"
            require(not writer.exists(), "Pixel writer lease already exists; never discard live/stale leases automatically")
            children_leases = list((out / "parallel").glob("*/worker_*.lease.json")) if (out / "parallel").exists() else []
            require(not any(common.same_live_process(read(path)) or
                    (read(path).get("state") == "reserved" and not read(path).get("pid")) for path in children_leases),
                    "Existing live/unknown pixel child blocks startup")
            lease = {**common.process_info(), "generation": generation, "workers": 2, "plan_sha256": plan_sha,
                     "runner_code_sha256": plan["runner_code_sha256"], "children": [], "utc": utc()}
            storage = Storage(root, generation); storage.charge(0, refresh=True); storage.new(writer, lease)
        children, handles = [], []
        summary = {"generation": generation, "plan_sha256": plan_sha, "workers": 2, "status": "initializing", "children": []}
        try:
            storage.new(storage.base / "execution.json", {"plan_sha256": plan_sha, "runner_code_sha256": plan["runner_code_sha256"],
                "helper_code_sha256": plan["helper_code_sha256"], "partition": "plan_index_modulo_2", "workers": 2,
                "external_growth_reserve_bytes": EXTERNAL_RESERVE, "per_worker_output_reserve_bytes": WORKER_RESERVE})
            for worker in range(2):
                common.check_memory(2 - worker)
                storage.new(storage.base / f"worker_{worker}.lease.json", {"state": "reserved", "pid": None,
                    "worker": worker, "generation": generation, "plan_sha256": plan_sha})
                stdout = (storage.base / f"worker_{worker}.stdout.txt").open("xb"); handles.append(stdout)
                process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--run", "--root", str(root),
                    "--worker-id", str(worker), "--generation", generation, "--plan-sha", plan_sha], cwd=root,
                    stdout=stdout, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                children.append((worker, process)); lease["children"].append({"worker": worker, **common.process_info(process.pid)})
                storage.replace(writer, lease)
                deadline = time.monotonic() + 180
                while read(storage.base / f"worker_{worker}.lease.json")["state"] != "ready":
                    require(process.poll() is None, "Worker failed before ready")
                    require(time.monotonic() < deadline, "Worker initialization timed out")
                    time.sleep(.2)
            storage.new(storage.base / "start.json", {"generation": generation, "utc": utc(), "children": lease["children"]})
            while any(process.poll() is None for _, process in children):
                if any(process.poll() not in (None, 0) for _, process in children):
                    with common.os_guard(storage.base / "stop.guard"):
                        if not (storage.base / "stop.request.json").exists():
                            storage.new(storage.base / "stop.request.json", {"reason": "child_failed", "utc": utc()})
                time.sleep(.5)
            summary["status"] = "complete" if all(process.returncode == 0 for _, process in children) else "failed"
        except BaseException as exc:
            summary.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
            with common.os_guard(storage.base / "stop.guard"):
                if not (storage.base / "stop.request.json").exists(): storage.new(storage.base / "stop.request.json", {"reason": str(exc)})
            # Never kill a fit; ask other workers to stop between fits and wait.
            for _, process in children:
                while process.poll() is None:
                    try: process.wait(timeout=1)
                    except subprocess.TimeoutExpired: pass
        finally:
            for handle in handles: handle.close()
            summary["children"] = [{"worker": worker, "pid": process.pid, "exit_code": process.poll()} for worker, process in children]
            summary["finished_utc"] = utc(); storage.new(storage.base / "supervisor_summary.json", summary)
            require(all(process.poll() is not None for _, process in children), "Live child: retain writer lease")
            reservations = [read(path) for path in storage.base.glob("worker_*.lease.json")]
            require(not any(r.get("state") == "reserved" and not r.get("pid") for r in reservations),
                    "Unknown launched child: retain writer lease for manual recovery")
            require(read(writer)["generation"] == generation, "Writer lease changed")
            writer.rename(storage.base / "global_lease.closed.json")
            print(json.dumps(summary), flush=True)
        return 0 if summary["status"] == "complete" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--workers", type=int, choices=[2], default=2)
    parser.add_argument("--worker-id", type=int, choices=[0, 1])
    parser.add_argument("--generation")
    parser.add_argument("--plan-sha")
    args = parser.parse_args(argv)
    if args.self_test:
        require(not args.run, "Self-test cannot run scientific fits")
        import unittest
        suite = unittest.defaultTestLoader.loadTestsFromName("test_v2_pixel_budget")
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    require(args.run and not args.self_test, "Real execution requires explicit --run; otherwise use --self-test")
    if args.worker_id is not None:
        require(args.generation and args.plan_sha, "Worker requires parent generation and plan SHA")
        return worker_main(args)
    return supervise(args)


if __name__ == "__main__":
    raise SystemExit(main())
