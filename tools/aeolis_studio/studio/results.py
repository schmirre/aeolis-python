"""Read aeolis.nc and compare the result with measured profiles."""
import json
import os

import netCDF4
import numpy as np
import pandas as pd

RHO_SED = 2650.0


def load(case_dir):
    """Model output as plain numpy arrays plus timestamps."""
    meta = json.load(open(os.path.join(case_dir, 'scenario.json')))
    d = netCDF4.Dataset(os.path.join(case_dir, 'aeolis.nc'))
    x = np.array(d['x'][0, :])
    t = np.array(d['time'][:])
    zb = np.array(d['zb'][:, 0, :])
    zs = np.array(d['zs'][:, 0, :]) if 'zs' in d.variables else None
    qs = np.array(d['qs'][:, 0, :, :]).sum(-1) if 'qs' in d.variables else None
    d.close()
    start = pd.Timestamp(meta['start'])
    return {'x': x, 't_s': t, 'time': [start + pd.Timedelta(seconds=float(s)) for s in t],
            'zb': zb, 'zs': zs, 'qs': qs, 'meta': meta}


def zone_volumes(x, z0, z1, zones):
    """Net volume change (m3/m) per zone; zones = {name: (x_from, x_to)}."""
    dx = np.gradient(x)
    out = {}
    for name, (a, b) in zones.items():
        sel = (x >= a) & (x <= b)
        out[name] = float(((z1 - z0) * dx)[sel].sum())
    return out


def volume_series(res, zones):
    x, zb = res['x'], res['zb']
    rows = []
    for i, tm in enumerate(res['time']):
        v = zone_volumes(x, zb[0], zb[i], zones)
        v['time'] = tm
        rows.append(v)
    return pd.DataFrame(rows).set_index('time')


def compare(res, measured_after, zones, x_range=None):
    """Compare the model's final profile with the measured 'after' profile.

    Returns a dict with RMSE and bias of bed level, Brier skill score (BSS, where
    1 is perfect and 0 is no better than assuming no change), and measured versus
    modelled volume change per zone.
    """
    x, z0, zm = res['x'], res['zb'][0], res['zb'][-1]
    zmeas = np.interp(x, measured_after['x_m'], measured_after['z_m'], left=np.nan, right=np.nan)
    sel = ~np.isnan(zmeas)
    if x_range:
        sel &= (x >= x_range[0]) & (x <= x_range[1])
    if sel.sum() < 3:
        raise ValueError('För lite överlapp mellan modellprofil och uppmätt profil.')
    err = zm[sel] - zmeas[sel]
    mse = float(np.mean(err ** 2))
    mse0 = float(np.mean((z0[sel] - zmeas[sel]) ** 2))
    zmeas_full = np.where(np.isnan(zmeas), z0, zmeas)
    vm = zone_volumes(x, z0, zmeas_full, zones)
    vmod = zone_volumes(x, z0, zm, zones)
    return {
        'rmse_m': float(np.sqrt(mse)),
        'bias_m': float(np.mean(err)),
        'bss': float(1 - mse / mse0) if mse0 > 0 else float('nan'),
        'zones': {k: {'measured_m3_per_m': vm[k], 'model_m3_per_m': vmod[k], 'error_m3_per_m': vmod[k] - vm[k]}
                  for k in zones},
        'x_range': [float(x[sel].min()), float(x[sel].max())],
    }


def default_zones(x, z, toe_level=None, wl=None):
    """A first guess at zones: beach up to the dune toe, dune from the toe landwards."""
    if toe_level is None:
        toe_level = 3.0
    idx = np.where(z >= toe_level)[0]
    xt = float(x[idx[0]]) if len(idx) else float(x[len(x) // 2])
    return {'Strand': (float(x.min()), xt), 'Dyn': (xt, float(x.max()))}
