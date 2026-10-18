"""Independent pixel-budget audit; validate_bundle is standard-library only.

Scientific functions import NumPy/Pillow lazily, after exact27/terminal gates.
No Torch/CuPy import, fitting, original-file mutation or partial-score analysis.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid
import v2_cuda_parallel_v2 as common

ROOT=Path(__file__).resolve().parents[1]
PLAN="configs/v2_pixel_budget_plan.json"
PLAN_SHA="3e776a5517286d634eb29968ab3a7cafa3912e166f47d84137e8d16ef03d58e9"
PROTOCOL="docs/v2_pixel_budget_protocol.md"
RUNNER="code/v2_pixel_budget.py"
OUT="evidence/v2/pixel_budget_execution"
AUDIT="evidence/v2/pixel_budget_audit.json"
ANALYSIS="tables/v2_pixel_budget/descriptive_analysis.json"
CUDA_AUDIT="evidence/v2/cuda_execution_audit.json"
SOURCE_PLAN="configs/v2_cuda_execution_plan.json"
SOURCE_SHA="15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545"
BUDGET=2_300_000
SEED=2026101811
STRATEGIES={"kcenter","region_kcenter","permuted_region_kcenter"}
MAPS=("result_files","artifact_sha256","code_sha256","inputs","source_cuda_result_files","source_cuda_artifact_sha256")
safe,sha,read,require=common.safe,common.sha,common.read,common.require


def valid_sha(value):
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)


def terminal(root,output):
    base=safe(root,output)
    writer=base/"writer.lock"
    if writer.exists():
        value=read(writer)
        require(not common.same_live_process(value) and not any(common.same_live_process(p) for p in value.get("children",[])),
                "Live writer/child: "+output)
        raise RuntimeError("Unresolved stale/unknown writer lock: "+output)
    for name in ("fit.lock","parallel_fit.lock"):
        require(not list(base.glob("*/"+name)),"Unresolved fit claim: "+output)
    parallel=base/"parallel"
    if parallel.exists():
        for generation in parallel.iterdir():
            if not generation.is_dir():continue
            for path in generation.glob("worker_*.lease.json"):
                lease=read(path)
                require(lease.get("state")=="terminal" and lease.get("pid") and not common.same_live_process(lease),
                        "Live/unknown/nonterminal child: "+path.relative_to(root).as_posix())
            if any((generation/name).exists() for name in ("execution.json","scheduling_amendment.json")):
                closed=generation/"global_lease.closed.json"
                require(closed.exists(),"Unclosed generation")
                lease=read(closed)
                require(not common.same_live_process(lease) and not any(common.same_live_process(p) for p in lease.get("children",[])),
                        "Closed generation has a live PID identity")


def inventory(root,plan,output):
    expected={output+"/"+common.run_key(s["identity"])+"/result.json":s for s in plan["runs"]}
    actual={p.relative_to(root).as_posix() for p in safe(root,output).rglob("result.json")}
    return expected,actual


def verify_maps(root,maps):
    seen={}
    for mapping in maps:
        require(isinstance(mapping,dict) and bool(mapping),"Missing identity map")
        for name,digest in mapping.items():
            require(valid_sha(digest) and (name not in seen or seen[name]==digest),"Conflicting/invalid mapped SHA")
            if name not in seen:require(sha(safe(root,name))==digest,"Mapped file SHA changed: "+name)
            seen[name]=digest


def locked_plan(root,source_sha=None):
    source_sha=SOURCE_SHA if source_sha is None else source_sha
    require(sha(safe(root,PLAN))==PLAN_SHA,"Locked pixel plan SHA differs")
    plan=read(safe(root,PLAN));source=read(safe(root,SOURCE_PLAN))
    require(sha(safe(root,SOURCE_PLAN))==source_sha==plan["source_cuda_plan_sha256"] and plan["source_cuda_plan"]==SOURCE_PLAN,
            "Original CUDA plan differs")
    require(plan["format"]=="v2-pixel-budget-plan-1" and plan["status"]=="LOCKED_BEFORE_PIXEL_BUDGET_FITS_AFTER_PANEL_EXPOSURE" and
            plan["prior_target_exposure"] is True and plan["original_primary_unchanged"] is True and
            plan["new_independent_holdout"] is False and plan["public_preregistration"] is False,"Pixel plan must acknowledge prior exposure")
    require(plan["runner_code_sha256"]==sha(safe(root,RUNNER)) and plan["protocol_sha256"]==sha(safe(root,PROTOCOL)),
            "Pixel runner/protocol SHA differs")
    require(plan["helper_code_sha256"]=={"code/v2_cuda_parallel_v2.py":sha(safe(root,"code/v2_cuda_parallel_v2.py"))},"Helper SHA differs")
    expected=[s for s in source["runs"] if s["identity"]["strategy"] in STRATEGIES]
    require(plan["runs"]==expected and plan["expected_runs"]==len(expected)==27 and
            len({common.run_key(s["identity"]) for s in expected})==27,"Need exact ordered27 original specs")
    require(plan["runtime"]==source["runtime"] and plan["runtime"]["threads"]==2 and
            plan["new_panel_image_ids"]==source["new_panel_image_ids"],"Runtime/panel changed")
    require(plan["supervision"]=={"processed_grid":[448,448],"available_valid_pixel_budget":BUDGET,"mask_seed_base":SEED,
        "mask_order":"ordered_selected_ids_then_row_major_original_valid_positions","sampling":"uniform_remove_without_replacement",
        "original_void_remains_ignored":True},"Supervision intervention changed")
    require(plan["workers"]==2 and plan["external_growth_reserve_bytes"]==55_000_000 and
            plan["per_worker_output_reserve_bytes"]==4_000_000,"Pixel worker/reserve policy changed")
    freeze=read(safe(root,"configs/v2_freeze.json"))
    require(plan["original_freeze_sha256"]==source["original_freeze_sha256"]==sha(safe(root,"configs/v2_freeze.json")) and
            plan["original_frozen_file_sha256"]==source["original_frozen_file_sha256"]==freeze["file_sha256"] and
            len(freeze["file_sha256"])==53,"Original53 freeze changed")
    return plan,source


def source_bundle(root,source):
    value=read(safe(root,CUDA_AUDIT))
    require(value["format"]=="v2-cuda90-audit-1" and value["passed"] is True and
            value["expected_count"]==value["observed_count"]==value["validated_count"]==90 and
            not any(value.get(k) for k in ("errors","missing","extra","duplicates")),"CUDA90 source audit must pass")
    expected,actual=inventory(root,source,common.OUT)
    require(actual==set(expected)==set(value["result_files"]) and len(actual)==90,"CUDA90 baseline inventory differs")
    verify_maps(root,[value[k] for k in ("result_files","artifact_sha256","code_sha256","inputs")])
    return value


def reconstruct_masks(root,selected,seed):
    """Independent global-keep implementation, not runner thin_masks import."""
    import numpy as np
    from PIL import Image
    originals=[];positions=[]
    for p in selected:
        path=safe(root,"v2/data/"+p["label"]["relative_path"])
        require(sha(path)==p["label"]["sha256"] and sha(safe(root,"v2/data/"+p["rgb"]["relative_path"]))==p["rgb"]["sha256"],
                "Original selected processed file changed")
        with Image.open(path) as image:raw_mask=np.asarray(image).copy()
        require(raw_mask.shape==(448,448) and set(np.unique(raw_mask))<=set(range(9)),"Invalid original448 mask")
        truth=(raw_mask.astype(np.int16)-1).astype(np.uint8);truth[raw_mask==0]=255
        originals.append(truth);positions.append(np.nonzero(raw_mask.reshape(-1)!=0)[0])
    total=sum(len(p) for p in positions);require(total>=BUDGET,"Source supervision below locked2.3M")
    keep=np.ones(total,dtype=bool)
    remove=np.random.Generator(np.random.PCG64(seed)).choice(total,size=total-BUDGET,replace=False)
    keep[remove]=False
    offset=0;images=[];combined=hashlib.sha256()
    for record,truth,pos in zip(selected,originals,positions):
        output=truth.copy();local_keep=keep[offset:offset+len(pos)]
        output.reshape(-1)[pos[~local_keep]]=255
        retained=output!=255;packed=np.packbits(retained.reshape(-1),bitorder="little").tobytes();combined.update(packed)
        before=np.bincount(truth[truth!=255],minlength=8).tolist();after=np.bincount(output[retained],minlength=8).tolist()
        images.append({"id":record["id"],"shape":[448,448],"original_valid_pixels":len(pos),"retained_valid_pixels":int(retained.sum()),
            "removed_pixels":int(len(pos)-retained.sum()),"original_class_counts":before,"retained_class_counts":after,
            "classes_removed_entirely":[i for i in range(8) if before[i] and not after[i]],
            "keep_bitmap_sha256":hashlib.sha256(packed).hexdigest(),
            "training_mask_uint8_row_major_sha256":hashlib.sha256(output.tobytes(order="C")).hexdigest()})
        offset+=len(pos)
    return {"seed":seed,"images":images,"available_valid_pixels_before":total,"available_valid_pixels_after":BUDGET,
        "removed_pixels":total-BUDGET,"ordered_selected_ids":[p["id"] for p in selected],
        "combined_keep_bitmap_sha256":combined.hexdigest(),"source_processed_file_sha256":[{"id":p["id"],"rgb":p["rgb"]["sha256"],
        "label":p["label"]["sha256"]} for p in selected]}


def bind_history(root,plan,plan_sha,bind):
    """Closed, named evidence only; never silently sweep arbitrary extras."""
    specs={common.run_key(s["identity"]):(i,s) for i,s in enumerate(plan["runs"])};excluded=[]
    for path in safe(root,OUT).rglob("*"):
        if not path.is_file():continue
        name=path.relative_to(root).as_posix();safe(root,name)
        parts=path.relative_to(safe(root,OUT)).parts
        if (parts==("admission.guard",) or len(parts)==3 and parts[0]=="parallel" and parts[-1] in ("budget.guard","stop.guard")):
            require(path.read_bytes()==b"0","OS guard must be exact one-byte mutex marker")
            excluded.append({"path":name,"bytes":1,"reason":"kernel mutex marker; no scientific/history payload"});continue
        if len(parts)==2 and parts[0] in specs:
            index,spec=specs[parts[0]]
            if parts[1]=="result.json":continue
            require(re.fullmatch(r"(?:attempt_\d+|failure_\d+|claim_\d+\.closed)\.json|training_\d+\.jsonl",parts[1]),
                    "Unknown per-run history file: "+name)
            if path.suffix==".json":
                value=read(path);require(value["plan_sha256"]==plan_sha,"Historical plan SHA differs")
                if parts[1].startswith("claim_"):require(value["index"]==index and value["worker"]==index%2 and value.get("generation") and
                    value.get("pid") and not common.same_live_process(value),"Historical claim ownership/live identity differs")
                else:
                    require(value["identity"]==spec["identity"],"Historical identity differs")
                    if parts[1].startswith("attempt_"):require(value["runner_code_sha256"]==plan["runner_code_sha256"] and
                        value["worker"]==index%2 and isinstance(value["generation"],str),"Historical attempt ownership differs")
                    else:require(isinstance(value["error"],str),"Missing failure evidence")
            else:
                from v2_audit_runs import validate_log
                entries=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
                if entries:
                    # An interrupted log may be an exact prefix of recorded50-step points.
                    expected=sorted({1,spec["steps"],*range(50,spec["steps"]+1,50)})
                    require([x["step"] for x in entries]==expected[:len(entries)],"Historical raw log is not a sampled-step prefix")
                    validate_log(entries,entries[-1]["step"])
        elif len(parts)==3 and parts[0]=="parallel":
            generation,leaf=parts[1:]
            require(leaf in {"execution.json","global_lease.closed.json","supervisor_summary.json","start.json","stop.request.json","budget.json"} or
                    re.fullmatch(r"worker_[01]\.(?:lease\.json|summary\.json|stdout\.txt)",leaf),"Unknown generation history file: "+name)
            if leaf.endswith(".json"):
                value=read(path)
                if "plan_sha256" in value:require(value["plan_sha256"]==plan_sha,"Historical generation plan differs")
                if "generation" in value:require(value["generation"]==generation,"Historical generation name differs")
                if "runner_code_sha256" in value:require(value["runner_code_sha256"]==plan["runner_code_sha256"],"Historical runner differs")
                if leaf=="execution.json":require(value["plan_sha256"]==plan_sha and value["runner_code_sha256"]==plan["runner_code_sha256"] and
                    value["helper_code_sha256"]==plan["helper_code_sha256"] and value["partition"]=="plan_index_modulo_2" and value["workers"]==2 and
                    value["external_growth_reserve_bytes"]==55_000_000 and value["per_worker_output_reserve_bytes"]==4_000_000,
                    "Invalid historical execution schema")
                if leaf=="global_lease.closed.json":require(value["generation"]==generation and value["plan_sha256"]==plan_sha and
                    value["runner_code_sha256"]==plan["runner_code_sha256"] and value["workers"]==2 and isinstance(value["children"],list) and value.get("pid"),
                    "Invalid historical closed lease")
                if re.fullmatch(r"worker_[01]\.lease\.json",leaf):require(value["state"]=="terminal" and value["worker"]==int(leaf[7]) and
                    value["generation"]==generation and value["plan_sha256"]==plan_sha and value.get("pid"),"Invalid historical worker lease")
                if leaf=="supervisor_summary.json":require(value["status"] in ("complete","failed") and value["workers"]==2 and
                    value["generation"]==generation and value["plan_sha256"]==plan_sha and isinstance(value["children"],list),"Invalid supervisor history")
                if leaf=="start.json":require(value["generation"]==generation and isinstance(value["children"],list) and
                    {p["worker"] for p in value["children"]}=={0,1},"Invalid start barrier history")
                if leaf=="stop.request.json":require(isinstance(value.get("reason"),str) or type(value.get("worker")) is int and value["worker"] in (0,1),"Invalid stop history")
                if leaf=="budget.json":require(type(value["accounted_bytes"]) is int and 0<value["accounted_bytes"]<common.CAP,"Invalid budget history")
                if re.fullmatch(r"worker_[01]\.summary\.json",leaf):
                    worker=int(leaf[7]);assigned=list(range(worker,27,2))
                    require(value.get("status") in ("complete","failed","cooperative_stop","failed_initialization"),"Unknown worker history state")
                    if value.get("status")=="failed_initialization":require(isinstance(value.get("error"),str),"Missing initialization failure evidence")
                    else:require(value["assigned_indices"]==assigned and len(set(value["executed_indices"]))==len(value["executed_indices"]) and
                        set(value["executed_indices"])<=set(assigned),"Invalid worker history partition")
            else:require("\x00" not in path.read_text(encoding="utf-8",errors="replace"),"Invalid raw stdout text")
        else:raise RuntimeError("Unrecognized pixel execution file: "+name)
        bind(name,"artifact_sha256")
    return excluded


def audit_pixel(root=ROOT,*,source_sha=SOURCE_SHA):
    root=Path(root).resolve();loaded=[];full=[]
    report={"format":"v2-pixel-budget-audit-1","passed":False,"created_utc":datetime.now(timezone.utc).isoformat(),
        "expected_count":27,"observed_count":0,"validated_count":0,"result_files":{},"artifact_sha256":{},"code_sha256":{},"inputs":{},
        "source_cuda_result_files":{},"source_cuda_artifact_sha256":{},"errors":[],"missing":[],"extra":[],"duplicates":[],
        "score_fields_opened":False,"original_primary_unchanged":True,"new_independent_holdout":False,
        "state_and_log_limits":"Declared finite/state hash and step1/every50/final logs; no independent unsaved state or unlogged-step verification."}
    def bind(name,category="inputs",expected=None):
        path=safe(root,name);digest=sha(path);require(expected is None or digest==expected,"SHA differs: "+name)
        require(name not in report[category] or report[category][name]==digest,"Conflicting binding")
        report[category][name]=digest;return path
    try:
        plan,source=locked_plan(root,source_sha);plan_sha=sha(safe(root,PLAN))
        terminal(root,OUT);terminal(root,common.OUT)
        expected,actual=inventory(root,plan,OUT)
        report.update(observed_count=len(actual),missing=sorted(set(expected)-actual),extra=sorted(actual-set(expected)))
        require(len(actual)==27 and actual==set(expected),"Incomplete/extra pixel inventory; scores not opened")
        baseline=source_bundle(root,source)
        report["source_cuda_result_files"]=baseline["result_files"];report["source_cuda_artifact_sha256"]=baseline["artifact_sha256"]
        report["inputs"].update(baseline["inputs"]);report["code_sha256"].update(baseline["code_sha256"])
        for name,digest in plan["original_frozen_file_sha256"].items():bind(name,expected=digest)
        for name in (PLAN,PROTOCOL,SOURCE_PLAN,CUDA_AUDIT,"evidence/v2/pixel_budget_rationale.json"):bind(name)
        for name in (RUNNER,"code/v2_audit_pixel_budget.py","code/test_v2_audit_pixel_budget.py","code/v2_audit_cuda.py","code/v2_cuda_parallel_v2.py"):bind(name,"code_sha256")
        for name in ("docs/v2_pixel_budget_audit.md","evidence/v2/software/pixel_budget_audit_validation.json"):bind(name)
        require(read(safe(root,"evidence/v2/software/pixel_budget_audit_validation.json"))["passed"] is True,"Pixel auditor software proof must pass")
        require(report["code_sha256"]["code/v2_audit_pixel_budget.py"]==sha(Path(__file__)),"Execute target-root auditor")
        for field in ("supplemental_input_sha256",):
            mapping=plan.get(field,{})
            require(isinstance(mapping,dict) and bool(mapping),"Missing supplemental input freeze")
            for name,digest in mapping.items():bind(name,expected=digest)
        # Scientific imports occur only after the exact27/terminal gates.
        import numpy as np
        import v2_audit_cuda as cuda
        from v2_audit_runs import audited_processed_counts,assert_same,validate_evaluation,validate_log
        require(sha(Path(cuda.__file__))==report["code_sha256"]["code/v2_audit_cuda.py"],"Loaded CUDA pure helper changed")
        manifest=read(safe(root,"v2/data/manifest.json"));pairs={p["id"]:p for p in manifest["pairs"]}
        counts=audited_processed_counts(read(safe(root,"evidence/v2/data_audit.json")),pairs)
        require(len(pairs)==len(counts)==192,"Need verified original processed-mask margins")
        panel={i:pairs[i] for i in plan["new_panel_image_ids"]};require(len(panel)==72,"Need original72 panel IDs")
        design=read(safe(root,"configs/v2_design.json"));splits={s["id"]:s for s in design["source_splits"]}
        calibration=read(safe(root,"evidence/v2/calibration/calibration.json"));truth={};seen=set()
        source_paths={common.run_key(s["identity"]):p for p,s in inventory(root,source,common.OUT)[0].items()}
        pending=[]
        for index,spec in enumerate(plan["runs"]):
            name=OUT+"/"+common.run_key(spec["identity"])+"/result.json";result=read(bind(name,"result_files"))
            key=common.run_key(result["identity"])
            if key in seen:report["duplicates"].append(name)
            require(key not in seen,"Duplicate pixel identity");seen.add(key)
            require(result["format"]=="v2-pixel-budget-result-1" and result["status"]=="complete" and
                result["plan_sha256"]==plan_sha and result["runner_code_sha256"]==plan["runner_code_sha256"] and
                result["helper_code_sha256"]==plan["helper_code_sha256"] and result["protocol_sha256"]==plan["protocol_sha256"] and
                result["source_cuda_plan_sha256"]==source_sha and result["original_freeze_sha256"]==plan["original_freeze_sha256"] and
                result["original_frozen_file_sha256"]==plan["original_frozen_file_sha256"],"Pixel result provenance differs")
            selected=[pairs[i] for i in spec["selection"]["selected_ids"]];require(len(selected)==12,"Need original ordered12 selection")
            adapter={**result,"format":"v2-cuda-execution-result-1","plan_sha256":source_sha}
            with_source_constant=cuda.PLAN_SHA
            require(with_source_constant==source_sha,"CUDA pure helper source-plan binding differs")
            cuda.validate_training(adapter,spec,source,selected,calibration,plan["original_frozen_file_sha256"]["code/v2_segmentation.py"])
            metadata=result["pixel_supervision"]
            require(hashlib.sha256(common.raw(metadata)).hexdigest()==result["pixel_supervision_sha256"],"Supervision metadata SHA differs")
            expected_masks=reconstruct_masks(root,selected,SEED+spec["identity"]["selection_seed"])
            for field,value in expected_masks.items():assert_same(metadata[field],value,"Independent supervision."+field)
            require(metadata["generator"]=="numpy.default_rng/PCG64" and metadata["numpy"]==plan["runtime"]["numpy"] and
                metadata["sampling"]=="uniform_remove_without_replacement" and metadata["order"]==plan["supervision"]["mask_order"] and
                metadata["class_conditioned_sampling"] is False,"Mask randomization policy differs")
            require(result["evaluation_original_loader_restored"] is True and result["evaluation_original_batch_sampler_restored"] is True and
                result["crop_eligibility"]=="original_full_mask; identical optimization RNG draws; thin-empty crop fails without resampling",
                "Evaluation restoration/original crop rule declaration differs")
            log=bind(result["log_file"],"artifact_sha256",result["log_sha256"])
            require(log.parent==safe(root,name).parent and log.name.startswith("training_"),"Wrong raw log path")
            entries=[json.loads(x) for x in log.read_text().splitlines() if x.strip()];validate_log(entries,spec["steps"])
            assert_same(entries,result["training"]["log"],"Raw/history log")
            schedule=result["scheduling"];worker=schedule["worker"];generation=schedule["generation"]
            require(schedule["workers"]==2 and worker==index%2,"Wrong pixel modulo ownership")
            attempt=read(bind(log.with_name("attempt_"+log.stem[len("training_"):] +".json").relative_to(root).as_posix(),"artifact_sha256"))
            require(attempt["identity"]==spec["identity"] and attempt["plan_sha256"]==plan_sha and
                attempt["runner_code_sha256"]==plan["runner_code_sha256"] and attempt["generation"]==generation and attempt["worker"]==worker,
                "Attempt provenance differs")
            folder=OUT+"/parallel/"+generation
            execution=read(bind(folder+"/execution.json","artifact_sha256"));own=read(bind(folder+f"/worker_{worker}.lease.json","artifact_sha256"))
            closed=read(bind(folder+"/global_lease.closed.json","artifact_sha256"))
            require(execution["plan_sha256"]==plan_sha and execution["runner_code_sha256"]==plan["runner_code_sha256"] and
                execution["helper_code_sha256"]==plan["helper_code_sha256"] and execution["partition"]=="plan_index_modulo_2" and execution["workers"]==2,
                "Generation execution binding differs")
            require(own["state"]=="terminal" and own["generation"]==generation and own["worker"]==worker and own["pid"]==schedule["pid"] and
                own.get("creation_token")==schedule.get("creation_token") and closed["generation"]==generation and closed["plan_sha256"]==plan_sha and
                closed["runner_code_sha256"]==plan["runner_code_sha256"] and any(p.get("worker")==worker and p["pid"]==schedule["pid"] for p in closed["children"]),
                "Pixel child/closed lease authorization differs")
            source_split=splits[spec["identity"]["source_split"]]
            validation={i:p for i,p in pairs.items() if p["role"]=="old_development" and p["region"] in source_split["validation"]}
            require(len(validation)==20,"Need original20 source-validation images")
            reference=read(safe(root,source_paths[common.run_key(spec["identity"])]))
            require(reference["identity"]==spec["identity"] and reference["selection"]==spec["selection"],"Full-label paired identity/selection differs")
            pending.append((result,validation,reference));report["metadata_preflight_count"]=len(pending)
        # No test/validation CM field is accessed until every27 metadata record passes.
        report["score_fields_opened"]=True
        for result,validation,reference in pending:
            validate_evaluation(result["test"],panel,truth,counts);validate_evaluation(result["validation"],validation,truth,counts)
            loaded.append(result);full.append(reference);report["validated_count"]+=1
        report["excluded_history_mutex_files"]=bind_history(root,plan,plan_sha,bind)
        verify_maps(root,[report[k] for k in MAPS]);terminal(root,OUT);terminal(root,common.OUT)
        require(inventory(root,plan,OUT)[1]==actual,"Pixel inventory changed during audit")
        report.update(passed=True,reconstruction_numpy_version=np.__version__,retained_valid_pixels_per_fit=BUDGET,
            masked_evaluation_used=False,independently_reconstructed_masks=True,optimization_rng_and_crop_rule="Runner code/software proof and restoration declarations; no replay of unlogged crop draws.")
    except (OSError,RuntimeError,ValueError,KeyError,TypeError) as exc:report["errors"].append(type(exc).__name__+": "+str(exc))
    return report,(loaded,full) if report["passed"] else ([],[])


def describe(thinned,full,design,audit,audit_sha):
    require(audit["passed"] and len(thinned)==len(full)==27,"Description requires passed27 audit")
    from v2_audit_runs import complete_aggregate
    from v2_statistics import average_regional,paired_region_summary
    groups=[]
    for results in (thinned,full):
        grouped=defaultdict(list)
        for r in results:grouped[r["identity"]["strategy"]].append({"identity":r["identity"],"regional":complete_aggregate(r["test"]["images"])["regions"]})
        require(set(grouped)==STRATEGIES and all(len(v)==9 for v in grouped.values()),"Wrong paired strategy support")
        groups.append(grouped)
    repetitions,seed=design["primary"]["repetitions"],design["primary"]["bootstrap_seed"]
    require((repetitions,seed)==(10000,2026101805),"Original bootstrap definition changed")
    rows=[]
    for left,right in (("region_kcenter","kcenter"),("region_kcenter","permuted_region_kcenter")):
        row={"a":left,"b":right,"role":"descriptive_post_exposure","thinned":{},"full_label_reference":{},"paired_change":{}}
        for source in (None,*sorted(s["id"] for s in design["source_splits"])):
            vectors=[]
            for grouped in groups:
                values=[]
                for strategy in (left,right):
                    fits=[f for f in grouped[strategy] if source is None or f["identity"]["source_split"]==source]
                    require(len(fits)==(9 if source is None else 3),"Paired source/seed support differs")
                    values.append(average_regional(fits,"union_class_miou"))
                require(set(values[0])==set(values[1])==set(design["new_test_regions"]) and len(values[0])==24,"Need fixed24 region support")
                vectors.append(values)
            label="overall24" if source is None else source
            for key,values in zip(("thinned","full_label_reference"),vectors):
                row[key][label]=paired_region_summary(*values,repetitions=repetitions,seed=seed)
            thin_delta={r:vectors[0][0][r]-vectors[0][1][r] for r in vectors[0][0]}
            full_delta={r:vectors[1][0][r]-vectors[1][1][r] for r in vectors[1][0]}
            row["paired_change"][label]=paired_region_summary(thin_delta,full_delta,repetitions=repetitions,seed=seed)
        rows.append(row)
    return {"format":"v2-pixel-budget-descriptive-1","scope":"DESCRIPTIVE_POST_EXPOSURE_PIXEL_BUDGET","created_utc":datetime.now(timezone.utc).isoformat(),
        "expected_count":27,"observed_count":27,"validated_count":27,"audit_sha256":audit_sha,**{k:audit[k] for k in MAPS},
        "original_primary_unchanged":True,"new_independent_holdout":False,"geographic_units":24,"contrasts":rows,
        "paired_change_definition":"Within the same region and matched source/seed identities, (thinned A-B)-(full-label CUDA90 A-B); bootstrap those regional paired changes, not CI signs.",
        "limits":"Post-exposure descriptive control of available unique processed labels; not native area, labeling time, realized crop visits or semantic information."}


def validate_bundle(root=ROOT):
    """Read-only stdlib integrity gate; no CM calculation, images or report writes."""
    root=Path(root).resolve();plan,source=locked_plan(root)
    terminal(root,OUT);terminal(root,common.OUT)
    audit=read(safe(root,AUDIT));analysis=read(safe(root,ANALYSIS))
    require(audit["format"]=="v2-pixel-budget-audit-1" and audit["passed"] is True and
        audit["expected_count"]==audit["observed_count"]==audit["validated_count"]==27 and
        not any(audit.get(k) for k in ("errors","missing","extra","duplicates")),"Pixel bundle lacks passed complete27 audit")
    require(analysis["format"]=="v2-pixel-budget-descriptive-1" and analysis["scope"]=="DESCRIPTIVE_POST_EXPOSURE_PIXEL_BUDGET" and
        analysis["expected_count"]==analysis["observed_count"]==analysis["validated_count"]==27 and
        analysis["audit_sha256"]==sha(safe(root,AUDIT)),"Stale/wrong pixel analysis binding")
    for value in (audit,analysis):require(value["original_primary_unchanged"] is True and value["new_independent_holdout"] is False,"Wrong inference scope")
    expected,actual=inventory(root,plan,OUT)
    require(actual==set(expected)==set(audit["result_files"]) and len(actual)==27,"Pixel result inventory differs")
    for key in MAPS:require(analysis[key]==audit[key],"Analysis map differs: "+key)
    actual_files={p.relative_to(root).as_posix() for p in safe(root,OUT).rglob("*") if p.is_file()}
    exclusions=audit.get("excluded_history_mutex_files",[]);excluded=set()
    for entry in exclusions:
        name=entry["path"];path=safe(root,name)
        require(name==OUT+"/admission.guard" or re.fullmatch(re.escape(OUT)+r"/parallel/[^/]+/(?:budget|stop)\.guard",name),"Invalid history exclusion")
        require(name not in excluded and entry["bytes"]==1 and path.read_bytes()==b"0","Invalid/mutated guard exclusion")
        excluded.add(name)
    require(all(name.startswith(OUT+"/") for name in audit["artifact_sha256"]) and
        actual_files-excluded==set(audit["result_files"])|set(audit["artifact_sha256"]),"Unbound/missing/unexpected pixel history")
    for name in actual_files:safe(root,name)
    verify_maps(root,[audit[k] for k in MAPS])
    require(audit["inputs"].get(PLAN)==sha(safe(root,PLAN)) and audit["inputs"].get(PROTOCOL)==plan["protocol_sha256"] and
        audit["code_sha256"].get(RUNNER)==plan["runner_code_sha256"] and audit["code_sha256"].get("code/v2_audit_pixel_budget.py")==sha(Path(__file__)),
        "Bundle lacks current plan/protocol/runner/auditor binding")
    require(all(audit["inputs"].get(p)==h for p,h in plan["supplemental_input_sha256"].items()),"Bundle lacks supplemental input bindings")
    require(len(analysis["contrasts"])==2 and {(r["a"],r["b"]) for r in analysis["contrasts"]}==
        {("region_kcenter","kcenter"),("region_kcenter","permuted_region_kcenter")},"Wrong descriptive contrast inventory")
    baseline=source_bundle(root,source)
    require(audit["source_cuda_result_files"]==baseline["result_files"] and audit["source_cuda_artifact_sha256"]==baseline["artifact_sha256"] and
        audit["inputs"][CUDA_AUDIT]==sha(safe(root,CUDA_AUDIT)),"Full-label reference audit/maps changed")
    terminal(root,OUT);terminal(root,common.OUT)
    union={}
    for key in MAPS:union.update(audit[key])
    union[AUDIT]=sha(safe(root,AUDIT));union[ANALYSIS]=sha(safe(root,ANALYSIS))
    return {"passed":True,"validated_count":27,"audit_sha256":union[AUDIT],"analysis_sha256":union[ANALYSIS],
        "result_files":audit["result_files"],"file_sha256":union,"excluded_history_mutex_files":audit.get("excluded_history_mutex_files",[]),
        "read_only":True,"scientific_analysis_recomputed":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--validate-bundle",action="store_true");parser.add_argument("--audit-only",action="store_true");parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args(argv)
    if args.self_test:
        import unittest,test_v2_audit_pixel_budget
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_v2_audit_pixel_budget)).wasSuccessful() else 1
    try:
        if args.validate_bundle:print(json.dumps(validate_bundle(args.root)));return 0
        report,(thin,full)=audit_pixel(args.root)
        import v2_audit_cuda as cuda
        cuda.write_report(args.root,AUDIT,report)
        if not report["passed"]:print(json.dumps({"passed":False,"errors":report["errors"]}));return 1
        if not args.audit_only:cuda.write_report(args.root,ANALYSIS,describe(thin,full,read(safe(args.root,"configs/v2_design.json")),report,sha(safe(args.root,AUDIT))))
        print(json.dumps({"passed":True,"validated_count":27}));return 0
    except (OSError,RuntimeError,ValueError,KeyError,TypeError) as exc:print("PIXEL AUDIT REFUSED: "+str(exc));return 1


if __name__=="__main__":raise SystemExit(main())
