"""Run AeoLiS on a case folder with the installed `aeolis` command."""
import os
import re
import shutil
import subprocess
import sys

PCT = re.compile(r'^\s*(\d{1,3}\.\d)%')


def aeolis_cmd():
    exe = shutil.which('aeolis')
    if exe:
        return [exe]
    return [sys.executable, '-m', 'aeolis.console']


def run(case_dir, progress=None):
    """Run the case. progress(fraction 0-1) is called as AeoLiS reports progress.

    Returns (ok, log_tail). The full log is AeoLiS' own aeolis.log in the case folder.
    """
    cmd = aeolis_cmd() + ['run', 'aeolis.txt']
    p = subprocess.Popen(cmd, cwd=case_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1)
    tail = []
    for line in p.stdout:
        tail = (tail + [line.rstrip()])[-40:]
        m = PCT.match(line)
        if m and progress:
            progress(min(float(m.group(1)) / 100.0, 1.0))
    p.wait()
    ok = p.returncode == 0 and os.path.exists(os.path.join(case_dir, 'aeolis.nc'))
    if progress and ok:
        progress(1.0)
    return ok, '\n'.join(tail)
