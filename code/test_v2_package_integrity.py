"""Focused temporary-fixture packaging integration; no scientific evidence.

Full scientific validators are explicitly mocked. Actual fixture COPY, budget,
write-ahead ledger and manifest operations use the production implementation.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import v2_package_delivery as p


def put(root, name, value):
    path = p.child(root, name); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else p.raw(value))
    return path


def pixel_fixture(root):
    guards = [p.PIXEL_OUT + "/admission.guard", p.PIXEL_OUT + "/parallel/synthetic/budget.guard",
              p.PIXEL_OUT + "/parallel/synthetic/stop.guard"]
    for name in guards: put(root, name, b"0")
    names = ["configs/v2_pixel_budget_plan.json", p.PIXEL_OUT + "/run_fixture/result.json"]
    for name in names: put(root, name, {"synthetic_opaque_bytes": name})
    bundle = {"passed": True, "file_sha256": {name:p.sha(p.child(root,name)) for name in names},
              "excluded_history_mutex_files": [{"path":name,"bytes":1} for name in guards]}
    inventory = p.pixel_guard_inventory(root, bundle)
    operations = []
    for name in names + guards:
        path = p.child(root,name)
        operations.append({"source":name,"target":name,"action":"copy", "sha256":p.sha(path),"bytes":path.stat().st_size,
                           "origin":p.PIXEL_GUARD_ORIGIN if name in guards else "pixel_budget_closed_execution_inventory"})
    plan = {"destination":p.DEFAULT_DESTINATION,"operations":operations,"pixel_budget_delivery_inventory":bundle,
            "pixel_budget_guard_files":inventory,"copy_additional_bytes":sum(v["bytes"] for v in operations),
            "metadata_reservation_bytes":100_000,"reproduction_temporary_reservation_bytes":0}
    return bundle, plan


class PackagingIntegrityChecks(unittest.TestCase):
    def test_active_validator_refusal_blocks_plan_mutation_and_refresh(self):
        with tempfile.TemporaryDirectory(prefix="active-package-gate-") as folder:
            root=Path(folder).resolve();put(root,"configs/v2_active_gpu_amendment.json",{"synthetic":True})
            validator=mock.Mock(return_value={"passed":False,"errors":["synthetic semantic refusal"]})
            incomplete={"destination":p.DEFAULT_DESTINATION,"operations":[],"copy_additional_bytes":0,
                        "metadata_reservation_bytes":10_000}
            with mock.patch.dict(sys.modules,{"v2_active_gpu_results":SimpleNamespace(validate_bundle=validator)}), mock.patch.object(
                    p,"gates",return_value=([{"passed":True}],{})):
                with self.assertRaisesRegex(ValueError,"Full active GPU576"):p.build_plan(root)
                with self.assertRaisesRegex(ValueError,"Full active GPU576"):p.apply_actions(root,incomplete)
                with self.assertRaisesRegex(ValueError,"Full active GPU576"):p.validate_refreshed_evidence(root,{})
            self.assertEqual(validator.call_count,3)
            self.assertFalse((root/p.DEFAULT_DESTINATION).exists())
            self.assertFalse((root/"evidence/v2/package_receipts").exists())
            self.assertIsNone(p._MIGRATION_BUDGET)

    def test_active_binding_is_small_current_and_requires_amendment(self):
        with tempfile.TemporaryDirectory(prefix="active-package-binding-") as folder:
            root=Path(folder).resolve()
            names=("configs/v2_active_gpu_amendment.json","evidence/v2/active_run_completeness.json",
                   "tables/v2/analysis_identity.json","code/v2_active_gpu_results.py")
            for name in names:put(root,name,b"synthetic immutable binding bytes")
            opaque={"passed":True,"errors":[],"audit":{"results":{"syntheticGPU":"a"*64},
                    "cpu_reference_files":{"syntheticCPU":"b"*64},"role":"synthetic descriptive role",
                    "active_model_counts":{"resnet18_unet":90,"dinov2_mlp128":486}}}
            validator=mock.Mock(return_value=opaque)
            with mock.patch.dict(sys.modules,{"v2_active_gpu_results":SimpleNamespace(validate_bundle=validator)}):
                binding=p.verify_active_delivery(root)
                self.assertNotIn("audit",binding)
                self.assertLess(len(p.raw(binding)),2000)
                plan={"active_bundle_binding":binding}
                self.assertEqual(p.verify_active_delivery(root,plan=plan),binding)
                path=root/names[-1];path.write_bytes(path.read_bytes()+b"changed")
                with self.assertRaisesRegex(ValueError,"binding changed"):p.verify_active_delivery(root,plan=plan)
            (root/names[0]).unlink()
            with self.assertRaisesRegex(ValueError,"amendment disappeared"):p.verify_active_delivery(root,plan=plan)

    def test_audited_pixel_guards_are_exact_one_byte_scoped_copy(self):
        with tempfile.TemporaryDirectory(prefix="pixel-package-scope-") as folder:
            root=Path(folder).resolve();bundle,plan=pixel_fixture(root)
            expected={entry["path"] for entry in bundle["excluded_history_mutex_files"]}
            self.assertEqual(set(p.pixel_guard_inventory(root,bundle)),expected)
            for name in expected:
                p.source_allowed(name,"copy",p.PIXEL_GUARD_ORIGIN)
                for action,origin in (("move",p.PIXEL_GUARD_ORIGIN),("copy","explicit_extra")):
                    with self.subTest(action=action,origin=origin),self.assertRaises(ValueError):p.source_allowed(name,action,origin)
            for name in ("code/budget.guard",p.PIXEL_OUT+"/parallel/../budget.guard",p.PIXEL_OUT+"/parallel/synthetic/other.guard"):
                with self.subTest(name=name),self.assertRaises(ValueError):p.source_allowed(name,"copy",p.PIXEL_GUARD_ORIGIN)
            first=root/next(iter(expected));original=first.read_bytes()
            for contents in (b"1",b"00",b""):
                first.write_bytes(contents)
                with self.subTest(contents=contents),self.assertRaises(ValueError):p.pixel_guard_inventory(root,bundle)
            first.write_bytes(original)
            for case in ("duplicate","outside","wrong_size"):
                bad=copy.deepcopy(bundle)
                if case=="duplicate":bad["excluded_history_mutex_files"].append(dict(bad["excluded_history_mutex_files"][0]))
                elif case=="outside":bad["excluded_history_mutex_files"][0]["path"]="runtime/guard"
                else:bad["excluded_history_mutex_files"][0]["bytes"]=True
                with self.subTest(case=case),self.assertRaises(ValueError):p.pixel_guard_inventory(root,bad)

    def test_pixel_plan_operations_cannot_omit_or_relabel_markers(self):
        with tempfile.TemporaryDirectory(prefix="pixel-package-operations-") as folder:
            root=Path(folder).resolve();bundle,plan=pixel_fixture(root)
            validator=mock.Mock(return_value=bundle)
            with mock.patch.dict(sys.modules,{"v2_audit_pixel_budget":SimpleNamespace(validate_bundle=validator)}):
                p.verify_pixel_delivery(root,plan=plan)
                for case in ("omit","origin","move","sha","extra"):
                    bad=copy.deepcopy(plan);index=next(i for i,e in enumerate(bad["operations"]) if e["origin"]==p.PIXEL_GUARD_ORIGIN)
                    if case=="omit":bad["operations"].pop(index)
                    elif case=="origin":bad["operations"][index]["origin"]="explicit_extra"
                    elif case=="move":bad["operations"][index]["action"]="move"
                    elif case=="sha":bad["operations"][index]["sha256"]="0"*64
                    else:
                        extra=copy.deepcopy(bad["operations"][index]);extra["source"]=extra["target"]=p.PIXEL_OUT+"/parallel/extra/budget.guard"
                        bad["operations"].append(extra)
                    with self.subTest(case=case),self.assertRaises(ValueError):p.verify_pixel_delivery(root,plan=bad)
            (root/"configs/v2_pixel_budget_plan.json").unlink()
            with self.assertRaisesRegex(ValueError,"Pixel plan is required"):p.verify_pixel_delivery(root,plan=plan)

    def test_real_fixture_copy_preserves_guards_manifest_and_budget(self):
        with tempfile.TemporaryDirectory(prefix="pixel-package-copy-") as folder:
            root=Path(folder).resolve();bundle,plan=pixel_fixture(root)
            before=p.logical_bytes(root);validator=mock.Mock(return_value=bundle)
            with mock.patch.dict(sys.modules,{"v2_audit_pixel_budget":SimpleNamespace(validate_bundle=validator)}):
                activation=p.apply_actions(root,plan)
                dest=p.child(root,p.DEFAULT_DESTINATION)
                manifest=p.read(dest/"delivery_manifest.json");entries={e["relative_path"]:e for e in manifest["files"]}
                p.verify_pixel_delivery(dest,old_entries=entries)
                for name in plan["pixel_budget_guard_files"]:
                    self.assertEqual((dest/name).read_bytes(),b"0")
                    self.assertEqual(entries[name]["bytes"],1)
                    self.assertEqual(entries[name]["sha256"],plan["pixel_budget_guard_files"][name]["sha256"])
                capacity=activation["capacity_accounting"]
                self.assertTrue(capacity["passed"])
                self.assertEqual(capacity["foreign_delta"],0)
                self.assertEqual(capacity["charged"],p.logical_bytes(root)-before)
                marker=next(iter(plan["pixel_budget_guard_files"]))
                bad=copy.deepcopy(entries);bad[marker]["sha256"]="0"*64
                with self.assertRaisesRegex(ValueError,"Immutable pixel mutex"):p.verify_pixel_delivery(dest,old_entries=bad)
                (dest/marker).unlink()
                with self.assertRaisesRegex(ValueError,"mutex marker missing"):p.verify_pixel_delivery(dest,old_entries=entries)


if __name__=="__main__":
    unittest.main(verbosity=2)
