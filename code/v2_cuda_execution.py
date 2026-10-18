"""Explicit secondary CUDA execution replication; original V2 remains immutable."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import sys
import json
import time
import platform
import argparse
import warnings
import gc
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import torch
import v2_segmentation as segmentation
from v2_segmentation import sha, fit, evaluate

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'configs/v2_cuda_execution_plan.json'
OUT = ROOT / 'evidence/v2/cuda_execution'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=True, indent=2)+'\n')


def used_bytes():
    return sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())


def prepare():
    # Use the original CPU interpreter and frozen selector to precompute IDs.
    from v2_run import load_locked, selected_info
    from v2_audit_runs import expected_matrix
    if PLAN.exists():
        raise RuntimeError('Plan already exists; do not overwrite a locked replication')
    freeze, design, manifest, index, development, panel = load_locked()
    calibration = read(ROOT/'evidence/v2/calibration/calibration.json')
    choices = {r['source_split']: r['chosen'] for r in calibration['splits']}
    splits = {r['id']: r for r in design['source_splits']}
    matrix = expected_matrix(design, read(ROOT/'configs/v2_extension.json'))
    runs = []
    for identity in matrix.values():
        if identity['model'] != 'resnet18_unet':
            continue
        s = identity['source_split']
        _, selection = selected_info(index, splits[s], identity['pool'], identity['budget'],
                                     identity['strategy'], identity['selection_seed'])
        runs.append({'identity': identity, 'selection': selection,
                     'encoder_lr': choices[s]['encoder_lr'], 'steps': choices[s]['steps']})
    assert len(runs) == 90
    preflight = read(ROOT/'evidence/v2/software/cuda_preflight.json')
    assert preflight['passed'] and not preflight['target_panel_opened']
    value = {'format': 'v2-cuda-execution-plan-1', 'created_utc': datetime.now(timezone.utc).isoformat(),
             'status': 'LOCKED_BEFORE_THIS_CUDA_REPLICATION_TARGET_EVALUATION',
             'interpretation': 'Secondary execution replication after user hardware correction; the panel has already been used by original CPU/frozen runs. This is not a new confirmatory holdout, architecture, primary or performance-driven revision.',
             'original_primary_and_576_matrix_unchanged': True,
             'motivation': 'Use the existing RTX4060 CUDA environment for complete-model training after CPU-only environment was identified.',
             'model_selection': 'Identical source-only selected IDs and existing CPU-calibrated LR/steps; no CUDA or target-specific hyperparameter tuning.',
             'numerical_limit': 'Python/Torch/NumPy versions and backend differ. CUDA NLLLoss2d has no strict deterministic implementation in this environment; warn-only deterministic mode is declared, so bitwise training equivalence is not promised.',
             'runtime': {'torch': preflight['torch'], 'numpy': preflight['numpy'], 'python': platform.python_version(),
                         'cuda_python': '3.12.3', 'cuda_build': preflight['cuda_build'], 'device': preflight['device'], 'threads': 2},
             'code_sha256': sha(Path(__file__)), 'original_freeze_sha256': sha(ROOT/'configs/v2_freeze.json'),
             'original_frozen_file_sha256': freeze['file_sha256'],
             'cuda_preflight_sha256': sha(ROOT/'evidence/v2/software/cuda_preflight.json'),
             'new_panel_image_ids': sorted(r['id'] for r in panel), 'expected_runs': 90,
             'checkpoints': 'No extra learned states saved; all90 result/log records and state hashes retained. Original CPU predetermined state/reload remains available.',
             'analysis_scope': 'All90 identities required. Compare actual/permuted quota and weighted coverage under the fixed skewed B12 recipe; report source and region sensitivity descriptively, separately from the original primary.',
             'runs': runs}
    write_new(PLAN, value)
    print(json.dumps({'cuda_plan': PLAN.relative_to(ROOT).as_posix(), 'sha256': sha(PLAN), 'planned': len(runs)}), flush=True)


def run(limit=None):
    plan = read(PLAN); plan_sha = sha(PLAN)
    assert plan['code_sha256'] == sha(Path(__file__))
    assert plan['original_freeze_sha256'] == sha(ROOT/'configs/v2_freeze.json')
    for name, digest in plan['original_frozen_file_sha256'].items():
        if sha(ROOT/name) != digest:
            raise RuntimeError('Original frozen input changed: '+name)
    assert torch.cuda.is_available(), 'CUDA required; never fall back to CPU'
    expected = plan['runtime']
    assert (torch.__version__, np.__version__, platform.python_version(), torch.version.cuda, torch.cuda.get_device_name(0)) == (
        expected['torch'], expected['numpy'], expected['cuda_python'], expected['cuda_build'], expected['device'])
    torch.set_num_threads(expected['threads'])
    original_seed = segmentation.seed_all
    def cuda_seed(seed):
        original_seed(seed)
        torch.use_deterministic_algorithms(True, warn_only=True)
    segmentation.seed_all = cuda_seed
    manifest = read(ROOT/'v2/data/manifest.json')
    design = read(ROOT/'configs/v2_design.json')
    by_id = {r['id']: r for r in manifest['pairs']}
    panel = [by_id[k] for k in plan['new_panel_image_ids']]
    splits = {r['id']: r for r in design['source_splits']}
    completed = 0; executed = 0
    OUT.mkdir(parents=True, exist_ok=True)
    lease = OUT/'writer.lock'
    with lease.open('x', encoding='utf-8') as f:
        f.write(json.dumps({'pid': os.getpid(), 'plan_sha256': plan_sha}))
    try:
        for spec in plan['runs']:
            identity = spec['identity']
            key = '_'.join(str(identity[k]) for k in ['source_split','pool','budget','selection_seed','initialization_seed','strategy'])
            folder = OUT/key; destination = folder/'result.json'
            if destination.exists():
                old = read(destination)
                assert old['status'] == 'complete' and old['plan_sha256'] == plan_sha and old['identity'] == identity
                assert sha(ROOT/old['log_file']) == old['log_sha256']
                completed += 1
                continue
            if limit is not None and executed >= limit:
                break
            if used_bytes()+55_000_000 >= 2_000_000_000:
                raise RuntimeError('Whole-root2GB reserve unavailable')
            assert sha(PLAN) == plan_sha and sha(Path(__file__)) == plan['code_sha256']
            selected = [by_id[k] for k in spec['selection']['selected_ids']]
            source = splits[identity['source_split']]
            assert len(selected) == 12 and all(r['region'] in source['train'] for r in selected)
            validation = [r for r in manifest['pairs'] if r['region'] in source['validation']]
            assert len(validation) == 20 and len(panel) == 72
            folder.mkdir(parents=True, exist_ok=True)
            attempt = str(time.time_ns())
            log = folder/('training_attempt_'+attempt+'.jsonl')
            write_new(folder/('attempt_'+attempt+'.json'), {'status':'started','identity':identity,'plan_sha256':plan_sha,'device':'cuda:0'})
            def callback(entry):
                with log.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(entry)+'\n')
                if entry['step'] == 1 or entry['step'] % 300 == 0:
                    print(json.dumps({'phase':'cuda_full_training','run':key,'step':entry['step'],
                                      'device':'cuda:0','gpu':torch.cuda.get_device_name(0),
                                      'allocated_bytes':torch.cuda.memory_allocated()}), flush=True)
            started = time.monotonic(); torch.cuda.reset_peak_memory_stats()
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('default')
                    model, training = fit(selected, ROOT/'v2/data', seed=identity['initialization_seed'],
                                          encoder_lr=spec['encoder_lr'], steps=spec['steps'], device='cuda:0',
                                          batch_size=2, crop=224, log_callback=callback)
                    test = evaluate(model, panel, ROOT/'v2/data', 'cuda:0')
                    val = evaluate(model, validation, ROOT/'v2/data', 'cuda:0')
                    torch.cuda.synchronize()
                result = {'format':'v2-cuda-execution-result-1','status':'complete','identity':identity,
                          'plan_sha256':plan_sha,'code_sha256':sha(Path(__file__)),
                          'selection':spec['selection'],'training':training,'test':test,'validation':val,
                          'log_file':log.relative_to(ROOT).as_posix(),'log_sha256':sha(log),
                          'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                          'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved(),
                          'deterministic_warn_only':True,'warnings':sorted(set(str(w.message) for w in caught)),
                          'total_seconds':time.monotonic()-started,'created_utc':datetime.now(timezone.utc).isoformat()}
                write_new(destination, result)
                del model; gc.collect(); torch.cuda.empty_cache()
            except Exception as exc:
                write_new(folder/('failure_'+attempt+'.json'), {'identity':identity,'error':type(exc).__name__+': '+str(exc),'plan_sha256':plan_sha})
                raise
            completed += 1; executed += 1
            print(json.dumps({'cuda_completed':completed,'planned':90,'run':key,'seconds':result['total_seconds']}), flush=True)
        print(json.dumps({'cuda_replication_completed':completed,'planned':90,'newly_executed':executed}), flush=True)
    finally:
        segmentation.seed_all = original_seed
        lease.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    prepare() if args.prepare else run(args.limit)
