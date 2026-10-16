"""Build an AeoLiS 1D case folder from a scenario.

Nothing here changes AeoLiS. A case is a folder with aeolis.txt and the input
files AeoLiS reads, plus scenario.json describing how it was made.
"""
import json
import os
import re
import shutil
from datetime import datetime

import numpy as np
import pandas as pd

from . import ioutil

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'template_aeolis.txt')

DEFAULTS = {
    'name': 'scenario',
    'profile_before': None,          # path to profil_YYYY-MM-DD.csv
    'profile_after': None,           # optional, for comparison and calibration
    'start': None,                   # 'YYYY-MM-DD HH:MM' (default: date of profile_before)
    'end': None,                     # default: date of profile_after
    'wind': None, 'waterlevel': None, 'waves': None, 'sediment': None,
    'constant_hs_m': 0.3, 'constant_tp_s': 5.0,  # used when no wave file
    'wind_height_m': 10.0,           # measurement height of the wind
    'coast_normal_deg': 270.0,       # direction onshore wind comes FROM (nautical)
    'dx_m': 0.5,
    'd50_mm': 0.3,                   # used when no sediment file
    'veg_x_m': None,                 # vegetation from this x landwards (None = none)
    'veg_density': 0.3,              # cover fraction 0-1
    'moisture': True,
    'wet_bed_reset': False,
    'avalanche': True,
    'method_transport': 'bagnold',
    'Cb': 1.5,
    'T': 1.0,
    'beach_slope': None,             # None = computed from the profile near mean water level
    'dt_s': 3600,
    'output_s': 21600,
    'nlayers': 3, 'layer_thickness': 0.05,
}


def scenario(**kw):
    s = dict(DEFAULTS)
    unknown = set(kw) - set(DEFAULTS)
    if unknown:
        raise ValueError('Okända inställningar: %s' % ', '.join(sorted(unknown)))
    s.update(kw)
    return s


def set_param(txt, key, val):
    pat = re.compile(r'^(\s*%s\s*=).*$' % re.escape(key), re.M)
    if pat.search(txt):
        return pat.sub(lambda m: '%s  %s' % (m.group(1), val), txt)
    return txt + '\n%s = %s\n' % (key, val)


def _parse_time(v):
    if v is None or isinstance(v, datetime):
        return v
    return pd.Timestamp(v).to_pydatetime()


def resolve_period(s):
    before, d0 = ioutil.read_profile(s['profile_before'])
    after, d1 = (None, None)
    if s.get('profile_after'):
        after, d1 = ioutil.read_profile(s['profile_after'])
    start = _parse_time(s['start']) or d0
    end = _parse_time(s['end']) or d1
    if start is None or end is None:
        raise ValueError('Ange start och slut, eller använd profilfiler med datum i namnet (profil_YYYY-MM-DD.csv).')
    if end <= start:
        raise ValueError('Slutdatum måste vara efter startdatum.')
    return before, after, start, end


def build(s, outdir):
    """Write a complete AeoLiS case for scenario s into outdir. Returns outdir."""
    before, after, start, end = resolve_period(s)
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)

    # grid
    x = np.arange(before['x_m'].min(), before['x_m'].max() + 1e-9, s['dx_m'])
    z = np.interp(x, before['x_m'], before['z_m'])
    np.savetxt(os.path.join(outdir, 'x.grd'), x, fmt='%.4f')
    np.savetxt(os.path.join(outdir, 'y.grd'), np.zeros_like(x), fmt='%.4f')
    np.savetxt(os.path.join(outdir, 'z.grd'), z, fmt='%.4f')
    veg = np.zeros_like(x)
    if s.get('veg_x_m') is not None:
        veg[x >= float(s['veg_x_m'])] = float(s['veg_density'])
    np.savetxt(os.path.join(outdir, 'veg.grd'), veg, fmt='%.4f')

    # forcing
    wind = ioutil.read_wind(s['wind'])
    wl = ioutil.read_waterlevel(s['waterlevel'])
    waves = ioutil.read_waves(s['waves']) if s.get('waves') else None
    w = ioutil.wind_to_seconds(wind, start, end)
    tide = ioutil.to_seconds(wl, start, end, ['wl_m'])
    wav = ioutil.to_seconds(waves, start, end, ['hs_m', 'tp_s'], fill=(s['constant_hs_m'], s['constant_tp_s']))
    np.savetxt(os.path.join(outdir, 'wind.txt'), w, fmt='%.3f')
    np.savetxt(os.path.join(outdir, 'tide.txt'), tide, fmt='%.4f')
    np.savetxt(os.path.join(outdir, 'wave.txt'), wav, fmt='%.4f')

    # sediment
    if s.get('sediment'):
        sed = ioutil.read_sediment(s['sediment'])
        sizes = ' '.join('%.6f' % (d / 1000) for d in sed['d_mm'])
        dist = ' '.join('%.4f' % (p / 100) for p in sed['mass_pct'])
        nfrac = len(sed)
    else:
        sizes, dist, nfrac = '%.6f' % (s['d50_mm'] / 1000), '1.0', 1

    # beach slope for run-up: profile slope between mean water level and +1 m above it
    slope = s.get('beach_slope')
    if slope is None:
        mwl = float(np.mean(tide[:, 1]))
        sel = (z >= mwl) & (z <= mwl + 1.0)
        slope = float(np.polyfit(x[sel], z[sel], 1)[0]) if sel.sum() >= 3 else 0.05
        slope = min(max(slope, 0.01), 0.3)

    txt = open(TEMPLATE).read()
    params = {
        'tstart': 0, 'tstop': int((end - start).total_seconds()), 'dt': s['dt_s'],
        'refdate': start.strftime('%Y-%m-%d %H:%M'),
        'output_times': s['output_s'], 'output_vars': 'zb zs qs mass w Hs',
        'nx': len(x) - 1, 'ny': 0, 'dx': s['dx_m'],
        'veg_file': 'veg.grd', 'process_vegetation': 'T' if s.get('veg_x_m') is not None else 'F',
        'wind_convention': 'nautical', 'alfa': '%.2f' % (float(s['coast_normal_deg']) - 270.0),
        'z': s['wind_height_m'],
        'grain_size': sizes, 'grain_dist': dist, 'nfractions': nfrac,
        'nlayers': s['nlayers'], 'layer_thickness': s['layer_thickness'],
        'process_moist': 'T' if s['moisture'] else 'F', 'th_moisture': 'T' if s['moisture'] else 'F',
        'method_moist_process': 'infiltration', 'method_moist_threshold': 'belly_johnson',
        'process_wet_bed_reset': 'T' if s['wet_bed_reset'] else 'F',
        'process_avalanche': 'T' if s['avalanche'] else 'F',
        'method_transport': s['method_transport'], 'Cb': s['Cb'], 'T': s['T'],
        'beach_slope': '%.4f' % slope,
    }
    for k, v in params.items():
        txt = set_param(txt, k, v)
    open(os.path.join(outdir, 'aeolis.txt'), 'w').write(txt)

    if after is not None:
        after.to_csv(os.path.join(outdir, 'measured_after.csv'), index=False)
    before.to_csv(os.path.join(outdir, 'measured_before.csv'), index=False)
    meta = dict(s)
    meta.update({'start': start.isoformat(), 'end': end.isoformat(), 'beach_slope_used': slope,
                 'built': datetime.now().isoformat(timespec='seconds')})
    for k in ['profile_before', 'profile_after', 'wind', 'waterlevel', 'waves', 'sediment']:
        if meta.get(k) is not None and not isinstance(meta[k], str):
            meta[k] = getattr(meta[k], 'name', 'uppladdad fil')
    json.dump(meta, open(os.path.join(outdir, 'scenario.json'), 'w'), indent=1, default=str)
    return outdir
