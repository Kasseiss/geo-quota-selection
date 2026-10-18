"""Independently reload the predetermined spatial checkpoint and compare all CMs."""
from datetime import datetime, timezone
import hashlib
import json

import torch
from v2_run import ROOT, load_locked
from v2_segmentation import ResNet18UNet, evaluate, sha, state_sha, seed_all
from v2_calibrate import write


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    freeze,design,manifest,index,development,panel=load_locked()
    path=ROOT/'evidence/v2/runs/resnet18_unet/source0_skewed5_1_b12_s0_i0_region_kcenter/result.json'
    result=json.loads(path.read_text())
    assert result['status']=='complete' and result['identity']['freeze_sha256']==sha(ROOT/'configs/v2_freeze.json')
    checkpoint=result['checkpoint'];assert sha(ROOT/checkpoint['path'])==checkpoint['sha256']
    spec=design['full_model'];torch.set_num_threads(spec['threads'])
    seed_all(0)
    saved=torch.load(ROOT/checkpoint['path'],map_location='cpu',weights_only=True)
    assert saved and all(torch.isfinite(value).all() for value in saved.values())
    model=ResNet18UNet(pretrained=False);model.load_state_dict(saved,strict=True)
    assert state_sha(model)==checkpoint['state_sha256']==result['training']['final_model_state_sha256']
    fresh=evaluate(model,panel,ROOT/'v2/data','cpu')
    old={entry['id']:entry for entry in result['test']['images']}
    new={entry['id']:entry for entry in fresh['images']}
    assert set(old)==set(new) and len(old)==72
    for identifier in sorted(old):
        assert old[identifier]==new[identifier], 'Reload CM mismatch: '+identifier
    assert fresh['aggregate']==result['test']['aggregate']
    report=dict(passed=True,created_utc=datetime.now(timezone.utc).isoformat(),
        scope='Predetermined source0/selection0/init0/real quota k-center complete spatial model',
        checkpoint_sha256=checkpoint['sha256'],model_state_sha256=state_sha(model),
        result_sha256=sha(path),manifest_sha256=sha(ROOT/'v2/data/manifest.json'),
        freeze_sha256=sha(ROOT/'configs/v2_freeze.json'),
        verifier_sha256=sha(ROOT/'code/v2_reload_checkpoint.py'),
        model_code_sha256=sha(ROOT/'code/v2_segmentation.py'),
        matched_images=len(old),matched_regions=len({entry['region'] for entry in new.values()}),
        expected_confusion_digest=digest(old),reloaded_confusion_digest=digest(new),
        all_integer_confusion_matrices_exact=True,aggregate_exact=True,
        checkpoint_predetermined_not_score_selected=True,refitting_performed=False,device='cpu')
    write(ROOT/'evidence/v2/checkpoint_reload.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
