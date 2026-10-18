"""Synthetic pixel-budget evidence; never run or read a scientific fit."""
from contextlib import ExitStack,contextmanager
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
import v2_audit_pixel_budget as a
import v2_audit_cuda as cuda
from test_v2_audit_cuda import fixture as full_fixture,put


@contextmanager
def constants(source_sha,pixel_sha):
    with ExitStack() as stack:
        stack.enter_context(patch.object(a,'SOURCE_SHA',source_sha));stack.enter_context(patch.object(a,'PLAN_SHA',pixel_sha))
        stack.enter_context(patch.object(cuda,'PLAN_SHA',source_sha));yield


def fixture(root):
    source,_,design=full_fixture(root)
    manifest=a.read(root/'v2/data/manifest.json');pairs={p['id']:p for p in manifest['pairs']}
    raw=(np.arange(448*448,dtype=np.uint32).reshape(448,448)%8+1).astype(np.uint8);raw[:2]=0
    histogram=np.bincount(raw.reshape(-1),minlength=9).tolist()
    for record in pairs.values():
        path=root/'v2/data'/record['label']['relative_path'];Image.fromarray(raw).save(path)
        record['label'].update(sha256=a.sha(path),bytes=path.stat().st_size)
    put(root,'v2/data/manifest.json',manifest)
    data=a.read(root/'evidence/v2/data_audit.json')
    data['inputs']['manifest']['sha256']=a.sha(root/'v2/data/manifest.json')
    for row in data['processed_png_availability']['pairs']:row['processed_mask_class_counts_raw_0_to_8']=histogram
    put(root,'evidence/v2/data_audit.json',data)
    freeze=a.read(root/'configs/v2_freeze.json')
    freeze['file_sha256']={p:a.sha(root/p) for p in freeze['file_sha256']};put(root,'configs/v2_freeze.json',freeze)
    source.update(original_frozen_file_sha256=freeze['file_sha256'],original_freeze_sha256=a.sha(root/'configs/v2_freeze.json'))
    source['runtime']['numpy']=np.__version__;put(root,a.SOURCE_PLAN,source);source_sha=a.sha(root/a.SOURCE_PLAN)
    full_results={};artifacts={};cm=np.diag(histogram[1:]).tolist()
    for spec in source['runs']:
        folder=root/cuda.OUT/a.common.run_key(spec['identity']);path=folder/'result.json';result=a.read(path)
        result['plan_sha256']=source_sha;result['training']['identity']['numpy']=np.__version__
        selected=[pairs[i] for i in spec['selection']['selected_ids']]
        result['training']['identity']['selected_record_sha256']=hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()
        for field in ('test','validation'):
            for entry in result[field]['images']:entry['confusion']=cm
            result[field]['aggregate']=cuda.complete_aggregate(result[field]['images'])
        path.write_bytes(a.common.raw(result));full_results[path.relative_to(root).as_posix()]=a.sha(path)
        attempt=folder/'attempt_synthetic.json';value=a.read(attempt);value['plan_sha256']=source_sha;attempt.write_bytes(a.common.raw(value))
        for p in (attempt,root/result['log_file']):artifacts[p.relative_to(root).as_posix()]=a.sha(p)
    codes={p:a.sha(root/p) for p in (cuda.scheduler.SCALAR,*cuda.EXECUTORS,*cuda.HELPERS,'code/v2_audit_cuda.py')}
    inputs={**freeze['file_sha256'],a.SOURCE_PLAN:source_sha,'configs/v2_freeze.json':a.sha(root/'configs/v2_freeze.json')}
    for record in pairs.values():
        for kind in ('rgb','label','metadata'):inputs['v2/data/'+record[kind]['relative_path']]=record[kind]['sha256']
    put(root,a.CUDA_AUDIT,{'format':'v2-cuda90-audit-1','passed':True,'expected_count':90,'observed_count':90,'validated_count':90,
        'result_files':full_results,'artifact_sha256':artifacts,'code_sha256':codes,'inputs':inputs,'errors':[],'missing':[],'extra':[],'duplicates':[]})
    origin=Path(a.__file__).parent
    for name in ('v2_audit_pixel_budget.py','test_v2_audit_pixel_budget.py','v2_pixel_budget.py'):
        shutil.copyfile(origin/name,root/'code'/name)
    for relative in (a.PROTOCOL,'docs/v2_pixel_budget_audit.md','evidence/v2/software/pixel_budget_audit_validation.json',
                     'evidence/v2/pixel_budget_rationale.json','evidence/v2/synthetic_supplement_proof.json'):
        put(root,relative,{'synthetic':True,'passed':True})
    runs=[s for s in source['runs'] if s['identity']['strategy'] in a.STRATEGIES]
    plan={'format':'v2-pixel-budget-plan-1','status':'LOCKED_BEFORE_PIXEL_BUDGET_FITS_AFTER_PANEL_EXPOSURE',
        'prior_target_exposure':True,'original_primary_unchanged':True,'new_independent_holdout':False,'public_preregistration':False,
        'expected_runs':27,'runs':runs,'runtime':source['runtime'],'new_panel_image_ids':source['new_panel_image_ids'],
        'runner_code_sha256':a.sha(root/a.RUNNER),'helper_code_sha256':{'code/v2_cuda_parallel_v2.py':a.sha(root/'code/v2_cuda_parallel_v2.py')},
        'protocol_sha256':a.sha(root/a.PROTOCOL),'source_cuda_plan':a.SOURCE_PLAN,'source_cuda_plan_sha256':source_sha,
        'original_freeze_sha256':source['original_freeze_sha256'],'original_frozen_file_sha256':source['original_frozen_file_sha256'],
        'workers':2,'external_growth_reserve_bytes':55_000_000,'per_worker_output_reserve_bytes':4_000_000,
        'supplemental_input_sha256':{'evidence/v2/synthetic_supplement_proof.json':a.sha(root/'evidence/v2/synthetic_supplement_proof.json')},
        'supervision':{'processed_grid':[448,448],'available_valid_pixel_budget':a.BUDGET,'mask_seed_base':a.SEED,
            'mask_order':'ordered_selected_ids_then_row_major_original_valid_positions','sampling':'uniform_remove_without_replacement','original_void_remains_ignored':True}}
    put(root,a.PLAN,plan);pixel_sha=a.sha(root/a.PLAN)
    generation='synthetic';folder=a.OUT+'/parallel/'+generation
    put(root,folder+'/execution.json',{'plan_sha256':pixel_sha,'runner_code_sha256':plan['runner_code_sha256'],
        'helper_code_sha256':plan['helper_code_sha256'],'partition':'plan_index_modulo_2','workers':2,
        'external_growth_reserve_bytes':55_000_000,'per_worker_output_reserve_bytes':4_000_000})
    children=[{'worker':w,'pid':99999990+w,'creation_token':'dead-synthetic'} for w in (0,1)]
    for w in (0,1):
        put(root,folder+f'/worker_{w}.lease.json',{'state':'terminal','generation':generation,'worker':w,'plan_sha256':pixel_sha,**children[w]})
        put(root,folder+f'/worker_{w}.summary.json',{'worker':w,'assigned_indices':list(range(w,27,2)),
            'executed_indices':list(range(w,27,2)),'skipped_existing':[],'status':'complete'})
        p=root/folder/f'worker_{w}.stdout.txt';p.write_text('synthetic operational stdout\n')
    put(root,folder+'/global_lease.closed.json',{'pid':99999999,'generation':generation,'workers':2,'plan_sha256':pixel_sha,
        'runner_code_sha256':plan['runner_code_sha256'],'children':children})
    put(root,folder+'/budget.json',{'accounted_bytes':1000000});(root/folder/'budget.guard').write_bytes(b'0')
    for index,spec in enumerate(runs):
        key=a.common.run_key(spec['identity']);base=root/a.OUT/key;base.mkdir(parents=True)
        result=copy.deepcopy(a.read(root/cuda.OUT/key/'result.json'))
        result.update(format='v2-pixel-budget-result-1',plan_sha256=pixel_sha,runner_code_sha256=plan['runner_code_sha256'],
            helper_code_sha256=plan['helper_code_sha256'],source_cuda_plan_sha256=source_sha,original_freeze_sha256=plan['original_freeze_sha256'],
            original_frozen_file_sha256=plan['original_frozen_file_sha256'],protocol_sha256=plan['protocol_sha256'])
        selected=[pairs[i] for i in spec['selection']['selected_ids']]
        # Generate fixture evidence with the separate runner implementation;
        # the auditor must independently reproduce its searchsorted mapping.
        from v2_pixel_budget import thin_masks
        original_truth=raw.astype(np.int64)-1;original_truth[raw==0]=255
        before=original_truth.copy()
        _,masking=thin_masks([original_truth.copy() for _ in selected],[p['id'] for p in selected],a.BUDGET,a.SEED+spec['identity']['selection_seed'])
        assert np.array_equal(original_truth,before)
        masking['source_processed_file_sha256']=[{'id':p['id'],'rgb':p['rgb']['sha256'],'label':p['label']['sha256']} for p in selected]
        result['pixel_supervision']=masking;result['pixel_supervision_sha256']=hashlib.sha256(a.common.raw(masking)).hexdigest()
        result.update(evaluation_original_loader_restored=True,evaluation_original_batch_sampler_restored=True,
            crop_eligibility='original_full_mask; identical optimization RNG draws; thin-empty crop fails without resampling',
            scheduling={'generation':generation,'workers':2,**children[index%2]})
        errors={'kcenter':2,'region_kcenter':0,'permuted_region_kcenter':1}[spec['identity']['strategy']]
        for entry in result['test']['images']:
            entry['confusion'][0][0]-=errors;entry['confusion'][0][1]+=errors
        result['test']['aggregate']=cuda.complete_aggregate(result['test']['images'])
        log=base/f'training_{index}.jsonl';shutil.copyfile(root/result['log_file'],log)
        result['log_file']=log.relative_to(root).as_posix();result['log_sha256']=a.sha(log)
        put(root,base.relative_to(root).as_posix()+f'/attempt_{index}.json',{'identity':spec['identity'],'plan_sha256':pixel_sha,
            'runner_code_sha256':plan['runner_code_sha256'],'generation':generation,'worker':index%2})
        (base/'result.json').write_bytes(a.common.raw(result))
    return source_sha,pixel_sha,plan,design,pairs


class PixelAuditChecks(unittest.TestCase):
    def test_named_history_requires_real_schema_not_arbitrary_json(self):
        for leaf in ('execution.json','global_lease.closed.json','worker_0.lease.json','supervisor_summary.json','start.json','budget.json'):
            with self.subTest(leaf=leaf),tempfile.TemporaryDirectory(prefix='pixel-history-') as directory:
                root=Path(directory);put(root,a.OUT+'/parallel/fake/'+leaf,{'arbitrary':True})
                plan={'runs':[],'runner_code_sha256':'a'*64}
                with self.assertRaises((RuntimeError,KeyError)):
                    a.bind_history(root,plan,'b'*64,lambda *args:None)

    def test_complete_masks_paired_change_bundle_and_stdlib_gate(self):
        with tempfile.TemporaryDirectory(prefix='pixel-audit-') as directory:
            root=Path(directory);source,pixel,plan,design,pairs=fixture(root)
            with constants(source,pixel):report,(thin,full)=a.audit_pixel(root,source_sha=source)
            self.assertTrue(report['passed'],report['errors']);self.assertEqual(report['validated_count'],27)
            self.assertEqual(report['retained_valid_pixels_per_fit'],2300000)
            put(root,a.AUDIT,report);analysis=a.describe(thin,full,design,report,a.sha(root/a.AUDIT));put(root,a.ANALYSIS,analysis)
            for row in analysis['contrasts']:
                self.assertGreater(row['paired_change']['overall24']['difference'],0)
                self.assertAlmostEqual(row['paired_change']['overall24']['difference'],row['thinned']['overall24']['difference'])
            with constants(source,pixel):bundle=a.validate_bundle(root)
            self.assertTrue(bundle['passed']);self.assertIn(a.AUDIT,bundle['file_sha256']);self.assertIn(a.RUNNER,bundle['file_sha256'])
            script="import sys;sys.path.insert(0,sys.argv[1]);import v2_audit_pixel_budget as a;a.SOURCE_SHA=sys.argv[3];a.PLAN_SHA=sys.argv[4];a.validate_bundle(sys.argv[2]);assert not any(x in sys.modules for x in ('numpy','PIL','torch','cupy'));print('stdlib-only bundle passed')"
            process=subprocess.run([sys.executable,'-B','-c',script,str(Path(a.__file__).parent),str(root),source,pixel],capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr);self.assertIn('stdlib-only',process.stdout)
            extra=root/a.OUT/'unknown_extra.txt';extra.write_bytes(b'must not silently package')
            with constants(source,pixel),self.assertRaisesRegex(RuntimeError,'unexpected pixel history'):a.validate_bundle(root)
            extra.unlink()
            analysis_path=root/a.ANALYSIS;saved=analysis_path.read_bytes();bad=json.loads(saved);bad['validated_count']=26;analysis_path.write_bytes(a.common.raw(bad))
            with constants(source,pixel),self.assertRaises(RuntimeError):a.validate_bundle(root)
            analysis_path.write_bytes(saved)
            self.assertNotIn('torch',sys.modules);self.assertNotIn('cupy',sys.modules)

    def test_late_metadata_missing_live_and_corruption_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix='pixel-audit-reject-') as directory:
            root=Path(directory);source,pixel,plan,_,_=fixture(root)
            paths=[root/a.OUT/a.common.run_key(s['identity'])/'result.json' for s in plan['runs']]
            last=paths[-1];original=last.read_bytes()
            for value in ('malformed','noncomplete','missing'):
                if value=='malformed':last.write_text('{bad')
                elif value=='noncomplete':d=json.loads(original);d['status']='started';last.write_bytes(a.common.raw(d))
                else:last.unlink()
                with constants(source,pixel):report,_=a.audit_pixel(root,source_sha=source)
                self.assertFalse(report['passed']);self.assertFalse(report['score_fields_opened']);last.write_bytes(original)
            first=paths[0];saved=first.read_bytes()
            for case in ('mask_sha','retained_count','evaluation_margin','log_sha','restoration'):
                d=json.loads(saved)
                if case=='mask_sha':d['pixel_supervision']['images'][0]['training_mask_uint8_row_major_sha256']='0'*64
                elif case=='retained_count':d['pixel_supervision']['available_valid_pixels_after']-=1
                elif case=='evaluation_margin':
                    d['validation']['images'][0]['confusion'][0][0]-=1;d['validation']['images'][0]['confusion'][1][0]+=1
                    d['validation']['aggregate']=cuda.complete_aggregate(d['validation']['images'])
                elif case=='log_sha':d['log_sha256']='0'*64
                else:d['evaluation_original_batch_sampler_restored']=False
                d['pixel_supervision_sha256']=hashlib.sha256(a.common.raw(d['pixel_supervision'])).hexdigest();first.write_bytes(a.common.raw(d))
                with constants(source,pixel):report,_=a.audit_pixel(root,source_sha=source)
                self.assertFalse(report['passed'],case);first.write_bytes(saved)
            put(root,a.OUT+'/writer.lock',{'pid':__import__('os').getpid()})
            with constants(source,pixel):report,_=a.audit_pixel(root,source_sha=source)
            self.assertFalse(report['score_fields_opened']);self.assertFalse(report['passed'])


if __name__=='__main__':unittest.main()
