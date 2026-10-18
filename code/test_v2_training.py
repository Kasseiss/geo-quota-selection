"""Small software checks on old development images; never new-panel evidence."""
from pathlib import Path
import json
import torch
from v2_segmentation import ROOT,fit,sha,software_check


def main():
    torch.set_num_threads(8)
    manifest=json.loads((ROOT/'v2/data/manifest.json').read_text())
    old=[r for r in manifest['pairs'] if r['role']=='old_development']
    assert len(old)>=3
    train=old[:2];validation=old[2:3]
    a,ha=fit(train,ROOT/'v2/data',seed=11,encoder_lr=.0001,steps=2)
    b,hb=fit(train,ROOT/'v2/data',seed=11,encoder_lr=.0001,steps=4,validation=validation,checkpoints=[2])
    assert ha['identity']['initial_model_state_sha256']==hb['identity']['initial_model_state_sha256']
    assert ha['final_model_state_sha256']==hb['validation'][0]['model_state_sha256']
    report={'passed':True,'same_training_prefix_state_exact':True,'standalone_steps':2,
            'long_run_steps':4,'checkpoint_step':2,'model_state_sha256':ha['final_model_state_sha256'],
            'development_record_ids':[r['id'] for r in train+validation],
            'new_panel_accessed':False,'model_code_sha256':sha(ROOT/'code/v2_segmentation.py'),
            'test_code_sha256':sha(Path(__file__)),'source':'Actual old development PNG pairs'}
    out=ROOT/'evidence/v2/software';out.mkdir(parents=True,exist_ok=True)
    (out/'training_prefix_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
