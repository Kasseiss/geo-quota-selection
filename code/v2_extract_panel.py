"""Cache only frozen features for the fixed new evaluation panel; no selection."""
from pathlib import Path
import argparse
import json
import os
import time

import numpy as np
from PIL import Image
import torch
from torch.nn import functional as F
from v2_segmentation import sha

ROOT=Path(__file__).resolve().parents[1]


def main(manifest_path):
    design=json.loads((ROOT/'configs/v2_design.json').read_text())
    manifest=json.loads(manifest_path.read_text())
    records=[r for r in manifest['pairs'] if r['region'] in design['new_test_regions']]
    assert len(records)==72 and len({r['id'] for r in records})==72
    assert set(r['region'] for r in records)==set(design['new_test_regions'])
    torch.set_num_threads(4);torch.hub.set_dir(str(ROOT/'runtime/torchhub'))
    commit='7764ea0f912e53c92e82eb78a2a1631e92725fc8'
    net=torch.hub.load(f'facebookresearch/dinov2:{commit}','dinov2_vits14',pretrained=True,
                       trust_repo=True,skip_validation=True).cpu().eval()
    for p in net.parameters():p.requires_grad_(False)
    weights=ROOT/'runtime/torchhub/checkpoints/dinov2_vits14_pretrain.pth'
    assert sha(weights)=='b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9'
    identity={'extractor_sha256':sha(Path(__file__)),'manifest_sha256':sha(manifest_path),
              'weight_sha256':sha(weights),'commit':commit,'input':448,'torch':torch.__version__,
              'normalization':'ImageNet; channelL2; float16cache','device':'cpu'}
    out=ROOT/'v2/cache/new_panel_dinov2';out.mkdir(parents=True,exist_ok=True)
    index={'status':'extracting','identity':identity,'records':[]}
    mean=torch.tensor([.485,.456,.406])[None,:,None,None]
    std=torch.tensor([.229,.224,.225])[None,:,None,None]
    start=time.monotonic()
    for i,record in enumerate(records):
        path=manifest_path.parent/record['rgb']['relative_path'];assert sha(path)==record['rgb']['sha256']
        dest=out/(record['id']+'.npz')
        key=json.dumps(dict(identity=identity,rgb_sha256=record['rgb']['sha256']),sort_keys=True)
        if dest.exists():
            with np.load(dest) as z:assert str(z['identity'])==key
        else:
            if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())+1_000_000>=2_000_000_000:
                raise RuntimeError('2GB storage cap: stop before feature write')
            rgb=np.array(Image.open(path).convert('RGB'));assert rgb.shape==(448,448,3)
            x=torch.from_numpy(rgb.copy()).permute(2,0,1)[None].float()/255
            with torch.inference_mode():
                e=net.forward_features((x-mean)/std)
                feature=F.normalize(e['x_norm_patchtokens'].transpose(1,2).reshape(1,384,32,32),dim=1)
                dense=feature[0].permute(1,2,0).numpy().astype(np.float16)
            np.savez_compressed(dest,features=dense,identity=np.array(key))
        index['records'].append(dict(id=record['id'],region=record['region'],cache=dest.name,
                                    cache_sha256=sha(dest),processed_rgb_sha256=record['rgb']['sha256']))
        (out/'index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
        print(f'{i+1}/72 frozen panel features, elapsed {time.monotonic()-start:.1f}s',flush=True)
    index['status']='complete';(out/'index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();main(a.manifest.resolve())
