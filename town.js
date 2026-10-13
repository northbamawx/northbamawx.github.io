// Plain-English rain timing for the next 12 hours from NWS hourly periods.
window.rainTiming = function (periods) {
  const hrs = (periods || []).filter(h => new Date(h.endTime) > Date.now()).slice(0, 12).map(h => ({
    t: new Date(h.startTime), pop: (h.probabilityOfPrecipitation && h.probabilityOfPrecipitation.value) || 0, storm: /thunder/i.test(h.shortForecast) }));
  if (!hrs.length) return '';
  const at = d => d.toLocaleTimeString('en-US', { hour: 'numeric' });
  const max = Math.max(...hrs.map(h => h.pop));
  if (max < 20) return 'No rain expected in the next 12 hours.';
  const peak = hrs.find(h => h.pop === max);
  if (max < 40) return `Small chance of a shower (${max}%), best chance around ${at(peak.t)}.`;
  const s = hrs.findIndex(h => h.pop >= 40);
  let e = s; while (e + 1 < hrs.length && hrs[e + 1].pop >= 40) e++;
  const storm = hrs.slice(s, e + 1).some(h => h.storm);
  const what = (storm ? 'Storms' : 'Rain') + (max >= 60 ? ' likely' : ' possible');
  const end = e + 1 < hrs.length ? `, ending around ${at(new Date(hrs[e].t.getTime() + 3600000))}` : ', lasting past the next 12 hours';
  return s === 0 ? `${what} now${end} (up to ${max}%).` : `${what} starting around ${at(hrs[s].t)}${end} (up to ${max}%).`;
};

// Shared script for the town pages (towns/*.html). Each page sets
// data-name, data-lat and data-lon on <body>.
(() => {
  const { name, lat, lon } = document.body.dataset;
  const NWS = { headers: { Accept: 'application/geo+json' } };
  const $ = id => document.getElementById(id);
  const f = c => Math.round(c * 9 / 5 + 32);

  // Same colors the stream and home page use (keep in sync with index.html alertColor).
  function alertColor(ev) {
    const e = ev.toLowerCase();
    if (e.includes('tornado')) return e.includes('watch') ? '#FF8C00' : '#FF2B2B';
    if (e.includes('extreme wind')) return '#E65C19';
    if (e.includes('severe thunderstorm')) return e.includes('watch') ? '#FFD700' : '#FFA500';
    if (e.includes('flash flood') || e.includes('flood warning')) return '#22e05a';
    if (e.includes('flood')) return '#2E8B57';
    if (e.includes('wind advisory')) return '#DA70D6';
    if (e.includes('winter')) return '#7B68EE';
    if (e.includes('heat')) return '#FF7E00';
    if (e.includes('freeze') || e.includes('frost')) return '#99CCEE';
    return '#8a99ad';
  }
  const rank = ev => /emergency/i.test(ev) ? 0 : /^tornado warning/i.test(ev) ? 1 : /warning/i.test(ev) ? 2 : /watch/i.test(ev) ? 3 : 4;

  async function loadAlerts() {
    const box = $('t-alerts');
    try {
      const d = await (await fetch(`https://api.weather.gov/alerts/active?point=${lat},${lon}`, NWS)).json();
      const list = (d.features || []).map(x => x.properties).filter(p => p.messageType !== 'Cancel').sort((a, b) => rank(a.event) - rank(b.event));
      box.textContent = '';
      if (!list.length) {
        const p = document.createElement('p'); p.className = 'ok'; p.textContent = `No warnings, watches or advisories for ${name} right now.`;
        box.append(p); return;
      }
      list.forEach(p => {
        const el = document.createElement('details'); el.className = 'alert'; el.style.setProperty('--k', alertColor(p.event));
        const s = document.createElement('summary');
        const b = document.createElement('b'); b.textContent = p.event;
        const t = document.createElement('small'); t.textContent = 'Until ' + new Date(p.ends || p.expires).toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' });
        s.append(b, t);
        const body = document.createElement('p'); body.textContent = (p.description || '').replace(/\s*\n\s*/g, ' ');
        el.append(s, body); box.append(el);
      });
    } catch (e) { box.innerHTML = '<p>Alerts are unavailable right now.</p>'; }
  }

  let pt = null;
  async function point() {
    if (!pt) pt = (await (await fetch(`https://api.weather.gov/points/${lat},${lon}`, NWS)).json()).properties;
    return pt;
  }

  async function loadNow() {
    try {
      const p = await point();
      // Nearest station first, but skip ones that are down or reporting stale/empty data.
      const sts = (await (await fetch(p.observationStations, NWS)).json()).features.slice(0, 4);
      let st = null, o = null;
      for (const s of sts) {
        try {
          const r = await fetch(s.id + '/observations/latest', NWS);
          if (!r.ok) continue;
          const ob = (await r.json()).properties;
          if (!ob || ob.temperature?.value == null || Date.now() - new Date(ob.timestamp) > 3 * 3600000) continue;
          st = s; o = ob; break;
        } catch (e) {}
      }
      if (!o) throw new Error('no station');
      const t = o.temperature && o.temperature.value;
      if (t != null) $('t-temp').textContent = f(t) + '°';
      $('t-desc').textContent = o.textDescription || '';
      const ws = o.windSpeed && o.windSpeed.value;
      $('t-wind').textContent = ws == null ? '--' : ws < 1 ? 'Calm' : Math.round(ws * 0.621371) + ' mph';
      const rh = o.relativeHumidity && o.relativeHumidity.value;
      $('t-rh').textContent = rh == null ? '--' : Math.round(rh) + '%';
      const fl = (o.heatIndex && o.heatIndex.value) ?? (o.windChill && o.windChill.value) ?? t;
      $('t-feel').textContent = fl == null ? '--' : f(fl) + '°';
      $('t-station').textContent = st.properties.name;
    } catch (e) { $('t-desc').textContent = 'Current conditions unavailable'; }
  }

  async function loadForecast() {
    const box = $('t-fc');
    try {
      const p = await point();
      const [fc, hr] = await Promise.all([fetch(p.forecast, NWS).then(r => r.json()), fetch(p.forecastHourly, NWS).then(r => r.json())]);
      $('t-rain').textContent = window.rainTiming ? window.rainTiming(hr.properties.periods) : '';
      box.textContent = '';
      fc.properties.periods.slice(0, 14).forEach(d => {
        const el = document.createElement('div'); el.className = 'fcd' + (d.isDaytime ? '' : ' night');
        const n = document.createElement('div'); n.className = 'n'; n.textContent = d.name;
        const img = document.createElement('img'); img.src = d.icon; img.alt = ''; img.width = 56; img.height = 56; img.loading = 'lazy';
        const t = document.createElement('div'); t.className = 't'; t.textContent = d.temperature + '°';
        const s = document.createElement('div'); s.className = 's'; s.textContent = d.shortForecast;
        const pop = d.probabilityOfPrecipitation && d.probabilityOfPrecipitation.value;
        if (pop) { const r = document.createElement('div'); r.className = 'pop'; r.textContent = pop + '% rain'; el.append(n, img, t, s, r); }
        else el.append(n, img, t, s);
        el.title = d.detailedForecast;
        box.append(el);
      });
    } catch (e) { box.innerHTML = '<p>Forecast unavailable right now.</p>'; }
  }

  function initRadar() {
    if (!window.L) return;
    const map = L.map('t-radar', { scrollWheelZoom: false, zoomSnap: 0.5 }).setView([+lat, +lon], 9);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      maxNativeZoom: 16, attribution: 'Esri | Radar: Iowa Environmental Mesonet' }).addTo(map);
    map.createPane('labels'); map.getPane('labels').style.zIndex = 650; map.getPane('labels').style.pointerEvents = 'none';
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', { pane: 'labels' }).addTo(map);
    let radar = null;
    const refresh = () => {
      const next = L.tileLayer(`https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png?${Math.floor(Date.now() / 300000)}`, { opacity: 0.75 }).addTo(map);
      if (radar) setTimeout(((old) => () => map.removeLayer(old))(radar), 1500);
      radar = next;
    };
    refresh(); setInterval(refresh, 300000);
    L.circleMarker([+lat, +lon], { radius: 6, color: '#33d6ff', weight: 2, fillOpacity: 0.4 }).addTo(map).bindTooltip(name);
  }

  // Share
  const shareBtn = $('t-share');
  if (shareBtn) shareBtn.addEventListener('click', async () => {
    const data = { title: document.title, text: `Live radar, alerts and forecast for ${name}`, url: location.href };
    if (navigator.share) { try { await navigator.share(data); } catch (e) {} }
    else { $('t-share-links').hidden = false; }
  });

  loadAlerts(); loadNow(); loadForecast();
  const io = new IntersectionObserver((en, o) => { if (en.some(e => e.isIntersecting)) { o.disconnect(); initRadar(); } }, { rootMargin: '400px' });
  io.observe($('t-radar'));
  setInterval(loadAlerts, 120000); setInterval(loadNow, 600000); setInterval(loadForecast, 1800000);
})();
