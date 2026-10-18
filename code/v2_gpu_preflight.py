"""Source-only CUDA feasibility check; not a held-out experiment or refit."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import sys
import json
import time
import hashlib
import warnings
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import torch
from torch.nn import functional as F
from v2_segmentation import ResNet18UNet, seed_all, load_pair, make_batch, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = {'format': 'v2-cuda-preflight-1', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'purpose': 'Source-only full segmentation model optimization on existing discrete GPU; no held-out evidence',
              'passed': False, 'formal_experiment_modified': False, 'target_panel_opened': False,
              'torch': torch.__version__, 'numpy': np.__version__, 'python': sys.version,
              'cuda_build': torch.version.cuda, 'cuda_available': torch.cuda.is_available(),
              'source_code_sha256': sha(Path(__file__)),
              'model_code_sha256': sha(ROOT / 'code/v2_segmentation.py')}
    out = ROOT / 'evidence/v2/software/cuda_preflight.json'
    try:
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA GPU unavailable in this interpreter')
        if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) + 2_000_000 >= 2_000_000_000:
            raise RuntimeError('Whole-project storage reserve unavailable')
        torch.set_num_threads(2)
        report['device'] = torch.cuda.get_device_name(0)
        report['compute_capability'] = list(torch.cuda.get_device_capability(0))
        weights = Path(torch.hub.get_dir()) / 'checkpoints/resnet18-f37072fd.pth'
        if not weights.is_file() or sha(weights) != 'f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec':
            raise RuntimeError('Existing pretrained weight missing or changed; no automatic download')
        report['pretrained_weight_sha256'] = sha(weights)
        design = json.loads((ROOT / 'configs/v2_design.json').read_text(encoding='utf-8'))
        manifest = json.loads((ROOT / 'v2/data/development_manifest.json').read_text(encoding='utf-8'))
        records = manifest['pairs']
        train_regions = set(design['source_splits'][0]['train'])
        selected = sorted([r for r in records if r['region'] in train_regions], key=lambda r: r['id'])[:2]
        assert len(selected) == 2 and not any(r['region'] in design['new_test_regions'] for r in selected)
        report['source_image_ids'] = [r['id'] for r in selected]
        report['development_manifest_sha256'] = sha(ROOT / 'v2/data/development_manifest.json')
        images = [load_pair(r, ROOT / 'v2/data') for r in selected]
        seed_all(20261018)
        model = ResNet18UNet(pretrained=True).to('cuda').train()
        encoder = [p for n, p in model.named_parameters() if n.startswith(('stem.', 'enc'))]
        decoder = [p for n, p in model.named_parameters() if not n.startswith(('stem.', 'enc'))]
        optimizer = torch.optim.AdamW([{'params': encoder, 'lr': 3e-4}, {'params': decoder, 'lr': 3e-3}], weight_decay=1e-4)
        rng = np.random.default_rng(20261018)
        x, y = make_batch(images, rng, 2, 224)
        x, y = x.cuda(), y.cuda()
        report['tensor_device'] = str(x.device)
        strict_error = None
        try:
            optimizer.zero_grad(set_to_none=True)
            F.cross_entropy(model(x), y, ignore_index=255).backward()
            torch.cuda.synchronize()
        except RuntimeError as exc:
            strict_error = str(exc)
            if 'deterministic' not in strict_error.lower():
                raise
        report['strict_deterministic_backward_passed'] = strict_error is None
        report['strict_deterministic_error'] = strict_error
        # A diagnostic relaxation only; never silently modify the frozen trainer.
        torch.use_deterministic_algorithms(True, warn_only=True)
        before = model.stem[0].weight.detach().clone()
        bn_before = model.stem[1].running_mean.detach().clone()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        started = time.monotonic()
        losses = []
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            for step in range(1, 31):
                optimizer.zero_grad(set_to_none=True)
                loss = F.cross_entropy(model(x), y, ignore_index=255)
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite CUDA loss')
                loss.backward()
                if step in (1, 30):
                    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
                optimizer.step()
                losses.append(float(loss.detach()))
                if step in (1, 10, 20, 30):
                    print(json.dumps({'phase': 'cuda_training_preflight', 'step': step, 'device': str(x.device),
                                      'gpu': report['device'], 'loss': losses[-1]}), flush=True)
            torch.cuda.synchronize()
        report.update(steps=30, crop=224, batch_size=2, trainable_parameters=sum(p.numel() for p in model.parameters()),
                      seconds=time.monotonic()-started, losses=losses,
                      peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                      peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                      encoder_convolution_changed=not torch.equal(before, model.stem[0].weight),
                      encoder_bn_statistics_fixed=torch.equal(bn_before, model.stem[1].running_mean),
                      all_final_parameters_finite=all(torch.isfinite(p).all().item() for p in model.parameters()),
                      diagnostic_warn_only=True, warnings=sorted(set(str(w.message) for w in caught)))
        assert report['encoder_convolution_changed'] and report['encoder_bn_statistics_fixed'] and report['all_final_parameters_finite']
        report['passed'] = True
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'preflight_report': out.relative_to(ROOT).as_posix(), 'passed': report['passed']}), flush=True)


if __name__ == '__main__':
    main()
