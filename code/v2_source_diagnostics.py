"""Post-selection source-class availability; never a selector input or target score.

This descriptive diagnostic covers every planned full-model condition, including
the two prospective weighted controls. It does not change the frozen experiment.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from core import candidate_pool
from v2_weighted_selection import select_images

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inputs=['configs/v2_design.json','configs/v2_extension.json','configs/v2_freeze.json',
            'cache/dinov2-formal120/index.json','evidence/v2/data_audit.json']
    design,extension,freeze,index,audit=[json.loads((ROOT/name).read_text()) for name in inputs]
    assert audit['passed'] and freeze['status']=='FROZEN_BEFORE_NEW_PANEL_EVALUATION'
    old_ids={r['id'] for r in index['records']}
    hist={r['id']:np.asarray(r['processed_mask_class_counts_raw_0_to_8'][1:],dtype=np.int64)
          for r in audit['processed_png_availability']['pairs'] if r['id'] in old_ids}
    assert set(hist)==old_ids and len(old_ids)==120
    names=index['classes']
    def summarize(ids):
        count=sum((hist[i] for i in ids),start=np.zeros(8,dtype=np.int64))
        return {'image_count':len(ids),'processed_class_pixel_counts':count.tolist(),
                'present_class_count':int(np.count_nonzero(count)),
                'absent_classes':[names[i] for i in np.flatnonzero(count==0)]}
    pools=[];selections=[]
    for split in design['source_splits']:
        all_ids=[r['id'] for r in index['records'] if r['region'] in split['train']]
        pools.append({'source_split':split['id'],'pool':'all60_development_source_images',**summarize(all_ids)})
        for profile in design['frozen_control']['pools']:
            pool=candidate_pool(index['records'],split['train'],profile,split['candidate_seed'])
            ids=[r['id'] for r in pool]
            pools.append({'source_split':split['id'],'pool':profile,**summarize(ids)})
        profile='skewed5_1';pool=candidate_pool(index['records'],split['train'],profile,split['candidate_seed'])
        ids=[r['id'] for r in pool];x=np.asarray([r['descriptor'] for r in pool]);regions=[r['region'] for r in pool]
        for seed in design['selection_seeds']:
            for strategy in design['strategies']+extension['additional_strategies']:
                selected=select_images(ids,x,regions,12,strategy,seed)
                selections.append({'source_split':split['id'],'pool':profile,'budget':12,'strategy':strategy,
                    'selection_seed':seed,'initialization_seed':extension['initialization_seed_by_selection_seed'][str(seed)],
                    'selected_ids':selected,**summarize(selected)})
    assert len(selections)==90 and len(pools)==9
    report={'created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Source-only descriptive class availability after locked selection; all90 planned full-model conditions, not a claim that all90 models have already completed.',
        'input_sha256':{name:sha(ROOT/name) for name in inputs},'code_sha256':sha(Path(__file__)),
        'classes':names,'source_pool_support':pools,'planned_full_model_selections':selections,
        'target_scores_or_target_mask_counts_used':False,'design_or_selection_modified':False,
        'limits':['Counts refer to complete448 processed source masks, not actual sampled training crops.',
                  'Source class availability is not fixed across source allocations or selected subsets.',
                  'Masks enter this descriptive diagnostic after selection; none is passed to the selector.',
                  'No class, image, region or fit is excluded and the primary metric remains unchanged.']}
    content=(json.dumps(report,indent=2)+'\n').encode()
    assert sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())+len(content)<2_000_000_000
    output=ROOT/'evidence/v2/source_class_support_diagnostic.json';output.write_bytes(content)
    print(json.dumps({'pool_support':pools,'planned_conditions':len(selections),'target_scores_used':False},indent=2))


if __name__=='__main__':main()
