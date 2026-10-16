"""Command line for AeoLiS Studio.

  python -m studio bygg   scenario.json  körningar/mitt_case
  python -m studio kor    körningar/mitt_case
  python -m studio jamfor körningar/mitt_case
  python -m studio kalibrera scenario.json körningar/kal --n 24 --mal volym --zon Dyn

scenario.json holds the same settings as the app (see studio/case.py DEFAULTS),
plus "zones": {"Strand": [x0, x1], "Dyn": [x1, x2]}.
"""
import argparse
import json
import sys

from . import calibrate, case, report, run


def _load(path):
    s = json.load(open(path))
    zones = {k: tuple(v) for k, v in s.pop('zones', {}).items()}
    return case.scenario(**s), zones


def _zones_from_case(case_dir, zones):
    if zones:
        return zones
    from . import results
    r = results.load(case_dir)
    return results.default_zones(r['x'], r['zb'][0])


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m studio', description='AeoLiS Studio')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('bygg', help='skapa ett case från scenario.json'); b.add_argument('scenario'); b.add_argument('mapp')
    k = sub.add_parser('kor', help='kör ett case'); k.add_argument('mapp')
    j = sub.add_parser('jamfor', help='rapport och jämförelse mot uppmätt profil'); j.add_argument('mapp')
    j.add_argument('--scenario', help='scenario.json med zoner')
    c = sub.add_parser('kalibrera', help='kalibrera Cb och T mot uppmätt profil')
    c.add_argument('scenario'); c.add_argument('mapp')
    c.add_argument('--n', type=int, default=24); c.add_argument('--mal', default='volym', choices=['volym', 'rmse'])
    c.add_argument('--zon', default='Dyn'); c.add_argument('--workers', type=int, default=2)
    a = ap.parse_args(argv)

    if a.cmd == 'bygg':
        s, _ = _load(a.scenario)
        print(case.build(s, a.mapp))
    elif a.cmd == 'kor':
        ok, tail = run.run(a.mapp, progress=lambda f: print('\r%5.1f %%' % (100 * f), end='', flush=True))
        print('\nKlar' if ok else '\nMisslyckades:\n' + tail)
        return 0 if ok else 1
    elif a.cmd == 'jamfor':
        zones = _load(a.scenario)[1] if a.scenario else {}
        print(report.case_report(a.mapp, _zones_from_case(a.mapp, zones)))
    elif a.cmd == 'kalibrera':
        s, zones = _load(a.scenario)
        if not zones:
            sys.exit('Ange "zones" i scenario.json för kalibrering.')
        calibrate.calibrate(s, calibrate.PARAM_SPACE, a.n, a.mapp, zones, a.mal, a.zon, workers=a.workers,
                            progress=lambda f, r: print('%3.0f %%  Cb %.2f  T %.2f  poäng %s' % (
                                100 * f, r['Cb'], r['T'], '%.3f' % r['score'] if r.get('ok') else 'misslyckad')))
        print(report.calibration_report(a.mapp))
    return 0


if __name__ == '__main__':
    sys.exit(main())
