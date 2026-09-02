/* TradingView Advanced Chart: embedded inside the existing analysis modal for stocks + indices. */
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
    host.style.cssText = 'height:100%;width:100%;';

    const widget = document.createElement('div');
    widget.className = 'tradingview-widget-container__widget';
    widget.style.cssText = 'height:100%;width:100%;';
    host.appendChild(widget);
    wrap.appendChild(host);

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.type = 'text/javascript';
    script.text = JSON.stringify({
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
      save_image: false,
      calendar: false,
      support_host: 'https://www.tradingview.com',
      studies: ['Volume@tv-basicstudies']
    });
    host.appendChild(script);

    const status = document.getElementById('azChartStatus');
    if (status) status.textContent = 'TradingView · ' + symbol + ' · Embedded';
    const hint = document.getElementById('azChartHint');
    if (hint) hint.textContent = 'Embedded TradingView Advanced Chart · drawing tools, indicators, timeframes, volume, zoom and pan are available. X10 levels remain in the decision panel.';
  }

  function install() {
    if (window.__azTradingViewInstalled) return true;
    if (typeof window.openInstrument !== 'function') return false;

    const modal = document.getElementById('azModal');
    if (!modal) return false;

    window.__azTradingViewOriginalOpenInstrument = window.openInstrument;
    window.openInstrument = function (raw) {
      const s = raw || {};
      window.currentInstrument = s;

      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';

      const title = document.getElementById('azTitle');
      const subtitle = document.getElementById('azSubtitle');
      if (title) title.textContent = s.name || s.symbol || 'Market Instrument';
      if (subtitle) subtitle.textContent = (s.symbol || s.name || '') + ' · TradingView' + (s.isIndex ? ' · INDEX' : ' · X10');

      if (typeof window.renderDNA === 'function') window.renderDNA(s);
      if (typeof window.renderTrade === 'function') window.renderTrade(s);
      if (typeof window.switchTab === 'function') window.switchTab('chart');

      mount(symbolForInstrument(s));
      return Promise.resolve();
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
