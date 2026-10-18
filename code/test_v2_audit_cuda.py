"""Synthetic complete90 CUDA evidence; no real model results, pixels or CUDA."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import v2_audit_cuda as a


def put(root, relative, value):
    path = root/relative; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(a.scheduler.raw(value)); return path


def fixture(root):
    old = ["old"+str(i) for i in range(24)]; new = ["panel"+str(i) for i in range(24)]
    splits=[]
    for j in range(3):
        order=old[8*j:]+old[:8*j]
        splits.append({"id":"source"+str(j),"train":order[:12],"validation":order[12:16],"unused_development":order[16:]})
    strategies=["random","kcenter","region_random","region_kcenter","permuted_region_kcenter","kmeanspp","facility_location","fd_roundrobin"]
    design={"old_development_regions":old,"new_test_regions":new,"source_splits":splits,"selection_seeds":[0,1,2],
        "strategies":strategies,"full_model":{"name":"resnet18_unet","budgets":[12],"pools":["skewed5_1"],"initialization_seeds":[0]},
        "frozen_control":{"name":"dinov2_mlp128","budgets":[6,12,24],"pools":["balanced3","skewed5_1"],"initialization_seeds":[0]},
        "primary":{"repetitions":10000,"bootstrap_seed":2026101805}}
    extension={"status":"PROSPECTIVE_SUPPLEMENT_BEFORE_NEW_PANEL_EVALUATION","additional_strategies":["region_weighted_facility_location","permuted_region_weighted_facility_location"],
        "pools":["skewed5_1"],"expected_additional_full_runs":18,"expected_additional_frozen_runs":54,"expected_additional_total_runs":72,
        "expected_total_runs":576,"randomization_amendment_before_new_panel_scores":True,"initialization_seed_by_selection_seed":{"0":0,"1":1,"2":2}}
    pairs=[]; audit_pairs=[]
    for role,regions,count in (("old_development",old,5),("new_panel",new,3)):
        for region in regions:
            for number in range(count):
                identifier=region+"__image"+str(number); p={"id":identifier,"region":region,"role":role}
                for kind,suffix in (("rgb",".png"),("label","_mask.png"),("metadata",".json")):
                    relative=role+"/"+region+"/image"+str(number)+suffix
                    path=root/'v2/data'/relative; path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"synthetic byte identity")
                    p[kind]={"relative_path":relative,"sha256":a.sha(path),"bytes":path.stat().st_size}
                pairs.append(p)
                audit_pairs.append({"id":identifier,"region":region,"usable":True,
                    "processed_mask_class_counts_raw_0_to_8":[0,448*448,0,0,0,0,0,0,0],
                    "label":{"sha256_verified":True,"relative_path":p['label']['relative_path']}})
    put(root,'v2/data/manifest.json',{"status":"complete","whole_v2_dataset_complete":True,"pairs":pairs})
    put(root,'configs/v2_design.json',design);put(root,'configs/v2_extension.json',extension)
    put(root,'evidence/v2/data_audit.json',{"passed":True,"processed_pngs_usable":True,"processed_png_availability":{"pairs":audit_pairs},
        "inputs":{"manifest":{"path":"v2/data/manifest.json","sha256":a.sha(root/'v2/data/manifest.json')}}})
    choices={s['id']:{"encoder_lr":.0001,"steps":1200 if s['id']=='source1' else 600} for s in splits}
    put(root,'evidence/v2/calibration/calibration.json',{"environment":{"pretrained_weight_sha256":"a"*64},
        "splits":[{"source_split":s,"chosen":v} for s,v in choices.items()]})
    code_dir=Path(a.__file__).parent
    for name in ('v2_audit_cuda.py','v2_audit_runs.py','v2_statistics.py','core.py','v2_cuda_parallel.py','v2_cuda_parallel_v2.py'):
        dest=root/'code'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(code_dir/name,dest)
    (root/'code/v2_cuda_execution.py').write_bytes(b'# synthetic scalar reference\n')
    (root/'code/v2_segmentation.py').write_bytes(b'# synthetic frozen model identity\n')
    frozen_names=['configs/v2_design.json','configs/v2_extension.json','v2/data/manifest.json','evidence/v2/data_audit.json',
        'evidence/v2/calibration/calibration.json',*a.HELPERS,'code/v2_segmentation.py']
    for i in range(53-len(frozen_names)):
        name=f'code/synthetic_frozen_{i}.py';(root/name).write_bytes(b'# synthetic\n');frozen_names.append(name)
    frozen={p:a.sha(root/p) for p in frozen_names}
    freeze=put(root,'configs/v2_freeze.json',{"file_sha256":frozen})
    preflight=put(root,'evidence/v2/software/cuda_preflight.json',{"synthetic":True})
    runtime={"torch":"synthetic","numpy":"synthetic","cuda_python":"synthetic","threads":2,"device":"synthetic GPU"}
    runs=[]
    matrix=a.expected_matrix(design,extension)
    for identity in matrix.values():
        if identity['model']!='resnet18_unet':continue
        source=next(s for s in splits if s['id']==identity['source_split'])
        selected=[p['id'] for p in pairs if p['role']=='old_development' and p['region'] in source['train']][:12]
        runs.append({"identity":identity,"selection":{"selected_ids":selected},**choices[source['id']]})
    plan={"expected_runs":90,"runs":runs,"runtime":runtime,"new_panel_image_ids":[p['id'] for p in pairs if p['role']=='new_panel'],
        "code_sha256":a.sha(root/a.scheduler.SCALAR),"original_freeze_sha256":a.sha(freeze),
        "original_frozen_file_sha256":frozen,"cuda_preflight_sha256":a.sha(preflight)}
    plan_path=put(root,a.PLAN,plan);plan_sha=a.sha(plan_path);by_id={p['id']:p for p in pairs}
    cm=[[0]*8 for _ in range(8)];cm[0][0]=448*448
    def evaluation(records):
        entries=[{"id":p['id'],"region":p['region'],"confusion":cm} for p in records]
        return {"images":entries,"aggregate":a.complete_aggregate(entries)}
    panel=[by_id[i] for i in plan['new_panel_image_ids']]
    for spec in runs:
        key=a.scheduler.run_key(spec['identity']);folder=a.OUT+'/'+key
        selected=[by_id[i] for i in spec['selection']['selected_ids']]
        source=next(s for s in splits if s['id']==spec['identity']['source_split'])
        val=[p for p in pairs if p['role']=='old_development' and p['region'] in source['validation']]
        steps=spec['steps']
        log=[{"step":i,"loss":1.0,"elapsed_seconds":float(i)/100} for i in sorted({1,steps,*range(50,steps+1,50)})]
        logpath=root/folder/'training_attempt_synthetic.jsonl';logpath.parent.mkdir(parents=True,exist_ok=True)
        logpath.write_text(''.join(json.dumps(x)+'\n' for x in log),encoding='utf-8')
        result={"format":"v2-cuda-execution-result-1","status":"complete","identity":spec['identity'],"selection":spec['selection'],
            "plan_sha256":plan_sha,"code_sha256":plan['code_sha256'],"deterministic_warn_only":True,
            "training":{"identity":{"torch":"synthetic","numpy":"synthetic","python":"synthetic","threads":2,"device_name":"synthetic GPU",
                "selected_ids":spec['selection']['selected_ids'],"selected_record_sha256":hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest(),
                "model_code_sha256":frozen['code/v2_segmentation.py'],"pretrained_weight_sha256":"a"*64,"initial_model_state_sha256":"b"*64},
                "final_model_state_sha256":"c"*64,"all_final_parameters_finite":True,"trainable_parameters":100,"encoder_lr":.0001,"decoder_lr":.001,
                "steps":steps,"seed":spec['identity']['initialization_seed'],"device":"cuda:0","batch_size":2,"crop":224,"validation":[],"log":log,"elapsed_seconds":steps/100+.1},
            "test":evaluation(panel),"validation":evaluation(val),"log_file":logpath.relative_to(root).as_posix(),"log_sha256":a.sha(logpath),
            "cuda_peak_allocated_bytes":1,"cuda_peak_reserved_bytes":2,"warnings":[],"total_seconds":steps/100+1}
        put(root,folder+'/result.json',result)
        put(root,folder+'/attempt_synthetic.json',{"status":"started","identity":spec['identity'],"plan_sha256":plan_sha,"device":"cuda:0"})
    return plan,plan_sha,design


class AuditChecks(unittest.TestCase):
    def test_complete90_and_fixed_descriptive_analysis_without_heavy_imports(self):
        with tempfile.TemporaryDirectory(prefix='cuda90-audit-') as directory:
            root=Path(directory);plan,digest,design=fixture(root)
            with patch.object(a,'PLAN_SHA',digest):report,results=a.audit_cuda(root,expected_plan_sha=digest)
            self.assertTrue(report['passed'],report['errors']);self.assertEqual(report['validated_count'],90)
            analysis=a.descriptive_analysis(results,design,report,'d'*64)
            self.assertEqual(len(analysis['contrasts']),4);self.assertFalse(analysis['new_independent_holdout'])
            self.assertEqual(analysis['result_files'],report['result_files'])
            self.assertEqual(analysis['contrasts'][0]['overall24']['difference'],0)
            self.assertNotIn('torch',sys.modules);self.assertNotIn('cupy',sys.modules)

    def test_missing_extra_and_live_gate_never_open_partial_scores(self):
        with tempfile.TemporaryDirectory(prefix='cuda90-gates-') as directory:
            root=Path(directory);plan,digest,_=fixture(root)
            first=root/a.OUT/a.scheduler.run_key(plan['runs'][0]['identity'])/'result.json';original=first.read_bytes();first.unlink()
            with patch.object(a,'PLAN_SHA',digest):report,_=a.audit_cuda(root,expected_plan_sha=digest)
            self.assertFalse(report['passed']);self.assertFalse(report['score_fields_opened']);self.assertEqual(len(report['missing']),1)
            first.write_bytes(original);duplicate=root/a.OUT/'unexpected/result.json';duplicate.parent.mkdir();duplicate.write_bytes(original)
            with patch.object(a,'PLAN_SHA',digest):report,_=a.audit_cuda(root,expected_plan_sha=digest)
            self.assertFalse(report['passed']);self.assertFalse(report['score_fields_opened']);duplicate.unlink()
            put(root,a.OUT+'/writer.lock',{"pid":__import__('os').getpid(),"plan_sha256":digest})
            with patch.object(a,'PLAN_SHA',digest):report,_=a.audit_cuda(root,expected_plan_sha=digest)
            self.assertFalse(report['passed']);self.assertFalse(report['score_fields_opened']);self.assertIn('writer.lock',report['errors'][0])

    def test_corrupt_identity_log_cm_and_sampled_step_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='cuda90-corruption-') as directory:
            root=Path(directory);plan,digest,_=fixture(root)
            path=root/a.OUT/a.scheduler.run_key(plan['runs'][1]['identity'])/'result.json';original=path.read_bytes()
            for case in ('identity','log_sha','truth_margin','logged_step','nonfinite_loss'):
                result=json.loads(original)
                if case=='identity':result['identity']=plan['runs'][0]['identity']
                elif case=='log_sha':result['log_sha256']='0'*64
                elif case=='truth_margin':
                    entries=result['test']['images'];entries[0]['confusion'][0][0]-=1;entries[0]['confusion'][1][0]+=1
                    result['test']['aggregate']=a.complete_aggregate(entries)
                elif case=='logged_step':result['training']['log'].pop(2)
                else:result['training']['log'][0]['loss']=float('nan')
                path.write_text(json.dumps(result),encoding='utf-8')
                with patch.object(a,'PLAN_SHA',digest):report,loaded=a.audit_cuda(root,expected_plan_sha=digest)
                self.assertFalse(report['passed'],case);self.assertEqual(loaded,[])
                if case=='identity':
                    self.assertFalse(report['score_fields_opened'])
                    self.assertFalse(report['terminal_metadata_preflight_passed'])
                path.write_bytes(original)

    def test_late_nonterminal_corrupt_identity_and_selection_refuse_before_scores(self):
        with tempfile.TemporaryDirectory(prefix='cuda90-terminal-metadata-') as directory:
            root=Path(directory);plan,digest,_=fixture(root)
            last=root/a.OUT/a.scheduler.run_key(plan['runs'][-1]['identity'])/'result.json'
            original=last.read_bytes()
            for case in ('malformed_json','noncomplete','wrong_identity','wrong_selection','wrong_plan','wrong_format'):
                value=json.loads(original)
                if case=='malformed_json':last.write_bytes(b'{"status":"complete",')
                else:
                    if case=='noncomplete':value['status']='running'
                    elif case=='wrong_identity':value['identity']=plan['runs'][0]['identity']
                    elif case=='wrong_selection':value['selection']['selected_ids'].reverse()
                    elif case=='wrong_plan':value['plan_sha256']='0'*64
                    else:value['format']='unknown-result'
                    last.write_bytes(a.scheduler.raw(value))
                with self.subTest(case=case),patch.object(a,'PLAN_SHA',digest), \
                     patch.object(a,'validate_evaluation',side_effect=AssertionError('CM access before all90 terminal')) as scoring:
                    report,loaded=a.audit_cuda(root,expected_plan_sha=digest)
                    self.assertFalse(report['passed'])
                    self.assertFalse(report['score_fields_opened'])
                    self.assertFalse(report['terminal_metadata_preflight_passed'])
                    self.assertEqual(report['validated_count'],0)
                    self.assertEqual(loaded,[])
                    scoring.assert_not_called()
                last.write_bytes(original)

    def test_scalar_v1_v2_provenance_and_actual_executor_bindings(self):
        with tempfile.TemporaryDirectory(prefix='cuda90-provenance-') as directory:
            root=Path(directory);plan,digest,_=fixture(root)
            for index,executor in enumerate(a.EXECUTORS):
                generation='synthetic_v'+str(index+1);worker=index%2;pid=99999990+index
                folder=a.OUT+'/parallel/'+generation;checksum=a.sha(root/executor)
                amendment={"executor_code_sha256":checksum,"plan_sha256":digest,"scalar_reference_code_sha256":plan['code_sha256'],
                    "generation":generation,"workers":2,"primary_and_original_576_unchanged":True,
                    "source_selected_ids_lr_steps_batch_crop_seeds_unchanged":True,"cpu_threads_per_worker":2,
                    "deterministic_warn_only":True,"no_extra_checkpoint":True,"score_fields_used_for_scheduling":False,"runtime":plan['runtime']}
                amendment_path=put(root,folder+'/scheduling_amendment.json',amendment)
                put(root,folder+f'/worker_{worker}.lease.json',{"state":"terminal","generation":generation,"worker":worker,"workers":2,
                    "pid":pid,"creation_token":"dead-synthetic","assigned_indices":list(range(worker,90,2))})
                put(root,folder+'/global_lease.closed.json',{"pid":99999999,"generation":generation,"plan_sha256":digest,
                    "executor_sha256":checksum,"amendment_sha256":a.sha(amendment_path),
                    "children":[{"worker":worker,"pid":pid,"creation_token":"dead-synthetic"}]})
                path=root/a.OUT/a.scheduler.run_key(plan['runs'][index]['identity'])/'result.json';result=a.read(path)
                result.update(code_sha256=checksum,executor_code_sha256=checksum,scalar_reference_code_sha256=plan['code_sha256'],
                    scheduling={"generation":generation,"workers":2,"worker":worker,"plan_index":index,"pid":pid,
                        "partition_rule":"fixed_plan_index_modulo_workers","cpu_threads_per_worker":2,
                        "amendment_file":amendment_path.relative_to(root).as_posix(),"amendment_sha256":a.sha(amendment_path)})
                path.write_bytes(a.scheduler.raw(result))
                attempt=a.read(path.parent/'attempt_synthetic.json');attempt['scheduling']=result['scheduling']
                (path.parent/'attempt_synthetic.json').write_bytes(a.scheduler.raw(attempt))
            with patch.object(a,'PLAN_SHA',digest):report,_=a.audit_cuda(root,expected_plan_sha=digest)
            self.assertTrue(report['passed'],report['errors']);self.assertEqual(report['provenance_counts'],{'parallel_v1':1,'parallel_v2':1,'scalar':88})
            result['code_sha256']='0'*64;path.write_bytes(a.scheduler.raw(result))
            with patch.object(a,'PLAN_SHA',digest):report,_=a.audit_cuda(root,expected_plan_sha=digest)
            self.assertFalse(report['passed'])


if __name__=='__main__':unittest.main()
