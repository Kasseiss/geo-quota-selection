"""Reclaim a regenerable official weight download after panel extraction completes."""
from pathlib import Path
from datetime import datetime,timezone
import json
from v2_segmentation import sha

ROOT=Path(__file__).resolve().parents[1]


def main():
    index_path=ROOT/'v2/cache/new_panel_dinov2/index.json'
    index=json.loads(index_path.read_text())
    assert index['status']=='complete' and len(index['records'])==72
    for item in index['records']:
        assert sha(index_path.parent/item['cache'])==item['cache_sha256']
    relative='runtime/torchhub/checkpoints/dinov2_vits14_pretrain.pth'
    target=(ROOT/relative).resolve()
    assert target.is_relative_to(ROOT.resolve()) and target.name=='dinov2_vits14_pretrain.pth'
    receipt=ROOT/'evidence/v2/encoder_download_reclamation.json'
    if not target.exists():
        prior=json.loads(receipt.read_text());assert prior['removed'] and prior['relative_path']==relative
        print('Already reclaimed with receipt');return
    checksum=sha(target)
    assert checksum==index['identity']['weight_sha256']=='b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9'
    record=dict(created_utc=datetime.now(timezone.utc).isoformat(),relative_path=relative,
        bytes=target.stat().st_size,sha256=checksum,index_sha256=sha(index_path),
        reason='Bounded2GB storage: official regenerable encoder download no longer needed by any planned fit; source and new-panel feature arrays remain available.',
        official_download_url='https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth',
        original_data_removed=False,learned_research_checkpoint_removed=False,removed=False)
    receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    target.unlink()
    record['removed']=True
    receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
