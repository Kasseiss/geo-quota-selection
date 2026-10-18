"""Record exact-code synthetic checks before the first new-panel model score."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    jobs=[
        ('weighted_selection_validation.json',['code/test_v2_weighted_selection.py'],
         ['code/test_v2_weighted_selection.py','code/v2_weighted_selection.py','code/v2_selection.py','code/core.py']),
        ('runs_audit_validation.json',['code/v2_audit_runs.py','--self-test'],
         ['code/v2_audit_runs.py','code/v2_weighted_selection.py','configs/v2_design.json','configs/v2_extension.json']),
        ('statistics_validation.json',['code/v2_statistics.py','--self-test'],
         ['code/v2_statistics.py','code/v2_audit_runs.py','configs/v2_design.json','configs/v2_extension.json']),
        ('data_audit_validation.json',['code/v2_audit_data.py','--self-test'],
         ['code/v2_audit_data.py','code/geography_audit.py'])]
    for name,args,files in jobs:
        binding={relative:sha(ROOT/relative) for relative in files}
        started=datetime.now(timezone.utc).isoformat()
        result=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        unchanged=all(sha(ROOT/relative)==checksum for relative,checksum in binding.items())
        report=dict(passed=result.returncode==0 and unchanged,started_utc=started,
            completed_utc=datetime.now(timezone.utc).isoformat(),command=['python',*args],
            validated_file_sha256=binding,code_unchanged_during_check=unchanged,
            stdout=result.stdout,stderr=result.stderr,returncode=result.returncode,
            scientific_new_panel_scores_read=False,synthetic_checks_only=True)
        destination=ROOT/'evidence/v2/software'/name
        destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'report':name,'passed':report['passed']}),flush=True)
        if not report['passed']:raise RuntimeError('Software validation failed: '+name)


if __name__=='__main__':main()
