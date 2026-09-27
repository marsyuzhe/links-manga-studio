"""Measure isolated offscreen startup and package costs without contacting services."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def child(output: Path, eager_control: bool = False) -> None:
    started = time.perf_counter()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QWidget
    from app.config import Config
    from app.project import ProjectService
    from app.ui.window import MainWindow
    from app.translation.profiles import WindowsSecrets
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('Startup attempted network or credential access')
    socket.socket.connect = forbidden
    WindowsSecrets.get = forbidden
    config = Config(output.with_suffix('.config.json'))
    config.data['translation_profiles'] = [dict(id='startup-fixture',name='Fixture',provider_type='openai',
        base_url='https://api.example.invalid/v1',model='fixture')]
    app = QApplication([])
    w = MainWindow(ProjectService(config),output.with_suffix('.log'))
    if eager_control:
        # Counterfactual control: materialize the same views using the current code.
        # This isolates widget construction cost; it is not an old-version checkout.
        _ = w.translation_center, w.glossary_workspace
    w.show(); app.processEvents()
    ready = (time.perf_counter()-started)*1000
    output.with_suffix('.ready').write_text(str(time.perf_counter()),encoding='ascii')
    def idle():
        modules = sorted(sys.modules)
        widgets = len(w.findChildren(QWidget))
        # Collect memory after the startup module inventory, excluding audit instrumentation imports.
        from tools.benchmark_phase1 import rss_mb
        report = dict(platform='Qt offscreen; not visible desktop timing',startup_window_ready_ms=round(ready,2),
            idle_observation_ms=750,ui_widget_count=widgets,modules=modules,imported_modules=len(modules),
            rss_mib=round(rss_mb(),2),background_jobs=len(w.workspace.jobs),
            ai_network_and_credential_access='NONE (guarded)',
            eager_control=eager_control,
            translation_page_created=(getattr(w,'_translation_center',None) or w.__dict__.get('translation_center')) is not None,
            glossary_page_created=(getattr(w,'_glossary_workspace',None) or w.__dict__.get('glossary_workspace')) is not None)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        w.close(); app.quit()
    QTimer.singleShot(750,idle); app.exec()


def package(path: Path) -> dict:
    files=[p for p in path.rglob('*') if p.is_file()]
    suffixes={}
    for p in files: suffixes[p.suffix]=suffixes.get(p.suffix,0)+p.stat().st_size
    return dict(path=path.relative_to(ROOT).as_posix(),files=len(files),bytes=sum(p.stat().st_size for p in files),
        suffix_bytes=suffixes,models=[dict(path=p.relative_to(path).as_posix(),bytes=p.stat().st_size) for p in files if p.suffix=='.onnx'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--child',type=Path);parser.add_argument('--label',default='before');parser.add_argument('--eager-control',action='store_true');parser.add_argument('--paired',action='store_true');args=parser.parse_args()
    if args.child: child(args.child,args.eager_control); return
    destination=ROOT/'dev_data'/f'lightweight-{args.label}';destination.mkdir(parents=True,exist_ok=True)
    runs=[]
    with tempfile.TemporaryDirectory(prefix='lmw-startup-audit-') as tmp:
        for n in range(6 if args.paired else 3):
            output=destination/f'startup-{n+1}.json';env={**os.environ,'QT_QPA_PLATFORM':'offscreen','LMW_CONFIG_DIR':tmp,'PYTHONUTF8':'1'}
            start=time.perf_counter()
            command=[sys.executable,'-m','tools.audit_lightweight','--child',str(output)]
            if args.paired and n%2==0:command.append('--eager-control')
            subprocess.run(command,cwd=ROOT,env=env,check=True,capture_output=True,timeout=45)
            row=json.loads(output.read_text(encoding='utf-8'));row['process_to_exit_ms']=round((time.perf_counter()-start)*1000,2);runs.append(row)
            row['process_start_to_ready_ms']=round((float(output.with_suffix('.ready').read_text())-start)*1000,2)
    paths=[ROOT/'dist/0.6.0-rc-r3/Links Manga Studio',ROOT/'dist/0.6.0-final/Links Manga Studio']
    report=dict(runs=runs,packages=[package(p) for p in paths if p.exists()])
    (destination/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in row.items() if k!='modules'} for row in runs],ensure_ascii=False))

if __name__=='__main__': main()
