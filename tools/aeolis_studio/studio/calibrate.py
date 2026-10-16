"""Calibration by sampling: Latin hypercube over chosen parameters, every sample a full AeoLiS run.

Kept deliberately simple and transparent: every run is an ordinary case folder
that can be opened and re-run by hand, and results.csv lists every sample and its score.
"""
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.stats import qmc

from . import case, results, run as runner

# name: (low, high, log-scale?) - the defaults offered in the app
PARAM_SPACE = {
    'Cb': (1.0, 3.0, False),
    'T': (0.5, 10.0, True),
}


def samples(space, n, seed=1):
    names = list(space)
    u = qmc.LatinHypercube(d=len(names), seed=seed).random(n)
    out = []
    for row in u:
        p = {}
        for k, ui in zip(names, row):
            lo, hi, lg = space[k]
            p[k] = float(np.exp(np.log(lo) + ui * (np.log(hi) - np.log(lo))) if lg else lo + ui * (hi - lo))
        out.append(p)
    return out


def narrowed_space(df, space, top=5, margin=0.15):
    """A smaller search box around the best `top` samples, for a second round."""
    best = df[df['ok']].head(top)
    out = {}
    for k, (lo, hi, lg) in space.items():
        a, b = best[k].min(), best[k].max()
        pad = (b - a) * margin or (hi - lo) * 0.05
        out[k] = (max(lo, a - pad), min(hi, b + pad), lg)
    return out


def score(cmp, objective, zone):
    if objective == 'rmse':
        return cmp['rmse_m']
    if objective == 'volym':
        return abs(cmp['zones'][zone]['error_m3_per_m'])
    raise ValueError('Okänt mål: %s' % objective)


def _one(args):
    scn, folder, zones, objective, zone, x_range = args
    case.build(scn, folder)
    ok, tail = runner.run(folder)
    if not ok:
        return {'folder': folder, 'ok': False, 'log': tail}
    res = results.load(folder)
    after = pd.read_csv(os.path.join(folder, 'measured_after.csv'))
    cmp = results.compare(res, after, zones, x_range)
    json.dump(cmp, open(os.path.join(folder, 'comparison.json'), 'w'), indent=1)
    row = {'folder': folder, 'ok': True, 'score': score(cmp, objective, zone), 'rmse_m': cmp['rmse_m'],
           'bss': cmp['bss']}
    for k, v in cmp['zones'].items():
        row['%s model (m3/m)' % k] = v['model_m3_per_m']
        row['%s uppmätt (m3/m)' % k] = v['measured_m3_per_m']
    return row


def calibrate(base, space, n, outdir, zones, objective='volym', zone='Dyn', x_range=None,
              workers=2, seed=1, progress=None):
    """Run n samples. base is a scenario dict with profile_after set. Returns a DataFrame sorted by score."""
    if not base.get('profile_after'):
        raise ValueError('Kalibrering kräver en uppmätt profil efter (profile_after).')
    os.makedirs(outdir, exist_ok=True)
    jobs, params = [], samples(space, n, seed)
    for i, p in enumerate(params):
        scn = dict(base, **p, name='%s_kal%02d' % (base['name'], i))
        jobs.append((scn, os.path.join(outdir, 'kal%02d' % i), zones, objective, zone, x_range))
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, j): i for i, j in enumerate(jobs)}
        for done, f in enumerate(as_completed(futs), 1):
            i = futs[f]
            r = f.result()
            r.update(params[i])
            rows.append(r)
            if progress:
                progress(done / len(jobs), r)
    df = pd.DataFrame(rows).sort_values('score', na_position='last').reset_index(drop=True)
    df.to_csv(os.path.join(outdir, 'results.csv'), index=False)
    json.dump({'space': {k: list(v) for k, v in space.items()}, 'n': n, 'objective': objective, 'zone': zone,
               'zones': zones, 'seed': seed}, open(os.path.join(outdir, 'calibration.json'), 'w'), indent=1)
    return df
