"""Development-only calibration; no new-panel image is evaluated or opened."""
from pathlib import Path
import argparse
import gc
import json
import os
import time

import numpy as np
import torch
from core import candidate_pool
from v2_selection import select_images
from v2_segmentation import fit, sha, records_sha, runtime_identity

ROOT=Path(__file__).resolve().parents[1]


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(obj,indent=2),encoding='utf-8');temporary.replace(path)


def calibration(manifest_path,limit=None):
    if manifest_path.resolve()!=(ROOT/'v2/data/development_manifest.json').resolve():
        raise ValueError('Calibration requires the immutable development manifest')
    design=json.loads((ROOT/'configs/v2_design.json').read_text())
    manifest=json.loads(manifest_path.read_text())
    assert manifest['status']=='complete' and manifest['scope']=='immutable_development_120_only'
    old=set(design['old_development_regions'])
    records=[r for r in manifest['pairs'] if r['region'] in old]
    assert len(records)==120 and set(r['region'] for r in records)==old
    assert not old & set(design['new_test_regions'])
    index=json.loads((ROOT/'cache/dinov2-formal120/index.json').read_text())
    descriptors={r['id']:r['descriptor'] for r in index['records']}
    assert set(descriptors)=={r['id'] for r in records}
    by_id={r['id']:r for r in records}
    for record in index['records']:
        assert by_id[record['id']]['source_rgb']['sha256']==record['source_rgb_sha256']
        assert by_id[record['id']]['source_label']['sha256']==record['source_label_sha256']
    config=design['full_model'];torch.set_num_threads(config['threads'])
    device='cuda' if torch.cuda.is_available() else 'cpu'
    environment=runtime_identity(device)
    assert environment['pretrained_weight_sha256']=='f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec'
    code_hashes={name:sha(ROOT/'code'/name) for name in ['v2_segmentation.py','v2_selection.py','v2_calibrate.py','core.py']}
    report={'purpose':'Old24 development only; all new panel records excluded before fit/evaluate',
            'design_sha256':sha(ROOT/'configs/v2_design.json'),'development_manifest_sha256':sha(manifest_path),
            'execution_code_sha256':code_hashes,'device':device,'torch':torch.__version__,'splits':[]}
    report.update(development_records_sha256=records_sha(records),environment=environment)
    out=ROOT/'evidence/v2/calibration'
    for split in design['source_splits'][:limit]:
        pool=candidate_pool(records,split['train'],config['calibration_pool'],split['candidate_seed'])
        selected=select_images([r['id'] for r in pool],np.array([descriptors[r['id']] for r in pool]),
                               [r['region'] for r in pool],config['calibration_budget'],'random',config['calibration_selection_seed'])
        by_id={r['id']:r for r in records};train=[by_id[k] for k in selected]
        validation=[r for r in records if r['region'] in split['validation']]
        settings=[]
        for lr in config['calibration_encoder_lrs']:
            destination=out/split['id']/f'encoder_lr_{lr:g}.json'
            identity=dict(split=split['id'],encoder_lr=lr,selected_ids=selected,
                          validation_ids=sorted(r['id'] for r in validation),code_hashes=code_hashes,
                          design_sha256=report['design_sha256'],development_manifest_sha256=report['development_manifest_sha256'],
                          development_records_sha256=records_sha(records),environment=environment)
            if destination.exists():
                result=json.loads(destination.read_text());assert result['identity']==identity and result['status']=='complete'
                assert sha(ROOT/result['log_file'])==result['log_sha256']
            else:
                write(destination.with_suffix('.pending.json'),{'status':'running','identity':identity})
                log_path=destination.with_name(destination.stem+f'.attempt_{time.time_ns()}.jsonl')
                def log_entry(entry):
                    with log_path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(entry)+'\n')
                try:
                    model,history=fit(train,manifest_path.parent,seed=0,encoder_lr=lr,
                        steps=max(config['calibration_checkpoints']),device=device,
                        batch_size=config['batch_size'],crop=config['crop'],validation=validation,
                        checkpoints=config['calibration_checkpoints'],log_callback=log_entry)
                    result=dict(status='complete',identity=identity,history=history,log_file=log_path.relative_to(ROOT).as_posix(),log_sha256=sha(log_path))
                    write(destination,result);del model;gc.collect()
                except BaseException as e:
                    write(destination.with_suffix('.failure.json'),{'identity':identity,'error':repr(e),'time':time.time()});raise
            assert [r['step'] for r in result['history']['validation']]==config['calibration_checkpoints']
            for check in result['history']['validation']:
                settings.append({'encoder_lr':lr,'steps':check['step'],
                    'validation_union_miou':check['validation']['aggregate']['equal_region_union_miou'],
                    'validation_truth_present_miou':check['validation']['aggregate']['equal_region_miou'],
                    'record':destination.relative_to(ROOT).as_posix()})
            print(json.dumps({'split':split['id'],'lr':lr,'settings':settings[-3:]}),flush=True)
        chosen=sorted(settings,key=lambda x:(-x['validation_union_miou'],x['steps'],x['encoder_lr']))[0]
        report['splits'].append({'source_split':split['id'],'settings':settings,'chosen':chosen})
        write(out/'calibration.json',report)
    report['complete']=len(report['splits'])==3;write(out/'calibration.json',report)
    print(json.dumps({'complete':report['complete'],'choices':{x['source_split']:x['chosen'] for x in report['splits']}},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--limit',type=int)
    a=p.parse_args();calibration(a.manifest.resolve(),a.limit)
