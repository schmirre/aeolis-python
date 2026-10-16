"""Reading the user's CSV files.

Formats (all times in UTC, all levels in RH2000):
  profil_YYYY-MM-DD.csv : x_m, z_m          (x from a fixed reference point, increasing landwards)
  vind.csv              : time_utc, speed_ms, dir_deg   (direction the wind comes FROM, 0 = north)
  vattenstand.csv       : time_utc, wl_m
  vagor.csv             : time_utc, hs_m, tp_s
  sediment.csv          : d_mm, mass_pct
Comma or semicolon separators and decimal comma are both accepted.
"""
import io
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd

DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def _read(src):
    """Read a CSV from a path, bytes or file-like object; tolerate ';' and decimal comma."""
    if hasattr(src, 'read'):
        raw = src.read()
    elif isinstance(src, (bytes, bytearray)):
        raw = src
    else:
        with open(src, 'rb') as f:
            raw = f.read()
    text = raw.decode('utf-8-sig') if isinstance(raw, (bytes, bytearray)) else raw
    first = text.splitlines()[0] if text else ''
    sep = ';' if first.count(';') > first.count(',') else ','
    df = pd.read_csv(io.StringIO(text), sep=sep, decimal=',' if sep == ';' else '.')
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _need(df, cols, what):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError('%s saknar kolumn(er): %s. Hittade: %s' % (what, ', '.join(missing), ', '.join(df.columns)))


def date_from_name(name):
    m = DATE_RE.search(os.path.basename(str(name)))
    return datetime.strptime(m.group(1), '%Y-%m-%d') if m else None


def read_profile(src, name=None):
    df = _read(src)
    _need(df, ['x_m', 'z_m'], 'Profilfil')
    df = df[['x_m', 'z_m']].dropna().sort_values('x_m').drop_duplicates('x_m')
    if len(df) < 3:
        raise ValueError('Profilen har för få punkter.')
    return df.reset_index(drop=True), date_from_name(name or getattr(src, 'name', src))


def _series(src, cols, what):
    df = _read(src)
    _need(df, ['time_utc'] + cols, what)
    df['time_utc'] = pd.to_datetime(df['time_utc'], utc=True).dt.tz_localize(None)
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['time_utc'] + cols).sort_values('time_utc').drop_duplicates('time_utc')
    return df[['time_utc'] + cols].reset_index(drop=True)


def read_wind(src):
    return _series(src, ['speed_ms', 'dir_deg'], 'Vindfil')


def read_waterlevel(src):
    return _series(src, ['wl_m'], 'Vattenståndsfil')


def read_waves(src):
    return _series(src, ['hs_m', 'tp_s'], 'Vågfil')


def read_sediment(src):
    df = _read(src)
    _need(df, ['d_mm', 'mass_pct'], 'Sedimentfil')
    df = df[['d_mm', 'mass_pct']].dropna()
    df = df[df['mass_pct'] > 0].sort_values('d_mm')
    if df.empty:
        raise ValueError('Sedimentfilen innehåller inga klasser med massprocent över 0.')
    df['mass_pct'] = 100 * df['mass_pct'] / df['mass_pct'].sum()
    return df.reset_index(drop=True)


def to_seconds(df, start, end, cols, fill=None):
    """Cut a series to [start, end] and express time as seconds since start.

    Values at start and end are interpolated so the model always has forcing
    over the whole period. Gaps are bridged by linear interpolation.
    """
    if df is None or df.empty:
        if fill is None:
            raise ValueError('Tidsserie saknas.')
        return np.array([[0.0] + list(fill), [(end - start).total_seconds()] + list(fill)])
    t = (df['time_utc'] - pd.Timestamp(start)).dt.total_seconds().to_numpy()
    T = (end - start).total_seconds()
    if t.min() > 0 or t.max() < T:
        raise ValueError('Tidsserien täcker inte hela perioden %s till %s (den går från %s till %s).'
                         % (start, end, df['time_utc'].min(), df['time_utc'].max()))
    keep = (t >= 0) & (t <= T)
    rows = [np.interp(0.0, t, df[c]) for c in cols]
    out = [[0.0] + rows]
    for i in np.where(keep)[0]:
        if 0 < t[i] < T:
            out.append([t[i]] + [df[c].iloc[i] for c in cols])
    out.append([T] + [np.interp(T, t, df[c]) for c in cols])
    return np.array(out, dtype=float)


def wind_to_seconds(df, start, end):
    """Like to_seconds, but interpolates direction as a vector so 350° to 10° stays near north."""
    d = df.copy()
    d['_s'] = np.sin(np.radians(d['dir_deg']))
    d['_c'] = np.cos(np.radians(d['dir_deg']))
    a = to_seconds(d, start, end, ['speed_ms', '_s', '_c'])
    ang = np.degrees(np.arctan2(a[:, 2], a[:, 3])) % 360
    return np.column_stack([a[:, 0], a[:, 1], ang])
