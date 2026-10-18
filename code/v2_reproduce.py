"""Reproduce completed v2 tables, optionally reload the fixed saved checkpoint.

Uses the current Python and the TARGET root's frozen scripts. No training,
downloads, dependency installation, feature loading or source-root imports.
--self-test uses small temporary fixtures, never the real experiment tree.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
NUMERICAL_OUTPUTS = tuple("tables/v2/" + name for name in (
    "conditions_by_source.csv", "conditions.csv", "regions.csv", "classes.csv", "contrasts.json", "primary.json"))
REPORT = "evidence/v2/reproduction_check.json"
RUN_AUDIT = "evidence/v2/run_completeness.json"
ANALYSIS_IDENTITY = "tables/v2/analysis_identity.json"
EXPECTED_COUNTS = {"fits": 576, "conditions_by_source": 192, "conditions": 64,
                   "regions_rows": 1536, "classes_rows": 512}
BUDGET_POLICY = "project_storage_budget.json"
CAP = 2_000_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def reject_redirected_path(path):
    absolute = Path(os.path.abspath(path))
    for item in reversed((absolute, *absolute.parents)):
        try:
            info = os.lstat(item)
        except FileNotFoundError:
            continue
        tag = getattr(info, "st_reparse_tag", 0)
        # Windows name-surrogate bit covers junctions/symlinks. Ordinary
        # OneDrive cloud placeholder reparse tags do not have this bit.
        require(not stat.S_ISLNK(info.st_mode) and not tag & 0x20000000,
                "Redirecting symlink/junction/name-surrogate path rejected")
    return absolute


def budget_scope(root, requested=None):
    root = reject_redirected_path(root).resolve()
    policy_root = None
    policy = None
    for ancestor in (root, *root.parents):
        path = ancestor / BUDGET_POLICY
        if path.exists():
            reject_redirected_path(path)
            policy = read(path)
            require(policy.get("schema") == "mdpi-resource-budget-1" and policy.get("cap_bytes") == CAP and
                    policy.get("scope") == "this directory and descendants", "Invalid ancestor storage-budget policy")
            policy_root = ancestor
            break
    selected = policy_root or root
    if requested is not None:
        selected = reject_redirected_path(requested).resolve()
        require(root.is_relative_to(selected), "Explicit budget root must be a target ancestor")
        require(policy_root is None or policy_root.is_relative_to(selected),
                "Explicit budget root cannot narrow an ancestor policy scope")
    metadata = {"cap_bytes": CAP, "target_relative_to_budget_root": root.relative_to(selected).as_posix(),
                "budget_root_ancestor_levels": len(root.parts) - len(selected.parts),
                "selection": "explicit_ancestor" if requested is not None else "nearest_ancestor_policy" if policy_root else "standalone_target_fallback"}
    if policy_root is not None:
        path = policy_root / BUDGET_POLICY
        metadata.update(policy_relative_to_budget_root=path.relative_to(selected).as_posix(), policy_sha256=sha(path))
    return selected, metadata


def ensure_budget_space(scope, extra):
    current = project_bytes(scope)
    require(current + extra < CAP, "Insufficient space under entire budget-scope2GB logical limit")
    return current


def target(root, name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "Expected a relative POSIX target path")
    item = Path(name)
    require(not item.is_absolute() and ".." not in item.parts, "Unsafe target-relative path")
    root = reject_redirected_path(root).resolve()
    result = reject_redirected_path(root / item).resolve()
    require(result.is_relative_to(root), "Target file escapes the selected root")
    return result


def hashes(root, names):
    return {name: sha(target(root, name)) for name in names}


def result_inventory(root):
    return {path.relative_to(root).as_posix(): sha(target(root, path.relative_to(root).as_posix()))
            for path in sorted(target(root, "evidence/v2/runs").rglob("result.json"))}


def verify_hashes(root, mapping, scope):
    require(isinstance(mapping, dict) and bool(mapping), f"Missing {scope} SHA map")
    for name, checksum in mapping.items():
        require(isinstance(checksum, str) and len(checksum) == 64 and sha(target(root, name)) == checksum,
                f"{scope} SHA mismatch: {name}")


def project_bytes(root):
    # Conservative logical accounting: hard-linked files count separately.
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file() and not path.is_symlink())


def dependency_check(mode):
    names = ("numpy",) if mode == "tables" else ("numpy", "torch", "torchvision", "PIL")
    missing = [name for name in names if importlib.util.find_spec(name) is None]
    require(not missing, "Missing dependencies in current Python: " + ", ".join(missing) +
            ". Nothing is installed automatically; select a prepared environment.")


def invoke(root, relative, with_root, report):
    script = target(root, relative)
    command = [sys.executable, "-B", str(script)]
    if with_root:
        command += ["--root", str(root)]
    event = {"script": relative, "uses_current_python": True,
             "cwd": ".", "arguments": ["--root", "."] if with_root else []}
    report["commands"].append(event)
    process = subprocess.run(command, cwd=root, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=False)
    event.update(returncode=process.returncode, stdout_tail=process.stdout[-16384:], stderr_tail=process.stderr[-16384:])
    require(process.returncode == 0, f"Target script failed ({process.returncode}): {relative}")


def verify_tables_evidence(root, report, frozen, initial_results):
    audit = read(target(root, RUN_AUDIT))
    require(audit.get("passed") is True and audit.get("expected_total") == 576 and
            audit.get("validated_runs") == audit.get("observed_result_files") == 576,
            "Target run audit did not pass the complete576 matrix")
    require(all(not audit.get(key) for key in ("errors", "missing", "extra", "duplicates")),
            "Target run audit has unresolved errors or matrix differences")
    require(audit.get("audit_code_sha256") == frozen["code/v2_audit_runs.py"], "Target audit code identity differs")
    require(audit.get("results") == initial_results and len(initial_results) == 576,
            "Audited result inventory differs from the pre-reproduction inventory")
    for category in ("inputs", "artifacts", "results"):
        verify_hashes(root, audit[category], "Audited " + category)
    analysis = read(target(root, ANALYSIS_IDENTITY))
    require(analysis.get("audit_sha256") == sha(target(root, RUN_AUDIT)), "Analysis is not bound to this rerun audit")
    require(analysis.get("analysis_code_sha256") == frozen["code/v2_statistics.py"] and
            analysis.get("audit_code_sha256") == audit["audit_code_sha256"], "Analysis code identity differs")
    for key, expected in EXPECTED_COUNTS.items():
        require(analysis.get("counts", {}).get(key) == expected, "Analysis count mismatch: " + key)
    require(analysis.get("result_sha256") == audit["results"] and
            analysis.get("audited_input_sha256") == audit["inputs"] and
            analysis.get("audited_artifact_sha256") == audit["artifacts"], "Analysis/audit provenance maps differ")
    outputs = hashes(root, NUMERICAL_OUTPUTS)
    require(analysis.get("output_sha256") == outputs, "Analysis output SHA map differs from six numerical files")
    require(result_inventory(root) == initial_results, "Results changed while reproducing tables")
    verify_hashes(root, frozen, "Frozen code/data/config evidence")
    report.update(audit_report_sha256=sha(target(root, RUN_AUDIT)),
                  analysis_identity_sha256=sha(target(root, ANALYSIS_IDENTITY)),
                  numerical_outputs_after_sha256=outputs, validated_counts=analysis["counts"],
                  result_sha256=initial_results, frozen_input_sha256=frozen)
    return audit


def verify_reload(root, report, frozen, audit, freeze_sha, numerical, initial_results):
    path = "evidence/v2/checkpoint_reload.json"
    check = read(target(root, path))
    require(check.get("passed") is True and check.get("matched_images") == 72 and check.get("matched_regions") == 24,
            "Checkpoint reload did not match the complete72-image/24-region panel")
    for key in ("all_integer_confusion_matrices_exact", "aggregate_exact", "checkpoint_predetermined_not_score_selected"):
        require(check.get(key) is True, "Checkpoint reload check failed: " + key)
    require(check.get("refitting_performed") is False and check.get("device") == "cpu", "Unexpected reload execution scope")
    require(check.get("freeze_sha256") == freeze_sha and
            check.get("manifest_sha256") == frozen["v2/data/manifest.json"] and
            check.get("verifier_sha256") == frozen["code/v2_reload_checkpoint.py"] and
            check.get("model_code_sha256") == frozen["code/v2_segmentation.py"], "Reload code/data/freeze binding differs")
    predetermined = "evidence/v2/runs/resnet18_unet/source0_skewed5_1_b12_s0_i0_region_kcenter/result.json"
    require(check.get("result_sha256") == audit["results"].get(predetermined), "Reload result is not the predetermined audited fit")
    require(check.get("expected_confusion_digest") == check.get("reloaded_confusion_digest") and
            isinstance(check.get("expected_confusion_digest"), str) and len(check["expected_confusion_digest"]) == 64,
            "Reload confusion digests differ")
    require(check.get("checkpoint_sha256") in audit["artifacts"].values(), "Reload checkpoint is not an audited artifact")
    require(hashes(root, NUMERICAL_OUTPUTS) == numerical and result_inventory(root) == initial_results,
            "Reload changed numerical tables or run results")
    verify_hashes(root, frozen, "Frozen inputs after reload")
    report["reload"] = {"passed": True, "report": path, "report_sha256": sha(target(root, path)),
                        "matched_images": 72, "matched_regions": 24,
                        "checkpoint_sha256": check["checkpoint_sha256"], "refitting_performed": False}


def reproduce(root, mode="tables", budget_root=None):
    root = reject_redirected_path(root).resolve()
    report = {"format": "v2-reproduction-check-1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "mode": mode, "passed": False, "tables_passed": False, "commands": [], "errors": [],
              "wrapper_code_sha256": sha(Path(__file__)), "python_version": sys.version,
              "execution_policy": "Current Python executes only selected target-root frozen scripts; no installs, downloads or refitting",
              "numerical_outputs_before_sha256": {}, "numerical_outputs_after_sha256": {}}
    try:
        require(mode in ("tables", "reload"), "Unsupported reproduction mode")
        require(root.is_dir(), "Target root does not exist")
        scope, storage = budget_scope(root, budget_root)
        report["storage_budget"] = storage
        report["storage_budget"]["logical_bytes_before"] = ensure_budget_space(scope, 0)
        # Missing baseline tables stop before either scientific script is run.
        report["numerical_outputs_before_sha256"] = hashes(root, NUMERICAL_OUTPUTS)
        dependency_check("tables")
        freeze_path = target(root, "configs/v2_freeze.json")
        freeze = read(freeze_path)
        freeze_sha = sha(freeze_path)
        report["freeze_sha256"] = freeze_sha
        require(freeze.get("status") == "FROZEN_BEFORE_NEW_PANEL_EVALUATION" and
                freeze.get("expected_full_runs") == 90 and freeze.get("expected_frozen_runs") == 486 and
                freeze.get("expected_total_runs") == 576, "Expected completed v2 90+486 freeze")
        frozen = freeze["file_sha256"]
        required = {"code/v2_audit_runs.py", "code/v2_statistics.py", "code/v2_segmentation.py",
                    "code/v2_reload_checkpoint.py", "v2/data/manifest.json"}
        require(required <= set(frozen), "Freeze misses reproduction execution/data bindings")
        verify_hashes(root, frozen, "Frozen inputs before reproduction")
        initial_results = result_inventory(root)
        require(len(initial_results) == 576, "Exactly576 existing result files required; wait for the completed matrix")
        # One atomic table temporary plus audit/identity/check reports need room.
        headroom = max(target(root, name).stat().st_size for name in NUMERICAL_OUTPUTS) + 4_000_000
        report["storage_budget"]["temporary_reservation_bytes"] = headroom
        ensure_budget_space(scope, headroom)
        invoke(root, "code/v2_audit_runs.py", True, report)
        ensure_budget_space(scope, headroom)
        # Do not let statistics run after an auditor that returned0 with bad evidence.
        audit = read(target(root, RUN_AUDIT))
        require(audit.get("passed") is True and audit.get("validated_runs") == 576,
                "Complete576 audit gate required before statistics")
        invoke(root, "code/v2_statistics.py", True, report)
        ensure_budget_space(scope, 0)
        audit = verify_tables_evidence(root, report, frozen, initial_results)
        require(report["numerical_outputs_after_sha256"] == report["numerical_outputs_before_sha256"],
                "Recomputed numerical outputs differ from delivered baseline SHA; no output was silently accepted")
        require(sha(freeze_path) == freeze_sha, "Freeze file changed during table reproduction")
        report["tables_passed"] = True
        if mode == "reload":
            dependency_check("reload")
            ensure_budget_space(scope, 4_000_000)
            invoke(root, "code/v2_reload_checkpoint.py", False, report)
            ensure_budget_space(scope, 0)
            verify_reload(root, report, frozen, audit, freeze_sha,
                          report["numerical_outputs_before_sha256"], initial_results)
            require(sha(freeze_path) == freeze_sha, "Freeze file changed during checkpoint reload")
        report["storage_budget"]["logical_bytes_after_execution"] = ensure_budget_space(scope, 0)
        report["passed"] = True
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    return report


def write_report(root, report, budget_root=None):
    root = reject_redirected_path(root).resolve()
    require(root.is_dir(), "Cannot write a report outside an existing target root")
    destination = target(root, REPORT)
    scope, metadata = budget_scope(root, budget_root)
    report.setdefault("storage_budget", metadata)
    report["storage_budget"]["logical_bytes_before_report_write"] = ensure_budget_space(scope, 0)
    data = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ensure_budget_space(scope, len(data))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_bytes(data); temporary.replace(destination)
    ensure_budget_space(scope, 0)


class FixtureChecks(unittest.TestCase):
    def test_parent_budget_scope_cannot_be_shrunk_and_peak_is_global(self):
        with tempfile.TemporaryDirectory(prefix="v2-budget-fixture-") as directory:
            parent = Path(directory).resolve()
            root = parent / "delivery" / "v2"; root.mkdir(parents=True)
            policy = parent / BUDGET_POLICY
            policy.write_text(json.dumps({"schema": "mdpi-resource-budget-1", "cap_bytes": CAP,
                                         "scope": "this directory and descendants"}), encoding="utf-8")
            scope, metadata = budget_scope(root)
            self.assertEqual(scope, parent)
            self.assertEqual(metadata["target_relative_to_budget_root"], "delivery/v2")
            with self.assertRaisesRegex(ValueError, "cannot narrow"):
                budget_scope(root, root)
            with patch(__name__ + ".project_bytes", side_effect=lambda p: 1_995_000_000 if p == parent else 150_000_000):
                with self.assertRaisesRegex(ValueError, "entire budget-scope"):
                    ensure_budget_space(scope, 6_000_000)
                ensure_budget_space(root, 6_000_000)  # Old target-only check would incorrectly pass.
            policy.unlink()
            self.assertEqual(budget_scope(root)[0], root)

    def test_target_scoped_subprocess_and_identity_gate(self):
        # Deliberately tiny fake target scripts, data and576 marker files live
        # only in an automatically removed OS temporary directory, never ROOT.
        with tempfile.TemporaryDirectory(prefix="v2-reproduction-fixture-") as directory:
            root = Path(directory).resolve()
            def put(name, content):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            for name in NUMERICAL_OUTPUTS:
                put(name, "synthetic fixture: " + name + "\n")
            for index in range(576):
                put(f"evidence/v2/runs/synthetic/{index}/result.json", "{}\n")
            put("v2/data/manifest.json", "{}\n")
            put("code/v2_segmentation.py", "# fixture only\n")
            put("code/v2_reload_checkpoint.py", "raise RuntimeError('Reload must not run in tables mode')\n")
            put("code/v2_audit_runs.py", '''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
f=json.loads((root/'configs/v2_freeze.json').read_text())
r={p.relative_to(root).as_posix():h(p) for p in (root/'evidence/v2/runs').rglob('result.json')}
a=dict(passed=True,expected_total=576,validated_runs=576,observed_result_files=576,errors=[],missing=[],extra=[],duplicates=[],audit_code_sha256=h(Path(__file__)),inputs=f['file_sha256'],artifacts={'v2/data/manifest.json':h(root/'v2/data/manifest.json')},results=r)
(root/'evidence/v2/run_completeness.json').write_text(json.dumps(a))
''')
            put("code/v2_statistics.py", '''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((root/'evidence/v2/run_completeness.json').read_text())
names=['conditions_by_source.csv','conditions.csv','regions.csv','classes.csv','contrasts.json','primary.json']
o={'tables/v2/'+name:h(root/'tables/v2'/name) for name in names}
j=dict(audit_sha256=h(root/'evidence/v2/run_completeness.json'),analysis_code_sha256=h(Path(__file__)),audit_code_sha256=a['audit_code_sha256'],counts=dict(fits=576,conditions_by_source=192,conditions=64,regions_rows=1536,classes_rows=512),result_sha256=a['results'],audited_input_sha256=a['inputs'],audited_artifact_sha256=a['artifacts'],output_sha256=o)
(root/'tables/v2/analysis_identity.json').write_text(json.dumps(j))
''')
            frozen_names = ["code/v2_audit_runs.py", "code/v2_statistics.py", "code/v2_reload_checkpoint.py",
                            "code/v2_segmentation.py", "v2/data/manifest.json"]
            frozen = hashes(root, frozen_names)
            put("configs/v2_freeze.json", json.dumps({"status": "FROZEN_BEFORE_NEW_PANEL_EVALUATION",
                "expected_full_runs": 90, "expected_frozen_runs": 486, "expected_total_runs": 576, "file_sha256": frozen}))
            baseline = hashes(root, NUMERICAL_OUTPUTS)
            report = reproduce(root)
            self.assertTrue(report["passed"], report["errors"])
            self.assertEqual([event["script"] for event in report["commands"]], ["code/v2_audit_runs.py", "code/v2_statistics.py"])
            self.assertEqual(report["numerical_outputs_after_sha256"], baseline)
            write_report(root, report)
            self.assertTrue(read(root / REPORT)["passed"])
            # A code mutation fails before executing either target script.
            put("code/v2_statistics.py", "raise RuntimeError('must not execute changed code')\n")
            bad = reproduce(root)
            self.assertFalse(bad["passed"]); self.assertEqual(bad["commands"], [])
            self.assertIn("SHA mismatch", bad["errors"][0]["message"])
            # A stub can bind its own newly emitted table honestly, but that
            # must still fail comparison with the delivered numerical baseline.
            numeric_drift = '''import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((root/'evidence/v2/run_completeness.json').read_text())
p=root/'tables/v2/conditions.csv';p.write_text(p.read_text()+'changed numerical fixture\\n')
names=['conditions_by_source.csv','conditions.csv','regions.csv','classes.csv','contrasts.json','primary.json']
j=dict(audit_sha256=h(root/'evidence/v2/run_completeness.json'),analysis_code_sha256=h(Path(__file__)),audit_code_sha256=a['audit_code_sha256'],counts=dict(fits=576,conditions_by_source=192,conditions=64,regions_rows=1536,classes_rows=512),result_sha256=a['results'],audited_input_sha256=a['inputs'],audited_artifact_sha256=a['artifacts'],output_sha256={'tables/v2/'+n:h(root/'tables/v2'/n) for n in names})
(root/'tables/v2/analysis_identity.json').write_text(json.dumps(j))
'''
            put("code/v2_statistics.py", numeric_drift)
            frozen = hashes(root, frozen_names)
            put("configs/v2_freeze.json", json.dumps({"status": "FROZEN_BEFORE_NEW_PANEL_EVALUATION",
                "expected_full_runs": 90, "expected_frozen_runs": 486, "expected_total_runs": 576, "file_sha256": frozen}))
            drift = reproduce(root)
            self.assertFalse(drift["passed"])
            self.assertNotEqual(drift["numerical_outputs_after_sha256"], baseline)
            self.assertIn("delivered baseline SHA", drift["errors"][0]["message"])

    def test_missing_baseline_and_path_escape_stop(self):
        with tempfile.TemporaryDirectory(prefix="v2-reproduction-fixture-") as directory:
            root = Path(directory).resolve()
            report = reproduce(root)
            self.assertFalse(report["passed"]); self.assertEqual(report["commands"], [])
            for name in ("../escape", "C:/outside", "nested\\escape"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    target(root, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Completed project/delivery root; execute its own frozen code")
    parser.add_argument("--mode", choices=("tables", "reload"), default="tables")
    parser.add_argument("--budget-root", type=Path, help="Optional target ancestor; cannot narrow an existing ancestor storage policy")
    parser.add_argument("--self-test", action="store_true", help="Temporary synthetic target fixture only; never run real tables/reload")
    args = parser.parse_args(argv)
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureChecks))
        return 0 if result.wasSuccessful() else 1
    try:
        report = reproduce(args.root, args.mode, args.budget_root)
        write_report(args.root, report, args.budget_root)
    except (OSError, ValueError) as exc:
        print(f"Cannot save target reproduction report: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": report["passed"], "tables_passed": report["tables_passed"],
                      "mode": report["mode"], "report": REPORT, "errors": report["errors"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
