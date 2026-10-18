"""Bind the complete extension before any new-panel segmentation evaluation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import shutil

from v2_run import ROOT, REQUIRED_FREEZE_FILES
from v2_segmentation import sha, records_sha


def main():
    destination=ROOT/'configs/v2_freeze.json'
    if destination.exists():raise RuntimeError('An extension freeze already exists; never overwrite it after target scoring')
    if list((ROOT/'evidence/v2/runs').glob('**/result.json')):
        raise RuntimeError('Target results exist before the declared freeze')
    design=json.loads((ROOT/'configs/v2_design.json').read_text())
    extension=json.loads((ROOT/'configs/v2_extension.json').read_text())
    assert extension['primary_unchanged'] and extension['expected_total_runs']==576
    assert extension['base_design_sha256']==sha(ROOT/'configs/v2_design.json')
    assert extension['initialization_seed_by_selection_seed']=={'0':0,'1':1,'2':2}
    assert extension['randomization_amendment_before_new_panel_scores']
    calibration=json.loads((ROOT/'evidence/v2/calibration/calibration.json').read_text())
    assert calibration['complete'] and len(calibration['splits'])==3
    assert calibration['design_sha256']==sha(ROOT/'configs/v2_design.json')
    for name,checksum in calibration['execution_code_sha256'].items():assert sha(ROOT/'code'/name)==checksum
    dev=json.loads((ROOT/'v2/data/development_manifest.json').read_text())
    manifest=json.loads((ROOT/'v2/data/manifest.json').read_text())
    assert manifest['status']=='complete' and manifest['whole_v2_dataset_complete'] and len(manifest['pairs'])==192
    assert records_sha(dev['pairs'])==calibration['development_records_sha256']
    assert calibration['development_manifest_sha256']==sha(ROOT/'v2/data/development_manifest.json')
    assert records_sha([r for r in manifest['pairs'] if r['role']=='old_development'])==records_sha(dev['pairs'])
    data_audit=json.loads((ROOT/'evidence/v2/data_audit.json').read_text())
    assert data_audit['passed']
    assert data_audit['audit_code_sha256']==sha(ROOT/'code/v2_audit_data.py')
    assert data_audit['geography_helper_sha256']==sha(ROOT/'code/geography_audit.py')
    for item in data_audit['inputs'].values():
        assert sha(ROOT/item['path'])==item['sha256'], 'Stale data audit: '+item['path']
    # Bind the reviewed CRS cautions even though no overlapping bbox candidate
    # was found; zero candidates cannot promote invalid-area geometry to proof.
    review=json.loads((ROOT/'evidence/v2/geographic_disposition.json').read_text())
    assert review['data_audit_sha256']==sha(ROOT/'evidence/v2/data_audit.json')
    assert review['decision']=='RETAIN_WITH_EXPLICIT_LIMITATION_AND_SENSITIVITY'
    assert review['sensitivity_configuration_sha256']==sha(ROOT/'configs/v2_geographic_sensitivity.json')
    assert review['new_panel_model_scores_available_at_review'] is False
    panel_index=json.loads((ROOT/'v2/cache/new_panel_dinov2/index.json').read_text())
    assert panel_index['status']=='complete' and len(panel_index['records'])==72
    assert panel_index['identity']['manifest_sha256']==sha(ROOT/'v2/data/manifest.json')
    assert panel_index['identity']['extractor_sha256']==sha(ROOT/'code/v2_extract_panel.py')
    for r in panel_index['records']:
        assert sha(ROOT/'v2/cache/new_panel_dinov2'/r['cache'])==r['cache_sha256']
    files=set(REQUIRED_FREEZE_FILES)|{'code/v2_freeze.py','code/v2_audit_runs.py','code/v2_statistics.py',
                                    'code/v2_validate_software.py','code/test_v2_training.py',
                                    'evidence/v2/source_selection_seed_diagnostic.json',
                                    'evidence/v2/prospective_amendments/weighted_fl_before_fit_seed_amendment.json'}
    if data_audit.get('human_review_required'):
        files.add('evidence/v2/geographic_disposition.json')
    for part in calibration['splits']:
        assert part['source_split'] in [s['id'] for s in design['source_splits']]
        assert len(part['settings'])==6
        expected=sorted(part['settings'],key=lambda x:(-x['validation_union_miou'],x['steps'],x['encoder_lr']))[0]
        assert part['chosen']==expected
        for setting in part['settings']:
            files.add(setting['record'])
            record=json.loads((ROOT/setting['record']).read_text())
            assert record['status']=='complete' and record['identity']['environment']==calibration['environment']
            assert [r['step'] for r in record['history']['validation']]==design['full_model']['calibration_checkpoints']
            assert sha(ROOT/record['log_file'])==record['log_sha256'];files.add(record['log_file'])
    software=ROOT/'evidence/v2/software'
    for required in ['preparation_validation.json','segmentation_validation.json','training_prefix_validation.json','data_audit_validation.json',
                     'weighted_selection_validation.json','runs_audit_validation.json','statistics_validation.json']:
        path=software/required
        assert path.exists();files.add(path.relative_to(ROOT).as_posix())
        check=json.loads(path.read_text())
        if required=='preparation_validation.json':
            assert check['failures']==check['errors']==0 and check['tests']>=8
            assert check['conversion_code_sha256']==sha(ROOT/'code/v2_prepare_data.py')
        else:assert check['passed']
        if required=='training_prefix_validation.json':
            assert check['model_code_sha256']==sha(ROOT/'code/v2_segmentation.py')
            assert check['test_code_sha256']==sha(ROOT/'code/test_v2_training.py')
        if required in ['weighted_selection_validation.json','runs_audit_validation.json','statistics_validation.json','data_audit_validation.json']:
            assert check['validated_file_sha256']
            for name,checksum in check['validated_file_sha256'].items():
                assert sha(ROOT/name)==checksum, 'Stale software check: '+name
                files.add(name)
    frozen={'status':'FROZEN_BEFORE_NEW_PANEL_EVALUATION','frozen_utc':datetime.now(timezone.utc).isoformat(),
            'expected_full_runs':90,'expected_frozen_runs':486,'expected_total_runs':576,
            'base_runs':504,'prospective_supplement_runs':72,
            'primary':design['primary'],'calibration_environment':calibration['environment'],
            'file_sha256':{name:sha(ROOT/name) for name in sorted(files)},
            'source_snapshot':'evidence/v2/source_snapshot',
            'nonclaims':['No public preregistration','No journal acceptance guarantee','No equivalence margin or post-hoc positive-result selection']}
    snapshot=ROOT/'evidence/v2/source_snapshot';snapshot.mkdir(exist_ok=False)
    for name in sorted(files):
        if name.startswith(('code/','configs/','docs/')):
            target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    destination.write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    print(json.dumps({'status':frozen['status'],'files':len(files),'expected_runs':576,'freeze_sha256':sha(destination)},indent=2))


if __name__=='__main__':main()
