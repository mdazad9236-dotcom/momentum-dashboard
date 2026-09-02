/* TradingView chart replacement: stocks + indices only. */
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
    wrap.innerHTML = '<div class="tradingview-widget-container" style="height:100%;width:100%"><div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div></div>';
    const host = wrap.querySelector('.tradingview-widget-container');
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.type = 'text/javascript';
    script.textContent = JSON.stringify({
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
    if (status) status.textContent = 'TradingView · ' + symbol + ' · Interactive chart';
    const hint = document.getElementById('azChartHint');
    if (hint) hint.textContent = 'TradingView chart · drawing tools, indicators, timeframes, volume, zoom and pan are available. X10 levels remain in the decision panel.';
  }

  function install() {
    if (typeof window.openInstrument !== 'function' || window.__azTradingViewInstalled) return;
    const originalOpenInstrument = window.openInstrument;
    window.openInstrument = function (raw) {
      const s = raw || {};
      currentInstrument = s;
      const modal = document.getElementById('azModal');
      if (modal) {
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
      }
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
    window.__azTradingViewOriginalOpenInstrument = originalOpenInstrument;
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
  setTimeout(install, 250);
  setTimeout(install, 1000);
})();
