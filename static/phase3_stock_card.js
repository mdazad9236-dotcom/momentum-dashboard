// Phase 3 stock opportunity card helpers.
// Loaded by the dashboard to render explicit risk/reward and chart controls.
window.Phase3StockCard = {
  riskReward(entry, stopLoss, target) {
    const e = Number(entry), s = Number(stopLoss), t = Number(target);
    if (![e,s,t].every(Number.isFinite) || e === s) return null;
    const risk = Math.abs(e - s), reward = Math.abs(t - e);
    return { risk, reward, ratio: reward / risk };
  },
  formatRR(entry, stopLoss, target) {
    const rr = this.riskReward(entry, stopLoss, target);
    return rr ? `1:${rr.ratio.toFixed(1)}` : '—';
  },
  chartDefaults() {
    return { timeframe: '1W', intervals: ['1W', '1M'], tools: ['crosshair','horizontal-line','trendline','support-resistance','zoom','reset'] };
  },
  renderChartControls(container, onChange) {
    if (!container) return;
    container.innerHTML = `<div class="phase3-chart-controls" role="group" aria-label="Chart timeframe and tools">
      <button type="button" data-tf="1W" class="active">Weekly</button>
      <button type="button" data-tf="1M">Monthly</button>
      <span class="chart-tools"><button type="button" data-tool="crosshair">Crosshair</button><button type="button" data-tool="trendline">Trendline</button><button type="button" data-tool="horizontal-line">Horizontal</button><button type="button" data-tool="support-resistance">S/R</button><button type="button" data-tool="zoom">Zoom</button></span>
    </div>`;
    container.querySelectorAll('[data-tf]').forEach(btn => btn.addEventListener('click', () => {
      container.querySelectorAll('[data-tf]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      onChange?.({ timeframe: btn.dataset.tf });
    }));
    container.querySelectorAll('[data-tool]').forEach(btn => btn.addEventListener('click', () => onChange?.({ tool: btn.dataset.tool })));
  }
};
