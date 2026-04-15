import os
import shutil
from pathlib import Path

def cleanup():
    ops = Path('ops/scripts')
    archive = ops / 'archive'
    archive.mkdir(exist_ok=True)
    
    keep = {
        'pr_self_review.py', 'pr_triage.py', 'run_workspace_smoke.py', 
        'healthcheck.py', 'cost_intelligence.py', 'cost_dashboard.py', 
        'dora_metrics.py', 'roi_report.py', 'tech_debt_scanner.py', 
        'orchestrator.py', 'prefect_orchestrator.py', 'workspace_summary.py', 
        'workspace_paths.py'
    }
    
    # move .py files
    for f in ops.glob('*.py'):
        if f.name not in keep and f.name != 'cleanup_scripts.py' and not f.name.startswith('_'):
            shutil.move(str(f), str(archive / f.name))
            print(f'Moved {f.name}')
            
    # move .ps1, .bat, .sh files that are no longer actively maintained there
    for ext in ['*.ps1', '*.bat', '*.sh']:
        for f in ops.glob(ext):
             shutil.move(str(f), str(archive / f.name))
             print(f'Moved {f.name}')

if __name__ == '__main__':
    cleanup()
