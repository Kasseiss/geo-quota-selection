"""Execute the locked extension. Target scoring requires a completed freeze."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import gc
import itertools
import json
import time

import numpy as np
import torch
from torch.nn import functional as F
from core import candidate_pool, confusion, aggregate
from v2_weighted_selection import select_images
from v2_segmentation import fit, evaluate, load_pair, sha, state_sha, records_sha, runtime_identity
from v2_calibrate import write

ROOT=Path(__file__).resolve().parents[1]
REQUIRED_FREEZE_FILES={
    'configs/v2_design.json','configs/v2_extension.json','configs/v2_geographic_sensitivity.json',
    'evidence/v2/geographic_disposition.json','docs/v2_protocol.md','docs/v2_weighted_selection.md','v2/data/development_manifest.json',
    'v2/data/manifest.json','v2/data/selection_plan.json','evidence/v2/data_audit.json',
    'evidence/v2/calibration/calibration.json','cache/dinov2-formal120/index.json',
    'v2/cache/new_panel_dinov2/index.json',
    *['code/'+name for name in ['v2_run.py','v2_segmentation.py','v2_selection.py','v2_weighted_selection.py','v2_calibrate.py','v2_reload_checkpoint.py',
                                'v2_prepare_data.py','v2_extract_panel.py','v2_audit_data.py','data_access.py',
                                'geography_audit.py','core.py','gpu_head.py']]}


def bytes_used():return sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())


def source_records(index, split, pool):
    return candidate_pool(index['records'],split['train'],pool,split['candidate_seed'])


def load_locked():
    path=ROOT/'configs/v2_freeze.json';freeze=json.loads(path.read_text())
    assert freeze['status']=='FROZEN_BEFORE_NEW_PANEL_EVALUATION'
    assert REQUIRED_FREEZE_FILES<=set(freeze['file_sha256'])
    for relative,checksum in freeze['file_sha256'].items():
        if sha(ROOT/relative)!=checksum:raise RuntimeError('Frozen input changed: '+relative)
    design=json.loads((ROOT/'configs/v2_design.json').read_text())
    manifest=json.loads((ROOT/'v2/data/manifest.json').read_text())
    assert manifest['status']=='complete' and manifest['whole_v2_dataset_complete'] and len(manifest['pairs'])==192
    index=json.loads((ROOT/'cache/dinov2-formal120/index.json').read_text())
    panel=[r for r in manifest['pairs'] if r['region'] in design['new_test_regions']]
    development=[r for r in manifest['pairs'] if r['region'] in design['old_development_regions']]
    assert len(panel)==72 and len(development)==120
    assert not {r['region'] for r in panel}&{r['region'] for r in development}
    assert len({r['id'] for r in manifest['pairs']})==192
    by_id={r['id']:r for r in development}
    calibration=json.loads((ROOT/'evidence/v2/calibration/calibration.json').read_text())
    immutable=json.loads((ROOT/'v2/data/development_manifest.json').read_text())
    assert calibration['complete'] and len(calibration['splits'])==3
    assert {r['source_split'] for r in calibration['splits']}=={s['id'] for s in design['source_splits']}
    assert records_sha(development)==records_sha(immutable['pairs'])==calibration['development_records_sha256']
    assert calibration['development_manifest_sha256']==sha(ROOT/'v2/data/development_manifest.json')
    for name,checksum in calibration['execution_code_sha256'].items():assert sha(ROOT/'code'/name)==checksum
    for split in calibration['splits']:
        assert len(split['settings'])==6
        for setting in split['settings']:
            assert setting['record'] in freeze['file_sha256']
    for r in index['records']:
        assert by_id[r['id']]['source_rgb']['sha256']==r['source_rgb_sha256']
        assert by_id[r['id']]['source_label']['sha256']==r['source_label_sha256']
    return freeze,design,manifest,index,development,panel


def selected_info(index,split,profile,budget,strategy,seed):
    pool=source_records(index,split,profile)
    x=np.array([r['descriptor'] for r in pool],dtype=np.float64)
    ids=[r['id'] for r in pool];regions=[r['region'] for r in pool]
    start=time.monotonic();selected=select_images(ids,x,regions,budget,strategy,seed)
    seconds=time.monotonic()-start
    assert len(set(selected))==budget and set(selected)<=set(ids)
    lookup={r['id']:r for r in pool};chosen=[lookup[k] for k in selected]
    positions=[ids.index(k) for k in selected]
    xx=x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
    distances=np.maximum(0,1-xx@xx[positions].T).min(1)
    per_region={name:float(distances[np.array(regions)==name].mean()) for name in sorted(set(regions))}
    selected_counts={name:sum(r['region']==name for r in chosen) for name in sorted(set(regions))}
    info=dict(candidate_ids=ids,selected_ids=selected,selected_regions=sorted({r['region'] for r in chosen}),
              mean_candidate_cosine_distance=float(distances.mean()),maximum_candidate_cosine_distance=float(distances.max()),
              equal_region_mean_candidate_cosine_distance=float(np.mean(list(per_region.values()))),
              candidate_region_mean_cosine_distances=per_region,selected_region_counts=selected_counts,
              selected_valid_original_pixels=sum(r['original_valid_pixels'] for r in chosen),
              selected_original_class_counts=np.array([r['original_class_counts'] for r in chosen]).sum(0).tolist(),
              selection_seconds=seconds)
    return chosen,info


def complete_aggregate(entries):
    summary=aggregate(entries)
    summary['equal_region_union_miou']=float(np.mean([r['union_class_miou'] for r in summary['regions'].values()]))
    return {'images':entries,'aggregate':summary}


def run(mode,limit=None):
    freeze,design,manifest,index,development,panel=load_locked()
    code_identity={name:sha(ROOT/'code'/name) for name in ['v2_run.py','v2_segmentation.py','v2_selection.py','v2_weighted_selection.py','core.py','gpu_head.py']}
    model_name='resnet18_unet' if mode=='full' else 'dinov2_mlp128'
    spec=design['full_model' if mode=='full' else 'frozen_control']
    torch.set_num_threads(spec.get('threads',2));base=ROOT/'v2/data'
    by_id={r['id']:r for r in development}
    plan=list(itertools.product(design['source_splits'],spec['pools'],spec['budgets'],design['selection_seeds'],spec['initialization_seeds'],design['strategies']))
    extension=json.loads((ROOT/'configs/v2_extension.json').read_text())
    assert extension['primary_unchanged'] and extension['base_design_unchanged']
    extra=list(itertools.product(design['source_splits'],[p for p in spec['pools'] if p in extension['pools']],spec['budgets'],design['selection_seeds'],spec['initialization_seeds'],extension['additional_strategies']))
    assert len(plan)==(72 if mode=='full' else 432)
    assert len(extra)==(18 if mode=='full' else 54)
    plan+=extra
    assert extension['initialization_seed_by_selection_seed']=={'0':0,'1':1,'2':2}
    plan=[(split,profile,budget,selection_seed,
           extension['initialization_seed_by_selection_seed'][str(selection_seed)],strategy)
          for split,profile,budget,selection_seed,_base_init,strategy in plan]
    assert len(plan)==extension['expected_full_runs' if mode=='full' else 'expected_frozen_runs']
    out=ROOT/'evidence/v2/runs'/model_name;out.mkdir(parents=True,exist_ok=True)
    calibration=json.loads((ROOT/'evidence/v2/calibration/calibration.json').read_text())
    if mode=='full':assert runtime_identity('cuda' if torch.cuda.is_available() else 'cpu')==calibration['environment']
    choices={r['source_split']:r['chosen'] for r in calibration['splits']}
    features={};test_features={}
    if mode=='frozen':
        from gpu_head import MLP,cp,device_info
        for r in index['records']:
            path=ROOT/'cache/dinov2-formal120'/r['cache'];assert sha(path)==r['cache_sha256']
            with np.load(path) as z:features[r['id']]={k:z[k] for k in ['features','target','coverage']}
        target_index=json.loads((ROOT/'v2/cache/new_panel_dinov2/index.json').read_text())
        for r in target_index['records']:
            path=ROOT/'v2/cache/new_panel_dinov2'/r['cache'];assert sha(path)==r['cache_sha256']
            with np.load(path) as z:test_features[r['id']]=z['features']
        assert set(test_features)=={r['id'] for r in panel}
    completed=0;executed=0
    for split,profile,budget,selection_seed,init,strategy in plan:
        key=f"{split['id']}_{profile}_b{budget}_s{selection_seed}_i{init}_{strategy}"
        folder=out/key;destination=folder/'result.json'
        identity={'model':model_name,'source_split':split['id'],'pool':profile,'budget':budget,
                  'selection_seed':selection_seed,'initialization_seed':init,'strategy':strategy,
                  'freeze_sha256':sha(ROOT/'configs/v2_freeze.json'),'execution_code_sha256':code_identity}
        chosen,selection=selected_info(index,split,profile,budget,strategy,selection_seed)
        if destination.exists():
            existing=json.loads(destination.read_text());assert existing['identity']==identity and existing['status']=='complete'
            assert existing['selection']['selected_ids']==selection['selected_ids']
            test_ids=[r['id'] for r in existing['test']['images']]
            assert len(test_ids)==len(set(test_ids))==len(panel) and set(test_ids)=={r['id'] for r in panel}
            assert sha(ROOT/existing['log_file'])==existing['log_sha256']
            if existing['checkpoint'] is not None:
                c=existing['checkpoint'];assert sha(ROOT/c['path'])==c['sha256']
                saved=torch.load(ROOT/c['path'],weights_only=True,map_location='cpu')
                assert saved and all(torch.isfinite(v).all() for v in saved.values())
            completed+=1;continue
        if limit is not None and executed>=limit:break
        if bytes_used()+55_000_000>=2_000_000_000:raise RuntimeError('2GB cap: insufficient safe run/checkpoint reserve')
        folder.mkdir(exist_ok=True);write(folder/'pending.json',dict(status='running',identity=identity,selection=selection))
        log_path=folder/f'training_attempt_{time.time_ns()}.jsonl'
        def log_entry(entry):
            with log_path.open('a',encoding='utf-8') as f:f.write(json.dumps(entry)+'\n')
        started=time.monotonic();validation=[r for r in development if r['region'] in split['validation']]
        assert all(r['region'] in split['train'] for r in chosen)
        assert not set(split['train'])&set(split['validation'])
        assert all(r['region'] in design['new_test_regions'] for r in panel)
        try:
            if mode=='full':
                device='cuda' if torch.cuda.is_available() else 'cpu';recipe=choices[split['id']]
                model,training=fit([by_id[r['id']] for r in chosen],base,seed=init,
                    encoder_lr=recipe['encoder_lr'],steps=recipe['steps'],device=device,
                    batch_size=spec['batch_size'],crop=spec['crop'],log_callback=log_entry)
                # The fixed new panel is opened for scoring only after the
                # locked selection, training and recipe have been completed.
                test=evaluate(model,panel,base,device);val=evaluate(model,validation,base,device)
                checkpoint=None
                if (split['id'],selection_seed,init,strategy)==('source0',0,0,'region_kcenter'):
                    path=folder/'predetermined_checkpoint.pt'
                    torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},path)
                    checkpoint={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'state_sha256':state_sha(model)}
                del model;gc.collect()
            else:
                tx=[];ty=[]
                for r in chosen:
                    d=features[r['id']];keep=d['coverage'].ravel()>=.5
                    tx.append(d['features'].reshape(-1,384)[keep]);ty.append(d['target'].reshape(-1,8)[keep])
                x=cp.asarray(np.concatenate(tx).astype(np.float32));y=cp.asarray(np.concatenate(ty).astype(np.float32))
                model=MLP(384,seed=init);rng=np.random.default_rng(init+10000);logs=[]
                for step in range(1,spec['steps']+1):
                    batch=cp.asarray(rng.integers(0,len(x),4096));loss=model.step(x[batch],y[batch],spec['learning_rate'],.0001)
                    if not np.isfinite(loss):raise RuntimeError('Nonfinite GPU loss')
                    if step==1 or step%50==0:
                        entry={'step':step,'loss':loss,'elapsed_seconds':time.monotonic()-started};logs.append(entry);log_entry(entry)
                entries=[]
                if not all(bool(cp.isfinite(p).all().get()) for p in model.p):raise RuntimeError('Nonfinite frozen head state')
                for record in panel:
                    dense=test_features[record['id']];h,w,c=dense.shape
                    logits=cp.asnumpy(model.logits(cp.asarray(dense.reshape(-1,c).astype(np.float32))))
                    if not np.isfinite(logits).all():raise RuntimeError('Nonfinite frozen evaluation logits')
                    tensor=torch.from_numpy(logits.reshape(h,w,8).transpose(2,0,1).copy())[None]
                    pred=F.interpolate(tensor,size=(448,448),mode='bilinear',align_corners=False).argmax(1)[0].numpy()
                    _,truth=load_pair(record,base)
                    entries.append({'id':record['id'],'region':record['region'],'confusion':confusion(truth.numpy(),pred,ignore=255).tolist()})
                test=complete_aggregate(entries);val=None;checkpoint=None
                training=dict(log=logs,steps=spec['steps'],learning_rate=spec['learning_rate'],seed=init,
                              device=device_info(),parameter_count=sum(p.size for p in model.p),all_final_parameters_finite=True)
                del model,x,y;cp.get_default_memory_pool().free_all_blocks()
            result=dict(status='complete',identity=identity,selection=selection,training=training,
                        test=test,validation=val,checkpoint=checkpoint,log_file=log_path.relative_to(ROOT).as_posix(),
                        log_sha256=sha(log_path),total_seconds=time.monotonic()-started,created_utc=datetime.now(timezone.utc).isoformat())
            write(destination,result)
        except BaseException as e:
            write(folder/f'failure_{time.time_ns()}.json',dict(identity=identity,error=repr(e)));raise
        completed+=1;executed+=1
        write(out/'progress.json',dict(completed=completed,expected=len(plan),last_run=key))
        print(json.dumps(dict(completed=completed,expected=len(plan),run=key,seconds=result['total_seconds'],
                              new_panel_region_union_miou=test['aggregate']['equal_region_union_miou'])),flush=True)
    print(json.dumps(dict(model=model_name,completed=completed,planned=len(plan),newly_executed=executed)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['full','frozen']);p.add_argument('--limit',type=int)
    a=p.parse_args();run(a.mode,a.limit)
