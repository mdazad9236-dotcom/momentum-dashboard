/* TradingView Advanced Chart: chart-only workspace inside the existing analysis modal. */
(function () {
  function symbolForInstrument(s) {
    const raw = String((s && (s.symbol || s.name)) || '').trim().toUpperCase();
    const name = String((s && s.name) || raw).trim().toUpperCase();
    if (s && s.isIndex) {
      const map = {
        'NIFTY 50': 'NSE:NIFTY',
        'NIFTY': 'NSE:NIFTY',
        'BANK NIFTY': 'NSE:BANKNIFTY',
        'BANKNIFTY': 'NSE:BANKNIFTY',
        'SENSEX': 'BSE:SENSEX',
        'INDIA VIX': 'NSE:INDIAVIX'
      };
      return map[name] || (raw.includes(':') ? raw : 'NSE:' + raw.replace(/[^A-Z0-9]/g, ''));
    }
    const stock = raw.replace(/^NSE:/, '').replace(/[^A-Z0-9_]/g, '');
    return stock ? 'NSE:' + stock : 'NSE:NIFTY';
  }

  function mount(symbol) {
    const wrap = document.getElementById('azChartWrap');
    if (!wrap) return;

    wrap.innerHTML = '';
    const host = document.createElement('div');
    host.className = 'tradingview-widget-container';
    host.style.cssText = 'height:100%;width:100%;min-height:0;';

    const widget = document.createElement('div');
    widget.className = 'tradingview-widget-container__widget';
    widget.style.cssText = 'height:100%;width:100%;min-height:0;';
    host.appendChild(widget);
    wrap.appendChild(host);

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.type = 'text/javascript';
    script.innerHTML = JSON.stringify({
      autosize: true,
      width: '100%',
      height: '100%',
      symbol: symbol,
      interval: 'D',
      timezone: 'exchange',
      theme: 'dark',
      style: '1',
      locale: 'en',
      withdateranges: true,
      hide_side_toolbar: false,
      allow_symbol_change: true,
      show_popup_button: false,
      save_image: false,
      calendar: false,
      support_host: 'https://www.tradingview.com',
      studies: ['Volume@tv-basicstudies']
    });
    host.appendChild(script);

    const status = document.getElementById('azChartStatus');
    if (status) status.textContent = 'TradingView · ' + symbol + ' · Embedded chart';
    const hint = document.getElementById('azChartHint');
    if (hint) hint.textContent = 'Chart tools only: drawing tools, indicators, timeframes, volume, crosshair, zoom, pan and fullscreen. Angel One remains the source for all analysis and X10 decisions.';
  }

  function install() {
    if (window.__azTradingViewInstalled) return true;
    if (typeof window.openInstrument !== 'function') return false;

    const modal = document.getElementById('azModal');
    if (!modal) return false;

    const originalOpenInstrument = window.openInstrument;
    window.__azTradingViewOriginalOpenInstrument = originalOpenInstrument;

    window.openInstrument = function (raw) {
      const instrument = raw || {};
      const symbol = symbolForInstrument(instrument);

      // Preserve the existing Angel One/X10 analysis flow first.
      let result;
      try {
        result = originalOpenInstrument(instrument);
      } catch (err) {
        console.error('Original instrument analysis failed:', err);
      }

      return Promise.resolve(result).then(function () {
        // Keep the existing modal and analysis UI; only replace its chart surface.
        if (!modal.classList.contains('open')) {
          modal.classList.add('open');
          modal.setAttribute('aria-hidden', 'false');
          document.body.style.overflow = 'hidden';
        }

        if (typeof window.switchTab === 'function') window.switchTab('chart');
        mount(symbol);
      });
    };

    window.__azTradingViewInstalled = true;
    return true;
  }

  function boot() {
    if (install()) return;
    setTimeout(install, 100);
    setTimeout(install, 500);
    setTimeout(install, 1200);
    setTimeout(install, 2500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
