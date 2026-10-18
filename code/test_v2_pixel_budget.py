"""Synthetic-only pixel-budget checks; never access real model outcomes."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import v2_pixel_budget as m


class PixelBudgetChecks(unittest.TestCase):
    def test_plan_exact27_binding_code_helper_protocol_and_supervision(self):
        with tempfile.TemporaryDirectory(prefix="pixel-plan-") as directory:
            root=Path(directory)
            mapping={}
            for i in range(53):
                name=f"frozen/input{i}.json";m.bare_new(m.safe(root,name),{"synthetic":i})
                mapping[name]=m.sha(m.safe(root,name))
            freeze={"file_sha256":mapping}
            m.bare_new(m.safe(root,"configs/v2_freeze.json"),freeze)
            helper=m.safe(root,m.HELPER);helper.parent.mkdir(parents=True,exist_ok=True)
            helper.write_bytes(Path(m.common.__file__).read_bytes())
            m.bare_new(m.safe(root,m.PROTOCOL),{"synthetic":"protocol"})
            strategies=["kcenter","region_kcenter","permuted_region_kcenter"]+[f"unused{i}" for i in range(7)]
            runs=[{"identity":{"model":"resnet18_unet","source_split":f"source{s}","pool":"skewed5_1","budget":12,
                "selection_seed":seed,"initialization_seed":seed,"strategy":strategy},
                "selection":{"selected_ids":[f"train__{j}" for j in range(12)]},"encoder_lr":.0001,"steps":600}
                for s in range(3) for seed in range(3) for strategy in strategies]
            source={"runs":runs,"runtime":{"threads":2},"original_freeze_sha256":m.sha(m.safe(root,"configs/v2_freeze.json")),
                    "original_frozen_file_sha256":mapping,"new_panel_image_ids":[f"panel__{j}" for j in range(72)]}
            m.bare_new(m.safe(root,m.SOURCE_PLAN),source);source_sha=m.sha(m.safe(root,m.SOURCE_PLAN))
            plan={"format":"v2-pixel-budget-plan-1","status":"LOCKED_BEFORE_PIXEL_BUDGET_FITS_AFTER_PANEL_EXPOSURE",
                "prior_target_exposure":True,"runner_code_sha256":m.sha(Path(m.__file__)),
                "helper_code_sha256":{m.HELPER:m.sha(helper)},"protocol_sha256":m.sha(m.safe(root,m.PROTOCOL)),
                "source_cuda_plan":m.SOURCE_PLAN,"source_cuda_plan_sha256":source_sha,
                "original_freeze_sha256":source["original_freeze_sha256"],"original_frozen_file_sha256":mapping,
                "runs":[r for r in runs if r["identity"]["strategy"] in m.STRATEGIES],"expected_runs":27,
                "runtime":source["runtime"],"new_panel_image_ids":source["new_panel_image_ids"],
                "supervision":{"processed_grid":[448,448],"available_valid_pixel_budget":2300000,"mask_seed_base":2026101811,
                    "mask_order":"ordered_selected_ids_then_row_major_original_valid_positions","sampling":"uniform_remove_without_replacement",
                    "original_void_remains_ignored":True}}
            path=m.safe(root,m.PLAN);m.bare_new(path,plan)
            with patch.object(m,"SOURCE_SHA",source_sha):
                self.assertEqual(len(m.load_plan(root)[0]["runs"]),27)
                for field in ("runner_code_sha256","helper_code_sha256","supervision","runs"):
                    bad=json.loads(json.dumps(plan))
                    if field=="runner_code_sha256":bad[field]="wrong"
                    elif field=="helper_code_sha256":bad[field][m.HELPER]="wrong"
                    elif field=="supervision":bad[field]["available_valid_pixel_budget"]+=1
                    else:bad[field][0]["selection"]["selected_ids"].reverse()
                    path.write_bytes(m.raw(bad))
                    with self.subTest(field=field),self.assertRaises(RuntimeError):m.load_plan(root)
                path.write_bytes(m.raw(plan))
                m.safe(root,m.PROTOCOL).write_bytes(b"changed protocol")
                with self.assertRaisesRegex(RuntimeError,"protocol SHA"):m.load_plan(root)

    def test_exact_large_budget_reproducible_without_replacement(self):
        masks = [np.full((448, 448), i % 8, dtype=np.uint8) for i in range(12)]
        masks[0].ravel()[:105175] = 255  # Exactly2,303,273 original valid pixels.
        before = [hashlib.sha256(x.tobytes()).hexdigest() for x in masks]
        np.random.seed(91); state = np.random.get_state()
        a, meta = m.thin_masks(masks, [str(i) for i in range(12)], 2300000, m.MASK_SEED)
        self.assertTrue(all(np.array_equal(x, y) if hasattr(x, "shape") else x == y
                            for x, y in zip(state, np.random.get_state())))
        b, again = m.thin_masks(masks, [str(i) for i in range(12)], 2300000, m.MASK_SEED)
        self.assertEqual(meta, again)
        self.assertTrue(all(np.array_equal(x, y) for x, y in zip(a, b)))
        self.assertEqual(meta["available_valid_pixels_before"], 2303273)
        self.assertEqual(meta["removed_pixels"], 3273)
        self.assertEqual(sum(np.count_nonzero(x != 255) for x in a), 2300000)
        self.assertEqual(before, [hashlib.sha256(x.tobytes()).hexdigest() for x in masks])
        for original, output in zip(masks, a):
            self.assertTrue(np.all(output[original == 255] == 255))
            self.assertTrue(np.all((output == original) | ((original != 255) & (output == 255))))
            self.assertTrue(set(np.unique(output)) <= set(range(8)) | {255})
        self.assertTrue(all(sum(row["retained_class_counts"]) == row["retained_valid_pixels"] for row in meta["images"]))

    def test_sampling_uses_validity_not_classes_and_handles_views(self):
        mask = np.arange(80, dtype=np.uint8).reshape(8, 10) % 8
        mask[0, :3] = 255
        reverse = mask[:, ::-1]
        relabel = np.where(reverse == 255, 255, (reverse + 3) % 8).astype(np.uint8)
        a, x = m.thin_masks([reverse], ["a"], 40, 4)
        b, y = m.thin_masks([relabel], ["a"], 40, 4)
        self.assertTrue(np.array_equal(a[0] != 255, b[0] != 255))
        self.assertEqual(x["combined_keep_bitmap_sha256"], y["combined_keep_bitmap_sha256"])
        self.assertEqual(np.count_nonzero(a[0] != 255), 40)
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            m.thin_masks([mask], ["a"], 100, 1)
        with self.assertRaisesRegex(RuntimeError, "mapping"):
            m.thin_masks([np.array([[9]])], ["a"], 1, 1)

    def test_loader_is_training_only_restored_on_success_and_failure(self):
        import torch
        original_mask = torch.tensor([[0, 1, 255], [2, 3, 4]], dtype=torch.long)
        images = {k: (torch.zeros((3, 2, 3)), original_mask.clone()) for k in ("a", "b", "val", "panel")}
        records = [{"id": k, "rgb": {"sha256": "r"}, "label": {"sha256": "l"}} for k in ("a", "b")]
        snapshots = {k: y.clone() for k, (_, y) in images.items()}
        def original(record, base): return images[record["id"]]
        original_batch = lambda *a, **k: None
        seg = SimpleNamespace(load_pair=original, make_batch=original_batch)
        with tempfile.TemporaryDirectory(prefix="pixel-loader-") as directory:
            for fail in (False, True):
                try:
                    with m.training_masks(seg, records, directory, 6, 3) as (meta, calls):
                        self.assertEqual(sum(int((seg.load_pair(r, directory)[1] != 255).sum()) for r in records), 6)
                        self.assertEqual(calls, ["a", "b"])
                        with self.assertRaisesRegex(RuntimeError, "Training-only"):
                            seg.load_pair({"id": "panel"}, directory)
                        if fail: raise ValueError("synthetic fit failed")
                except ValueError:
                    self.assertTrue(fail)
                self.assertIs(seg.load_pair, original)
                self.assertIs(seg.make_batch, original_batch)
                self.assertTrue(torch.equal(seg.load_pair({"id": "val"}, directory)[1], snapshots["val"]))
                self.assertTrue(torch.equal(seg.load_pair({"id": "panel"}, directory)[1], snapshots["panel"]))
                self.assertTrue(all(torch.equal(images[k][1], y) for k, y in snapshots.items()))

    def test_backend_evaluates_only_after_restoration(self):
        import torch
        with tempfile.TemporaryDirectory(prefix="pixel-backend-") as directory:
            root = Path(directory); weight = root / "weight"; weight.write_bytes(b"synthetic")
            selected = [{"id": k, "rgb": {"sha256": "r"}, "label": {"sha256": "l"}} for k in ("a", "b")]
            mask = torch.tensor([[0, 1, 2], [3, 4, 255]], dtype=torch.long)
            def original(record, base): return torch.zeros((3, 2, 3)), mask.clone()
            original_batch = lambda *a, **k: None
            seg = SimpleNamespace(load_pair=original, make_batch=original_batch)
            def fit(records, base, **kwargs):
                self.assertEqual(sum(int((seg.load_pair(r, base)[1] != 255).sum()) for r in records), 6)
                return object(), {"synthetic": True}
            evaluated = []
            def evaluate(model, records, base, device):
                self.assertIs(seg.load_pair, original)
                self.assertIs(seg.make_batch, original_batch)
                self.assertTrue(torch.equal(seg.load_pair(records[0], base)[1], mask))
                evaluated.append(records[0]["id"])
                return {"synthetic": True}
            seg.fit, seg.evaluate = fit, evaluate
            backend = m.Backend.__new__(m.Backend)
            backend.weight, backend.weight_sha, backend.segmentation = weight, m.sha(weight), seg
            backend.torch = SimpleNamespace(cuda=SimpleNamespace(reset_peak_memory_stats=lambda: None,
                synchronize=lambda: None, max_memory_allocated=lambda: 0, max_memory_reserved=lambda: 0, empty_cache=lambda: None))
            spec = {"identity": {"selection_seed": 0, "initialization_seed": 0}, "selection": {"selected_ids": ["a", "b"]},
                    "encoder_lr": .0001, "steps": 1}
            with patch.object(m, "BUDGET", 6):
                payload = backend.execute(selected, [{"id": "val"}], [{"id": "panel"}], root, spec, lambda _: None)
            self.assertEqual(evaluated, ["panel", "val"])
            self.assertTrue(payload["evaluation_original_loader_restored"])
            self.assertIs(seg.load_pair, original)

    def test_batch_rgb_augmentations_and_rng_state_equal_frozen_sampler(self):
        import torch
        import v2_segmentation as frozen
        torch.set_num_threads(1)
        x = torch.arange(3*448*448).reshape(3,448,448).remainder(256).to(torch.uint8)
        full = torch.arange(448*448).reshape(448,448).remainder(8)
        thin = full.clone(); thin[::3, ::2] = 255
        snapshots = (x.clone(), full.clone(), thin.clone())
        for seed in (0,1,2,99):
            first, second = np.random.default_rng(seed), np.random.default_rng(seed)
            expected_x, expected_y = frozen.make_batch([(x,full)], first, 2,224)
            actual_x, actual_y = m.masked_batch([(x,thin)], second, {id(thin):full}, frozen.MEAN,frozen.STD,2,224)
            self.assertTrue(torch.equal(expected_x,actual_x))
            self.assertEqual(first.bit_generator.state,second.bit_generator.state)
            self.assertTrue(torch.equal(expected_y[actual_y!=255],actual_y[actual_y!=255]))
        self.assertTrue(all(torch.equal(a,b) for a,b in zip((x,full,thin),snapshots)))

    def test_original_sparse_eligibility_retries_then_thin_empty_fails_no_extra_draw(self):
        import torch
        import v2_segmentation as frozen
        class Rng:
            def __init__(self): self.calls=[];self.coordinates=iter(([100,100],[0,0]))
            def integers(self,*args,**kwargs):
                self.calls.append(('integers',args,kwargs))
                return np.array(next(self.coordinates)) if kwargs.get('size')==2 else 0
            def random(self): self.calls.append(('random',));return .75
        full=torch.full((448,448),255,dtype=torch.long);full[0,0]=0;full[400,400]=1
        thin=full.clone();thin[0,0]=255
        x=torch.zeros((3,448,448),dtype=torch.uint8)
        a,b=Rng(),Rng()
        frozen.make_batch([(x,full)],a,1,224)
        with self.assertRaisesRegex(ValueError,'fail closed without resampling'):
            m.masked_batch([(x,thin)],b,{id(thin):full},frozen.MEAN,frozen.STD,1,224)
        self.assertEqual(a.calls,b.calls)

    def test_live_cuda_writer_unknown_child_and_missing90_refuse(self):
        with tempfile.TemporaryDirectory(prefix="pixel-admission-") as directory:
            root = Path(directory)
            path = m.safe(root, m.CUDA_OUT + "/writer.lock")
            m.bare_new(path, m.common.process_info())
            with self.assertRaisesRegex(RuntimeError, "still live"):
                m.require_cuda_terminal(root)
            path.unlink()
            child = m.safe(root, m.CUDA_OUT + "/parallel/g/worker_0.lease.json")
            m.bare_new(child, {"state": "reserved", "pid": None})
            with self.assertRaisesRegex(RuntimeError, "unknown"):
                m.require_cuda_terminal(root)
            child.unlink()
            m.bare_new(m.safe(root, m.SOURCE_PLAN), {"runs": []})
            with self.assertRaisesRegex(RuntimeError, "exact90"):
                m.require_cuda_terminal(root)

    def test_existing_result_missing_or_changed_log_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="pixel-resume-") as directory:
            root = Path(directory)
            identity = dict(source_split="source0", pool="skewed5_1", budget=12, selection_seed=0, initialization_seed=0, strategy="kcenter")
            spec = {"identity": identity, "selection": {"selected_ids": ["a"]}, "steps": 600, "encoder_lr": .0001}
            plan = {"runner_code_sha256": "code", "helper_code_sha256": {"helper": "sha"}}
            self.assertFalse(m.validate_existing(root, spec, plan, "plan"))
            dest = m.safe(root, m.OUT + "/" + m.run_key(identity) + "/result.json")
            log = dest.parent / "log.jsonl"
            value = {"status": "complete", "plan_sha256": "plan", "identity": identity, "selection": spec["selection"],
                **plan, "log_file": log.relative_to(root).as_posix(), "log_sha256": "missing"}
            m.bare_new(dest, value); digest = m.sha(dest)
            with self.assertRaises(FileNotFoundError): m.validate_existing(root, spec, plan, "plan")
            self.assertEqual(m.sha(dest), digest)
            log.write_bytes(b"synthetic log\n")
            masking={"available_valid_pixels_after":m.BUDGET,"seed":m.MASK_SEED,"ordered_selected_ids":["a"],
                     "images":[{"retained_valid_pixels":m.BUDGET}]}
            value.update(log_sha256=m.sha(log),pixel_supervision=masking,
                pixel_supervision_sha256=hashlib.sha256(m.raw(masking)).hexdigest(),
                training={"steps":600,"encoder_lr":.0001,"seed":0,"identity":{"selected_ids":["a"]},"all_final_parameters_finite":True})
            dest.write_bytes(m.raw(value))
            self.assertTrue(m.validate_existing(root,spec,plan,"plan"))
            log.write_bytes(b"changed")
            changed_digest=m.sha(dest)
            with self.assertRaisesRegex(RuntimeError,"log missing/changed"):m.validate_existing(root,spec,plan,"plan")
            self.assertEqual(m.sha(dest),changed_digest)
            with self.assertRaises(FileExistsError): m.bare_new(dest, {"overwrite": True})
            self.assertEqual(m.sha(dest), changed_digest)

    def test_source_files_selection_immutable_and_rare_class_loss_recorded(self):
        with tempfile.TemporaryDirectory(prefix="pixel-source-") as directory:
            root = Path(directory); source = root / "original.npy"
            np.save(source, np.array([[7, 0, 0, 0]], dtype=np.uint8))
            digest = m.sha(source); ids = ["source__a"]
            selected = json.dumps(ids)
            for seed in range(100):
                outputs, metadata = m.thin_masks([np.load(source)], ids, 1, seed)
                if 7 in metadata["images"][0]["classes_removed_entirely"]: break
            else: self.fail("Synthetic rare class was never removed")
            self.assertEqual(m.sha(source), digest)
            self.assertEqual(json.dumps(ids), selected)
            self.assertFalse(metadata["class_conditioned_sampling"])

    def test_budget_refuses_cap_and_two_real_os_workers_share_storage(self):
        with tempfile.TemporaryDirectory(prefix="pixel-os-workers-") as directory:
            root = Path(directory); store = m.Storage(root, "synthetic")
            with patch.object(m.common, "logical_bytes", return_value=m.CAP-m.EXTERNAL_RESERVE-2*m.WORKER_RESERVE):
                with self.assertRaisesRegex(RuntimeError, "reserve refused"): store.charge(0, refresh=True)
            script = root / "worker.py"
            script.write_text('''from pathlib import Path
import sys,os,time
sys.path.insert(0,sys.argv[1])
import numpy as np
import v2_pixel_budget as m
root=Path(sys.argv[2]); worker=int(sys.argv[3]); s=m.Storage(root,"synthetic")
s.charge(0,refresh=True)
lease=s.base/("worker_"+str(worker)+".lease.json")
s.new(lease,{**m.common.process_info(),"state":"ready","worker":worker})
deadline=time.monotonic()+10
while len(list(s.base.glob("worker_*.lease.json")))<2:
 if time.monotonic()>deadline: raise RuntimeError("missing second OS worker")
 time.sleep(.02)
a,meta=m.thin_masks([np.zeros((20,20),dtype=np.uint8)],["a"],300,worker)
s.new(s.base/("result_"+str(worker)+".json"),{"pid":os.getpid(),"retained":meta["available_valid_pixels_after"]})
''', encoding="utf-8")
            processes = [subprocess.Popen([sys.executable, "-B", str(script), str(Path(m.__file__).parent), str(root), str(i)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) for i in range(2)]
            for process in processes:
                output, error = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, (output, error))
            results = [m.read(store.base / f"result_{i}.json") for i in range(2)]
            self.assertEqual(len({r["pid"] for r in results}), 2)
            self.assertTrue(all(r["retained"] == 300 for r in results))
            state = m.read(store.state)
            self.assertGreater(state["accounted_bytes"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
