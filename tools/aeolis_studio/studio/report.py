"""A short text report of a run or a calibration, meant to be read by a person or pasted into a chat with Claude."""
import json
import os

import pandas as pd

from . import results


def case_report(case_dir, zones, x_range=None):
    meta = json.load(open(os.path.join(case_dir, 'scenario.json')))
    res = results.load(case_dir)
    keys = ['name', 'start', 'end', 'coast_normal_deg', 'wind_height_m', 'd50_mm', 'sediment', 'veg_x_m', 'veg_density',
            'moisture', 'wet_bed_reset', 'method_transport', 'Cb', 'T', 'beach_slope_used', 'dx_m', 'dt_s']
    lines = ['# AeoLiS-körning: %s' % meta.get('name'), '', '## Inställningar', '']
    lines += ['- %s: %s' % (k, meta.get(k)) for k in keys]
    vol = results.zone_volumes(res['x'], res['zb'][0], res['zb'][-1], zones)
    lines += ['', '## Volymändring i modellen (m³/m)', '']
    lines += ['- %s (x %.1f–%.1f m): %.2f' % (k, zones[k][0], zones[k][1], v) for k, v in vol.items()]
    after = os.path.join(case_dir, 'measured_after.csv')
    if os.path.exists(after):
        cmp = results.compare(res, pd.read_csv(after), zones, x_range)
        lines += ['', '## Jämförelse med uppmätt profil', '',
                  '- RMSE bottennivå: %.3f m' % cmp['rmse_m'], '- Medelavvikelse (bias): %.3f m' % cmp['bias_m'],
                  '- Brier skill score: %.2f (1 = perfekt, 0 = inte bättre än ingen förändring)' % cmp['bss'], '',
                  '| Zon | Uppmätt (m³/m) | Modell (m³/m) | Fel (m³/m) |', '| --- | --- | --- | --- |']
        lines += ['| %s | %.2f | %.2f | %.2f |' % (k, v['measured_m3_per_m'], v['model_m3_per_m'], v['error_m3_per_m'])
                  for k, v in cmp['zones'].items()]
    lines += ['', 'Körningens mapp innehåller aeolis.txt och alla indatafiler och kan köras om med `aeolis run aeolis.txt`.']
    return '\n'.join(lines)


def calibration_report(cal_dir, top=10):
    cfg = json.load(open(os.path.join(cal_dir, 'calibration.json')))
    df = pd.read_csv(os.path.join(cal_dir, 'results.csv'))
    lines = ['# Kalibrering', '', '- Mål: %s%s' % (cfg['objective'], ' (zon %s)' % cfg['zone'] if cfg['objective'] == 'volym' else ''),
             '- Antal körningar: %d' % len(df), '- Sökområde: %s' % ', '.join('%s %.3g–%.3g%s' % (k, v[0], v[1], ' (log)' if v[2] else '')
                                                                      for k, v in cfg['space'].items()),
             '- Zoner: %s' % ', '.join('%s %.1f–%.1f m' % (k, *v) for k, v in cfg['zones'].items()), '',
             '## Bästa %d' % min(top, len(df)), '']
    cols = [c for c in df.columns if c not in ('folder', 'ok', 'log')]
    lines.append(df[cols].head(top).round(3).to_markdown(index=False))
    failed = int((~df['ok'].astype(bool)).sum()) if 'ok' in df else 0
    if failed:
        lines += ['', '%d körningar misslyckades.' % failed]
    return '\n'.join(lines)
