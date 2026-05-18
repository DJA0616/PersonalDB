/**
 * PersonalDB — Embedding Visualization Controller
 * Interactive Plotly scatter with UMAP/t-SNE/PCA, 2D/3D, lasso select,
 * time animation, and semantic search.
 */
(function () {
  'use strict';

  // ── State ──────────────────────────────────────────
  let currentMethod = 'umap';
  let currentDim = 2;
  let currentColorBy = 'sender';
  let allCoords = [];
  let plotDiv = null;

  // ── DOM refs ──────────────────────────────────────
  const $plot = document.getElementById('embedding-plot');
  const $loading = document.getElementById('viz-loading');
  const $error = document.getElementById('viz-error');
  const $errorMsg = document.getElementById('viz-error-msg');
  const $selectionPanel = document.getElementById('selection-panel');
  const $selectionList = document.getElementById('selection-list');
  const $searchInput = document.getElementById('viz-search-input');
  const $searchBtn = document.getElementById('viz-search-btn');
  const $statusText = document.getElementById('viz-status');

  if (!$plot) return; // Not on a page with embedding viz

  // ── API helpers ───────────────────────────────────
  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    return res.json();
  }

  function showLoading() { if ($loading) $loading.style.display = 'flex'; }
  function hideLoading() { if ($loading) $loading.style.display = 'none'; }
  function showError(msg) {
    if ($error && $errorMsg) { $errorMsg.textContent = msg; $error.style.display = 'block'; }
  }
  function hideError() { if ($error) $error.style.display = 'none'; }

  // ── Load initial status ───────────────────────────
  async function loadStatus() {
    try {
      const s = await api('/api/embedding/status');
      if ($statusText) $statusText.textContent = `${s.n_chunks.toLocaleString()} chunks · ${s.methods_available.join('/')}`;
    } catch (e) { /* ignore */ }
  }

  // ── Run reduction & render plot ───────────────────
  async function runReduction(method, dim) {
    hideError();
    showLoading();
    try {
      const data = await api('/api/embedding/reduce', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method, dim }),
      });
      allCoords = data.coords;
      currentMethod = data.method;
      currentDim = data.dim;
      renderPlot();
    } catch (e) {
      showError(e.message);
    } finally {
      hideLoading();
    }
  }

  // ── Render Plotly scatter ─────────────────────────
  function renderPlot() {
    if (!allCoords.length) return;

    const groups = {};
    for (const c of allCoords) {
      let key = c[currentColorBy] || 'unknown';
      if (currentColorBy === 'timestamp' && c.timestamp) {
        const dt = new Date(c.timestamp);
        key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}`;
      }
      if (!groups[key]) groups[key] = [];
      groups[key].push(c);
    }

    const colors = ['#7eb8d4', '#a0d4b0', '#f8f8f8', '#c8c8c8', '#888888', '#e07a5f', '#b5838d', '#81b29a'];
    const groupKeys = Object.keys(groups).sort();
    const colorMap = {};
    groupKeys.forEach((k, i) => { colorMap[k] = colors[i % colors.length]; });

    // Color by timestamp: use continuous Plasma scale
    const isTimeColor = currentColorBy === 'timestamp';

    const traces = [];
    for (const key of groupKeys) {
      const pts = groups[key];
      const trace = {
        x: pts.map(p => p.x),
        y: pts.map(p => p.y),
        mode: 'markers',
        name: key,
        type: currentDim === 3 ? 'scatter3d' : 'scattergl',
        marker: {
          size: 5,
          opacity: 0.85,
          line: { width: 0.3, color: '#333333' },
        },
        text: pts.map(p => `<b>${p.sender || '?'}</b><br>${(p.text || '').substring(0, 120)}`),
        hoverinfo: 'text',
        hovertemplate: '%{text}<extra></extra>',
        customdata: pts.map(p => p.id),
      };

      if (currentDim === 3) {
        trace.z = pts.map(p => p.z || 0);
      }

      if (isTimeColor) {
        const nums = pts.map(p => {
          if (!p.timestamp) return 0;
          const d = new Date(p.timestamp);
          return d.getFullYear() * 12 + d.getMonth();
        });
        trace.marker.color = nums;
        trace.marker.colorscale = 'Plasma';
        trace.marker.colorbar = { title: 'Month', tickfont: { color: '#c8c8c8' } };
        trace.marker.showscale = (key === groupKeys[0]);
        // Delete name to merge into one trace
        if (groupKeys.length > 1) {
          // Multiple traces with time color — keep separate for now
        }
      } else {
        trace.marker.color = colorMap[key];
      }
      traces.push(trace);
    }

    const layout = {
      title: { text: `${currentMethod.toUpperCase()} ${currentDim}D — ${allCoords.length.toLocaleString()} chunks`, font: { color: '#efefef', size: 18 } },
      paper_bgcolor: '#111111',
      plot_bgcolor: '#0a0a0a',
      font: { color: '#c8c8c8' },
      margin: { l: 40, r: 40, t: 60, b: 40 },
      dragmode: 'lasso',
      hoverlabel: { bgcolor: '#1a1a1a', font: { color: '#efefef' } },
      legend: { x: 1.02, y: 1, font: { color: '#c8c8c8' }, bgcolor: 'rgba(17,17,17,0.8)' },
      xaxis: { showgrid: false, zeroline: false, showticklabels: false },
      yaxis: { showgrid: false, zeroline: false, showticklabels: false },
    };

    if (currentDim === 3) {
      layout.scene = {
        xaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
        zaxis: { showgrid: false, zeroline: false, showticklabels: false, title: '' },
        bgcolor: '#0a0a0a',
      };
    }

    const config = {
      displayModeBar: true,
      modeBarButtonsToRemove: ['sendDataToCloud', 'autoScale2d', 'toggleSpikelines'],
      displaylogo: false,
      responsive: true,
    };

    Plotly.react($plot, traces, layout, config);

    // Lasso/box select → show selection panel
    $plot.removeAllListeners && $plot.removeAllListeners('plotly_selected');
    $plot.on('plotly_selected', handleSelection);
  }

  // ── Selection handler ─────────────────────────────
  async function handleSelection(event) {
    if (!event || !event.points || event.points.length === 0) {
      if ($selectionPanel) $selectionPanel.style.display = 'none';
      return;
    }
    const ids = event.points.map(p => p.customdata).filter(id => id != null);
    if (ids.length === 0) return;
    if (ids.length > 50) ids.length = 50; // Cap

    try {
      const data = await api('/api/embedding/selection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
      });
      renderSelection(data.messages);
    } catch (e) {
      showError(e.message);
    }
  }

  function renderSelection(messages) {
    if (!$selectionPanel || !$selectionList) return;
    if (!messages.length) {
      $selectionPanel.style.display = 'none';
      return;
    }
    $selectionPanel.style.display = 'block';
    $selectionList.innerHTML = messages.map(m => `
      <div class="selection-item" style="padding:8px 0;border-bottom:1px solid var(--ds-border, #222);">
        <div class="t-mono" style="font-size:10px;color:var(--ds-accent, #7eb8d4);">${escHtml(m.sender)} · ${m.timestamp ? new Date(m.timestamp).toLocaleDateString() : ''}</div>
        <div class="t-body" style="font-size:13px;margin-top:4px;">${escHtml(m.text)}</div>
      </div>
    `).join('');
  }

  // ── Time animation ────────────────────────────────
  async function loadTimeline() {
    hideError();
    showLoading();
    try {
      const data = await api('/api/embedding/timeline');
      if (!data.frames || !data.frames.length) {
        showError('No timeline data available');
        hideLoading();
        return;
      }

      const traces = [];
      const allFrames = [];
      const sliderSteps = [];

      for (let i = 0; i < data.frames.length; i++) {
        const frame = data.frames[i];
        const visible = i === 0;
        traces.push({
          x: frame.coords.map(c => c.x),
          y: frame.coords.map(c => c.y),
          mode: 'markers',
          type: 'scattergl',
          name: frame.time_label,
          marker: { size: 5, opacity: 0.85, color: '#7eb8d4', line: { width: 0.3, color: '#333333' } },
          text: frame.coords.map(c => `${c.sender}<br>${(c.text || '').substring(0, 100)}`),
          hoverinfo: 'text',
          visible: visible,
        });
        allFrames.push({
          name: frame.time_label,
          data: [{ visible: Array(traces.length).fill(false).map((_, j) => j === i) }],
        });
        sliderSteps.push({
          method: 'animate',
          label: frame.time_label,
          args: [[frame.time_label], { mode: 'immediate', transition: { duration: 300 } }],
        });
      }

      const layout = {
        title: { text: 'Temporal Drift Animation', font: { color: '#efefef', size: 18 } },
        paper_bgcolor: '#111111',
        plot_bgcolor: '#0a0a0a',
        font: { color: '#c8c8c8' },
        xaxis: { showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false },
        updatemenus: [{
          type: 'buttons',
          showactive: false,
          x: 0.1, y: 0,
          buttons: [{
            label: '▶ Play', method: 'animate',
            args: [null, { fromcurrent: true, transition: { duration: 300 }, frame: { duration: 500, redraw: false } }],
          }, {
            label: '⏸ Pause', method: 'animate',
            args: [[null], { mode: 'immediate', transition: { duration: 0 }, frame: { duration: 0, redraw: false } }],
          }],
        }],
        sliders: [{
          active: 0,
          steps: sliderSteps,
          x: 0.1, len: 0.9,
          currentvalue: { prefix: 'Month: ', font: { color: '#c8c8c8' } },
        }],
      };

      Plotly.react($plot, traces, layout, { responsive: true });
    } catch (e) {
      showError(e.message);
    } finally {
      hideLoading();
    }
  }

  // ── Semantic search ───────────────────────────────
  async function runSearch() {
    const phrase = ($searchInput ? $searchInput.value : '').trim();
    if (!phrase) return;
    hideError();
    showLoading();
    try {
      const data = await api('/api/embedding/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phrase }),
      });

      const qx = data.query_coords.x;
      const qy = data.query_coords.y;

      const traces = [{
        x: allCoords.map(c => c.x),
        y: allCoords.map(c => c.y),
        mode: 'markers',
        type: 'scattergl',
        name: 'all chunks',
        marker: { size: 3, color: '#444444', opacity: 0.25 },
        hoverinfo: 'none',
        showlegend: false,
      }, {
        x: data.neighbors.map(n => n.x),
        y: data.neighbors.map(n => n.y),
        mode: 'markers',
        type: 'scattergl',
        name: 'nearest neighbors',
        marker: { size: 10, color: '#7eb8d4', opacity: 0.9, line: { width: 2, color: '#a0d4b0' } },
        text: data.neighbors.map((n, i) => `#${i + 1} ${n.sender}<br>${(n.text || '').substring(0, 120)}<br><i>distance: ${n.distance}</i>`),
        hoverinfo: 'text',
      }, {
        x: [qx],
        y: [qy],
        mode: 'markers',
        type: 'scattergl',
        name: `"${phrase}"`,
        marker: { size: 16, symbol: 'star', color: '#e07a5f', line: { width: 2, color: '#ffffff' } },
        text: [`<b>Query</b>: ${phrase}`],
        hoverinfo: 'text',
      }];

      // Connector lines
      for (const n of data.neighbors) {
        traces.push({
          x: [qx, n.x], y: [qy, n.y],
          mode: 'lines',
          type: 'scattergl',
          line: { color: '#7eb8d4', width: 0.6, dash: 'dot' },
          showlegend: false,
          hoverinfo: 'none',
        });
      }

      Plotly.react($plot, traces, {
        title: { text: `Semantic Field: "${phrase}"`, font: { color: '#efefef', size: 18 } },
        paper_bgcolor: '#111111', plot_bgcolor: '#0a0a0a',
        font: { color: '#c8c8c8' },
        xaxis: { showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false },
        legend: { x: 1.02, y: 1, font: { color: '#c8c8c8' }, bgcolor: 'rgba(17,17,17,0.8)' },
        dragmode: 'pan',
      }, { responsive: true });

      // Show neighbors list below search
      if ($selectionPanel && $selectionList) {
        $selectionPanel.style.display = 'block';
        $selectionList.innerHTML = `<div class="t-label" style="margin-bottom:8px;">Nearest Neighbors</div>` +
          data.neighbors.map((n, i) => `
            <div style="padding:6px 0;border-bottom:1px solid var(--ds-border, #222);">
              <span class="t-accent" style="font-size:11px;">#${i + 1} · d=${n.distance}</span>
              <span class="t-mono" style="font-size:10px;margin-left:8px;">${escHtml(n.sender)}</span>
              <div style="font-size:12px;color:#c8c8c8;margin-top:2px;">${escHtml(n.text.substring(0, 150))}</div>
            </div>
          `).join('');
      }
    } catch (e) {
      showError(e.message);
    } finally {
      hideLoading();
    }
  }

  function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  // ── Button bindings ───────────────────────────────
  document.getElementById('viz-method-umap')?.addEventListener('click', () => runReduction('umap', currentDim));
  document.getElementById('viz-method-tsne')?.addEventListener('click', () => runReduction('tsne', currentDim));
  document.getElementById('viz-method-pca')?.addEventListener('click', () => runReduction('pca', currentDim));
  document.getElementById('viz-dim-2d')?.addEventListener('click', () => runReduction(currentMethod, 2));
  document.getElementById('viz-dim-3d')?.addEventListener('click', () => runReduction(currentMethod, 3));
  document.getElementById('viz-color-by')?.addEventListener('change', function () {
    currentColorBy = this.value;
    if (allCoords.length) renderPlot();
  });
  document.getElementById('viz-timeline-btn')?.addEventListener('click', loadTimeline);
  $searchBtn?.addEventListener('click', runSearch);
  $searchInput?.addEventListener('keydown', function (e) { if (e.key === 'Enter') runSearch(); });
  document.getElementById('viz-error-dismiss')?.addEventListener('click', hideError);

  // ── Init ──────────────────────────────────────────
  loadStatus();
  runReduction('umap', 2);
})();
