"""AeoLiS Studio - a Streamlit front end for 1D AeoLiS runs.

Start with:  streamlit run app.py
The app only writes AeoLiS input files, runs the `aeolis` command and plots aeolis.nc.
"""
import io
import json
import os
import shutil
import zipfile
from datetime import datetime, time as dtime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from studio import calibrate, case, ioutil, report, results, run as runner

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get('AEOLIS_STUDIO_PROJECT', os.path.join(HERE, 'projekt'))
INDATA = os.path.join(PROJECT, 'indata')
RUNS = os.path.join(PROJECT, 'korningar')
CALS = os.path.join(PROJECT, 'kalibreringar')
EXAMPLE = os.path.join(HERE, 'exempeldata')
for d in (INDATA, RUNS, CALS):
    os.makedirs(d, exist_ok=True)

BLUE, ORANGE, AQUA, GREY, VIOLET = '#2a78d6', '#eb6834', '#1baf7a', '#8a8984', '#6250d6'
st.set_page_config(page_title='AeoLiS Studio', layout='wide')
ss = st.session_state
if '_pending' in ss:  # values set from another tab, applied before widgets are drawn
    for k, v in ss.pop('_pending').items():
        ss[k] = v


# ---------- helpers ----------
def files(prefix=None, kind=None):
    out = sorted(f for f in os.listdir(INDATA) if f.lower().endswith('.csv'))
    if prefix:
        out = [f for f in out if f.lower().startswith(prefix)]
    return out


def profile_files():
    fs = [f for f in files() if ioutil.date_from_name(f) is not None and f.lower().startswith('profil')]
    return sorted(fs, key=lambda f: ioutil.date_from_name(f))


def save_upload(up):
    with open(os.path.join(INDATA, os.path.basename(up.name)), 'wb') as f:
        f.write(up.getbuffer())


def run_dirs(folder=RUNS):
    ds = [d for d in os.listdir(folder) if os.path.exists(os.path.join(folder, d, 'aeolis.nc'))]
    return sorted(ds, key=lambda d: os.path.getmtime(os.path.join(folder, d)), reverse=True)


def layout(fig, x='x (m), hav → land', y='Bottennivå (m RH2000)', h=420):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), xaxis_title=x, yaxis_title=y,
                      legend=dict(orientation='h', y=1.08, x=0), hovermode='x unified', template='plotly_white')
    return fig


def pick(label, options, key, index=0, none=False):
    opts = (['(ingen)'] if none else []) + options
    if not opts:
        st.info('Inga filer ännu för: %s' % label)
        return None
    # the key includes the option list, so a new upload resets the choice to the best guess
    v = st.selectbox(label, opts, index=min(index, len(opts) - 1), key='%s_%d' % (key, abs(hash(tuple(opts))) % 10 ** 8))
    return None if v == '(ingen)' else v


def path(f):
    return os.path.join(INDATA, f) if f else None


def zones_from_state():
    return {'Strand': (float(ss.get('x_min', 0.0)), float(ss['x_toe'])), 'Dyn': (float(ss['x_toe']), float(ss.get('x_max', 1e9)))}


def current_scenario(**over):
    s = case.scenario(
        name=ss.get('run_name', 'korning'),
        profile_before=path(ss.get('prof_before')), profile_after=path(ss.get('prof_after')),
        start=datetime.combine(ss['start_d'], dtime(0)) if ss.get('start_d') else None,
        end=datetime.combine(ss['end_d'], dtime(0)) if ss.get('end_d') else None,
        wind=path(ss.get('wind_f')), waterlevel=path(ss.get('wl_f')), waves=path(ss.get('wave_f')),
        sediment=path(ss.get('sed_f')) if ss.get('sed_mode') == 'Klasser från fil' else None,
        constant_hs_m=ss.get('hs_const', 0.3), constant_tp_s=ss.get('tp_const', 5.0),
        wind_height_m=ss.get('wind_h', 10.0), coast_normal_deg=ss.get('coast', 270.0),
        dx_m=ss.get('dx', 0.5), d50_mm=ss.get('d50', 0.3),
        veg_x_m=ss.get('veg_x') if ss.get('veg_on', True) else None, veg_density=ss.get('veg_rho', 0.3),
        moisture=ss.get('moist', True), wet_bed_reset=ss.get('wbr', False), avalanche=ss.get('aval', True),
        method_transport=ss.get('method', 'bagnold'), Cb=ss.get('Cb', 1.5), T=ss.get('T', 1.0),
        beach_slope=None if ss.get('slope_auto', True) else ss.get('slope', 0.05),
        dt_s=int(ss.get('dt', 3600)), output_s=int(ss.get('out_h', 6) * 3600))
    s.update(over)
    return s


def zip_folder(folder):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, fs in os.walk(folder):
            for f in fs:
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, os.path.dirname(folder)))
    return buf.getvalue()


# ---------- page ----------
st.title('AeoLiS Studio')
st.caption('Bygger indata till AeoLiS, kör modellen och jämför med mätningar. Modellkoden ändras inte. '
           'Tider i UTC, höjder i RH2000. Projektmapp: `%s`' % PROJECT)

tabs = st.tabs(['1 · Indata', '2 · Inställningar', '3 · Kör', '4 · Resultat', '5 · Kalibrera', '6 · Jämför scenarier'])

# ===== 1 Indata =====
with tabs[0]:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader('Ladda upp filer')
        ups = st.file_uploader('CSV-filer (profil_ÅÅÅÅ-MM-DD.csv, vind, vattenstånd, vågor, sediment)', type='csv',
                               accept_multiple_files=True)
        if ups:
            for u in ups:
                save_upload(u)
            st.success('Sparade %d fil(er) i projektmappen.' % len(ups))
        if st.button('Använd exempeldata (Europlatform 2012, syntetisk profil)'):
            for f in os.listdir(EXAMPLE):
                if f.endswith('.csv'):
                    shutil.copy(os.path.join(EXAMPLE, f), INDATA)
            st.rerun()
        with st.expander('Filformat'):
            st.markdown("""
| Fil | Kolumner | Kommentar |
| --- | --- | --- |
| `profil_2023-04-12.csv` | `x_m, z_m` | Mätdatum i filnamnet. x från fast referenspunkt, ökande mot land |
| vind | `time_utc, speed_ms, dir_deg` | Riktning varifrån vinden blåser, 0 = nord |
| vattenstånd | `time_utc, wl_m` | RH2000 |
| vågor (valfri) | `time_utc, hs_m, tp_s` | |
| sediment (valfri) | `d_mm, mass_pct` | Kornklasser och massprocent |

Tid som `2023-04-12T13:00`. Komma eller semikolon som avgränsare går bra.""")
    with c2:
        st.subheader('Välj filer')
        pf = profile_files()
        others = files()
        ss.prof_before = pick('Profil före (start)', pf, 'pb')
        later = [f for f in pf if ss.prof_before and ioutil.date_from_name(f) > ioutil.date_from_name(ss.prof_before)]
        ss.prof_after = pick('Profil efter (för jämförelse och kalibrering)', later, 'pa', index=1, none=True)
        guess = lambda key: next((i for i, f in enumerate(others) if key in f.lower()), -1)
        ss.wind_f = pick('Vind', others, 'wf', max(guess('vind'), 0))
        ss.wl_f = pick('Vattenstånd', others, 'wlf', max(guess('vatten'), 0))
        ss.wave_f = pick('Vågor', others, 'wvf', guess('vag') + 1, none=True)
        ss.sed_f = pick('Sediment', others, 'sf', guess('sediment') + 1, none=True)

    if ss.get('prof_before'):
        fig = go.Figure()
        b, db = ioutil.read_profile(path(ss.prof_before))
        fig.add_scatter(x=b['x_m'], y=b['z_m'], name='Före %s' % db.date(), line=dict(color=GREY, dash='dash'))
        if ss.get('prof_after'):
            a, da = ioutil.read_profile(path(ss.prof_after))
            fig.add_scatter(x=a['x_m'], y=a['z_m'], name='Efter %s' % da.date(), line=dict(color=BLUE))
        st.plotly_chart(layout(fig, h=340), width='stretch')
    cc = st.columns(2)
    try:
        if ss.get('wind_f'):
            w = ioutil.read_wind(path(ss.wind_f))
            fig = go.Figure(go.Scatter(x=w['time_utc'], y=w['speed_ms'], line=dict(color=GREY, width=1), name='Vind'))
            cc[0].plotly_chart(layout(fig, 'Tid (UTC)', 'Vind (m/s)', 260), width='stretch')
            bins = np.arange(0, 361, 30)
            sect = pd.cut(w['dir_deg'] % 360, bins, right=False, labels=bins[:-1] + 15)
            rose = w.assign(sect=sect, strong=w['speed_ms'] >= 8).groupby('sect', observed=False)
            fig = go.Figure()
            fig.add_barpolar(r=rose.size() / len(w) * 100, theta=rose.size().index.astype(float), name='Alla', marker_color=GREY)
            fig.add_barpolar(r=rose['strong'].sum() / len(w) * 100, theta=rose.size().index.astype(float), name='≥ 8 m/s', marker_color=BLUE)
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), polar=dict(angularaxis=dict(direction='clockwise', rotation=90)),
                              title='Vindros (andel av tiden, %)', template='plotly_white')
            cc[1].plotly_chart(fig, width='stretch')
        if ss.get('wl_f'):
            wl = ioutil.read_waterlevel(path(ss.wl_f))
            fig = go.Figure(go.Scatter(x=wl['time_utc'], y=wl['wl_m'], line=dict(color=BLUE, width=1)))
            cc[0].plotly_chart(layout(fig, 'Tid (UTC)', 'Vattenstånd (m RH2000)', 240), width='stretch')
        if ss.get('sed_f'):
            sd = ioutil.read_sediment(path(ss.sed_f))
            fig = go.Figure(go.Bar(x=sd['d_mm'].astype(str), y=sd['mass_pct'], marker_color=ORANGE))
            cc[1].plotly_chart(layout(fig, 'Kornklass (mm)', 'Massprocent', 240), width='stretch')
    except Exception as e:
        st.error('Kunde inte läsa en fil: %s' % e)

# ===== 2 Settings =====
with tabs[1]:
    if not ss.get('prof_before'):
        st.info('Välj först en startprofil under Indata.')
    else:
        b, db = ioutil.read_profile(path(ss.prof_before))
        ss.x_min, ss.x_max = float(b['x_m'].min()), float(b['x_m'].max())
        da = ioutil.date_from_name(ss.prof_after) if ss.get('prof_after') else None
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader('Period och plats')
            st.text_input('Namn på körningen', 'korning', key='run_name')
            st.date_input('Start', db.date(), key='start_d')
            st.date_input('Slut', (da or db + pd.Timedelta(days=30)).date(), key='end_d')
            st.number_input('Kustnormal, riktning som pålandsvind kommer från (°, 0 = nord)', 0.0, 360.0, 270.0, 1.0, key='coast',
                            help='En västvänd kust har 270°. Används för att vrida vinden mot profilen.')
            st.number_input('Vindens mäthöjd (m)', 1.0, 100.0, 10.0, 0.5, key='wind_h')
        with c2:
            st.subheader('Sediment och vegetation')
            st.radio('Sediment', ['d50', 'Klasser från fil'], key='sed_mode', horizontal=True,
                     disabled=not ss.get('sed_f'))
            if ss.get('sed_mode') != 'Klasser från fil':
                st.number_input('d50 (mm)', 0.05, 5.0, 0.3, 0.01, key='d50')
            st.checkbox('Vegetation på dynen', True, key='veg_on')
            if ss.veg_on:
                guess_toe = float(b['x_m'][np.argmax(b['z_m'].to_numpy() >= 3.0)]) if (b['z_m'] >= 3).any() else ss.x_min
                st.number_input('Vegetation från x (m)', ss.x_min, ss.x_max, guess_toe, 0.5, key='veg_x')
                st.slider('Täckningsgrad (0–1)', 0.0, 1.0, 0.3, 0.05, key='veg_rho')
            st.subheader('Zoner för volymer')
            st.number_input('Gräns strand / dyn, x (m)', ss.x_min, ss.x_max,
                            float(ss.get('veg_x', (ss.x_min + ss.x_max) / 2)), 0.5, key='x_toe')
        with c3:
            st.subheader('Processer och modell')
            st.checkbox('Fukt (process_moist, th_moisture)', True, key='moist')
            st.checkbox('Återställ våt bädd (process_wet_bed_reset)', False, key='wbr',
                        help='Där vattnet når upp dras bottnen tillbaka mot startprofilen. Förhindrar att strandplanet grävs ur.')
            st.checkbox('Lavinering', True, key='aval')
            st.selectbox('Transportformel', ['bagnold', 'kawamura', 'lettau', 'dk', 'sauermann', 'vanrijn_strypsteen'], key='method')
            st.number_input('Cb', 0.1, 10.0, 1.5, 0.1, key='Cb')
            st.number_input('T, anpassningstid (s)', 0.05, 60.0, 1.0, 0.25, key='T')
            if not ss.get('wave_f'):
                st.number_input('Konstant Hs utan vågfil (m)', 0.0, 5.0, 0.3, 0.1, key='hs_const')
                st.number_input('Konstant Tp utan vågfil (s)', 1.0, 20.0, 5.0, 0.5, key='tp_const')
            st.checkbox('Strandlutning för uppspolning från profilen', True, key='slope_auto')
            if not ss.slope_auto:
                st.number_input('Strandlutning (−)', 0.005, 0.5, 0.05, 0.005, key='slope')
            with st.expander('Numerik'):
                st.number_input('dx (m)', 0.1, 5.0, 0.5, 0.1, key='dx')
                st.number_input('Tidssteg dt (s)', 60, 3600, 3600, 60, key='dt')
                st.number_input('Utskrift var (timmar)', 1, 48, 6, 1, key='out_h')

# ===== 3 Run =====
with tabs[2]:
    if not (ss.get('prof_before') and ss.get('wind_f') and ss.get('wl_f') and ss.get('x_toe') is not None):
        st.info('Välj indata och gå igenom Inställningar först.')
    else:
        s = current_scenario()
        st.write('Period **%s** till **%s**, transportformel **%s**, Cb **%.2f**, T **%.2f s**, fukt **%s**.' %
                 (ss.start_d, ss.end_d, s['method_transport'], s['Cb'], s['T'], 'på' if s['moisture'] else 'av'))
        if st.button('Kör modellen', type='primary'):
            folder = os.path.join(RUNS, '%s_%s' % (s['name'], datetime.now().strftime('%Y%m%d_%H%M%S')))
            try:
                case.build(s, folder)
                bar = st.progress(0.0, 'Kör AeoLiS…')
                ok, tail = runner.run(folder, progress=lambda f: bar.progress(f, 'Kör AeoLiS… %d %%' % (100 * f)))
                if ok:
                    json.dump({k: list(v) for k, v in zones_from_state().items()}, open(os.path.join(folder, 'zones.json'), 'w'))
                    ss.last_run = os.path.basename(folder)
                    st.success('Klar: %s. Se fliken Resultat.' % ss.last_run)
                else:
                    st.error('Körningen misslyckades.')
                    st.code(tail)
            except Exception as e:
                st.error(str(e))

# ===== 4 Results =====
with tabs[3]:
    rd = run_dirs()
    if not rd:
        st.info('Inga körningar ännu.')
    else:
        sel = st.selectbox('Körning', rd, index=rd.index(ss['last_run']) if ss.get('last_run') in rd else 0)
        folder = os.path.join(RUNS, sel)
        res = results.load(folder)
        zf = os.path.join(folder, 'zones.json')
        zones = {k: tuple(v) for k, v in json.load(open(zf)).items()} if os.path.exists(zf) else results.default_zones(res['x'], res['zb'][0])
        x = res['x']
        i = st.slider('Tidpunkt', 0, len(res['time']) - 1, len(res['time']) - 1, format='%d')
        st.caption(str(res['time'][i]))
        fig = go.Figure()
        fig.add_scatter(x=x, y=res['zb'][0], name='Start', line=dict(color=GREY, dash='dash'))
        if res['zs'] is not None:
            fig.add_scatter(x=x, y=np.where(res['zs'][i] > res['zb'][i] + 1e-3, res['zs'][i], np.nan), name='Vatten', line=dict(color=AQUA, width=1))
        fig.add_scatter(x=x, y=res['zb'][i], name='Modell', line=dict(color=BLUE, width=3))
        after = os.path.join(folder, 'measured_after.csv')
        if os.path.exists(after):
            m = pd.read_csv(after)
            fig.add_scatter(x=m['x_m'], y=m['z_m'], name='Uppmätt efter', mode='markers', marker=dict(color=ORANGE, size=5))
        for k, (a, _) in zones.items():
            if a > x.min():
                fig.add_vline(x=a, line=dict(color=GREY, width=1, dash='dot'))
        st.plotly_chart(layout(fig), width='stretch')
        c1, c2 = st.columns(2)
        vs = results.volume_series(res, zones)
        fig = go.Figure()
        for k, col in zip(vs.columns, [ORANGE, BLUE, AQUA, VIOLET]):
            fig.add_scatter(x=vs.index, y=vs[k], name=k, line=dict(color=col, width=2))
        c1.plotly_chart(layout(fig, 'Tid (UTC)', 'Volymändring (m³/m)', 320), width='stretch')
        if res['qs'] is not None:
            fig = go.Figure(go.Scatter(x=x, y=res['qs'][i] * 1000, line=dict(color=BLUE)))
            c2.plotly_chart(layout(fig, 'x (m)', 'Transport qs (g/m/s)', 320), width='stretch')
        if os.path.exists(after):
            cmp = results.compare(res, pd.read_csv(after), zones)
            st.subheader('Jämförelse med uppmätt profil')
            m1, m2, m3 = st.columns(3)
            m1.metric('RMSE bottennivå', '%.3f m' % cmp['rmse_m'])
            m2.metric('Bias', '%.3f m' % cmp['bias_m'])
            m3.metric('Brier skill score', '%.2f' % cmp['bss'], help='1 = perfekt, 0 = inte bättre än att anta ingen förändring')
            st.dataframe(pd.DataFrame(cmp['zones']).T.rename(columns={'measured_m3_per_m': 'Uppmätt (m³/m)', 'model_m3_per_m': 'Modell (m³/m)',
                                                                      'error_m3_per_m': 'Fel (m³/m)'}).round(2))
        rep = report.case_report(folder, zones)
        d1, d2 = st.columns(2)
        d1.download_button('Ladda ner rapport (.md, för Claude)', rep, file_name='%s_rapport.md' % sel)
        d2.download_button('Ladda ner körningens mapp (.zip)', zip_folder(folder), file_name='%s.zip' % sel)

# ===== 5 Calibrate =====
with tabs[4]:
    if not ss.get('prof_after'):
        st.info('Kalibrering kräver en uppmätt profil efter. Välj den under Indata.')
    elif ss.get('x_toe') is None:
        st.info('Gå igenom Inställningar först.')
    else:
        st.write('Varje prov är en fullständig AeoLiS-körning med samma indata som under Inställningar, där bara de valda parametrarna varierar. '
                 'Proven väljs med Latin hypercube.')
        c1, c2, c3 = st.columns(3)
        cb = c1.slider('Cb, intervall', 0.2, 6.0, (1.0, 3.0), 0.1)
        tt = c1.slider('T, intervall (s, logaritmiskt)', 0.1, 30.0, (0.5, 10.0), 0.1)
        n = c2.number_input('Antal körningar', 4, 200, 24, 4)
        workers = c2.number_input('Körningar samtidigt', 1, max(1, os.cpu_count() or 1), min(2, os.cpu_count() or 1))
        obj = c3.radio('Mål', ['volym', 'rmse'], format_func=lambda v: {'volym': 'Fel i volym för en zon', 'rmse': 'RMSE i profil'}[v])
        zone = c3.selectbox('Zon', list(zones_from_state()), index=1, disabled=obj != 'volym')
        space = {'Cb': (cb[0], cb[1], False), 'T': (tt[0], tt[1], True)}

        def do_cal(space, n, tag):
            folder = os.path.join(CALS, '%s_%s_%s' % (ss.get('run_name', 'kal'), tag, datetime.now().strftime('%Y%m%d_%H%M%S')))
            bar = st.progress(0.0, 'Kalibrerar…')
            df = calibrate.calibrate(current_scenario(), space, int(n), folder, zones_from_state(), obj, zone, workers=int(workers),
                                     progress=lambda f, r: bar.progress(f, 'Kalibrerar… %d %%' % (100 * f)))
            ss.last_cal, ss.last_space = folder, space
            return df

        b1, b2 = st.columns(2)
        if b1.button('Starta kalibrering', type='primary'):
            do_cal(space, n, 'r1')
        if ss.get('last_cal') and b2.button('Förfina runt de 5 bästa'):
            prev = pd.read_csv(os.path.join(ss.last_cal, 'results.csv'))
            do_cal(calibrate.narrowed_space(prev, ss.last_space), n, 'r2')

        cals = sorted([d for d in os.listdir(CALS) if os.path.exists(os.path.join(CALS, d, 'results.csv'))], reverse=True)
        if cals:
            pick_cal = st.selectbox('Kalibrering att visa', cals, index=cals.index(os.path.basename(ss['last_cal'])) if ss.get('last_cal') and os.path.basename(ss['last_cal']) in cals else 0)
            cdir = os.path.join(CALS, pick_cal)
            df = pd.read_csv(os.path.join(cdir, 'results.csv'))
            ok = df[df['ok'].astype(bool)]
            g1, g2 = st.columns([1, 1])
            fig = go.Figure(go.Scatter(x=ok['Cb'], y=ok['T'], mode='markers', name='Prov', marker=dict(size=11, color=ok['score'], colorscale='Blues_r',
                                       showscale=True, colorbar=dict(title='Poäng')), text=ok['score'].round(3)))
            if len(ok):
                fig.add_scatter(x=[ok['Cb'].iloc[0]], y=[ok['T'].iloc[0]], mode='markers', marker=dict(size=18, color='rgba(0,0,0,0)',
                                line=dict(color=ORANGE, width=3)), name='Bäst')
            fig.update_yaxes(type='log')
            g1.plotly_chart(layout(fig, 'Cb', 'T (s)', 380), width='stretch')
            if len(ok):
                best = results.load(ok['folder'].iloc[0])
                m = pd.read_csv(os.path.join(ok['folder'].iloc[0], 'measured_after.csv'))
                fig = go.Figure()
                fig.add_scatter(x=best['x'], y=best['zb'][0], name='Start', line=dict(color=GREY, dash='dash'))
                fig.add_scatter(x=best['x'], y=best['zb'][-1], name='Bästa modell', line=dict(color=BLUE, width=3))
                fig.add_scatter(x=m['x_m'], y=m['z_m'], name='Uppmätt', mode='markers', marker=dict(color=ORANGE, size=5))
                g2.plotly_chart(layout(fig, h=380), width='stretch')
            show = [c for c in df.columns if c not in ('folder', 'ok', 'log')]
            st.dataframe(df[show].round(3), width='stretch')
            st.caption('Ligger flera kombinationer nära varandra i poäng men långt ifrån varandra i Cb och T kompenserar parametrarna varandra. '
                       'Kontrollera då mot en andra mätperiod innan du väljer värden.')
            if len(ok) and st.button('Använd bästa Cb och T i Inställningar'):
                ss._pending = {'Cb': round(float(ok['Cb'].iloc[0]), 3), 'T': round(float(ok['T'].iloc[0]), 3)}
                st.rerun()
            st.download_button('Ladda ner kalibreringsrapport (.md, för Claude)', report.calibration_report(cdir), file_name='%s.md' % pick_cal)

# ===== 6 Compare scenarios =====
with tabs[5]:
    rd = run_dirs()
    chosen = st.multiselect('Körningar att jämföra', rd, default=rd[:2])
    if chosen:
        fig = go.Figure()
        rows = []
        cols = [BLUE, ORANGE, AQUA, VIOLET, GREY]
        first = results.load(os.path.join(RUNS, chosen[0]))
        fig.add_scatter(x=first['x'], y=first['zb'][0], name='Start (%s)' % chosen[0], line=dict(color=GREY, dash='dash'))
        vfig = go.Figure()
        for n_, (r_, col) in enumerate(zip(chosen, cols * 5)):
            folder = os.path.join(RUNS, r_)
            res = results.load(folder)
            zf = os.path.join(folder, 'zones.json')
            zones = {k: tuple(v) for k, v in json.load(open(zf)).items()} if os.path.exists(zf) else results.default_zones(res['x'], res['zb'][0])
            fig.add_scatter(x=res['x'], y=res['zb'][-1], name=r_, line=dict(color=col, width=2.5))
            vs = results.volume_series(res, zones)
            if 'Dyn' in vs:
                vfig.add_scatter(x=vs.index, y=vs['Dyn'], name=r_, line=dict(color=col, width=2))
            meta = res['meta']
            days = (pd.Timestamp(meta['end']) - pd.Timestamp(meta['start'])).days
            row = {'Körning': r_, 'Dygn': days, 'Cb': meta['Cb'], 'T': meta['T'], 'Fukt': meta['moisture']}
            for k, v in results.zone_volumes(res['x'], res['zb'][0], res['zb'][-1], zones).items():
                row['%s (m³/m)' % k] = round(v, 2)
                row['%s per år (m³/m/år)' % k] = round(v * 365.25 / days, 2) if days else None
            rows.append(row)
        st.plotly_chart(layout(fig), width='stretch')
        st.plotly_chart(layout(vfig, 'Tid (UTC)', 'Volymändring dyn (m³/m)', 320), width='stretch')
        st.dataframe(pd.DataFrame(rows), width='stretch')
