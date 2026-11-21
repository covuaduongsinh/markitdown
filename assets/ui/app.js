(function(){
  window.MID_PIECES = __MID_PIECES__;
  var MOON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  var SUN = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F6B92B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.2" y1="4.2" x2="5.6" y2="5.6"/><line x1="18.4" y1="18.4" x2="19.8" y2="19.8"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.2" y1="19.8" x2="5.6" y2="18.4"/><line x1="18.4" y1="5.6" x2="19.8" y2="4.2"/></svg>';

  function setThemeBtn(){
    var dark = document.body.getAttribute('data-mid-theme') === 'dark';
    var want = dark ? 'sun' : 'moon';
    document.querySelectorAll('[data-mid-theme-icon]').forEach(function(el){
      if (el.getAttribute('data-mid-icon') !== want){ el.innerHTML = dark ? SUN : MOON; el.setAttribute('data-mid-icon', want); }
    });
    var label = dark ? 'Sáng' : 'Tối';
    document.querySelectorAll('[data-mid-theme-label]').forEach(function(el){ if (el.textContent !== label) el.textContent = label; });
  }
  window.midToggleTheme = function(){
    var b = document.body, dark = b.getAttribute('data-mid-theme') === 'dark';
    var next = dark ? 'light' : 'dark';
    b.setAttribute('data-mid-theme', next);
    try { localStorage.setItem('mid-theme', next); } catch(e){}
    setThemeBtn();
  };
  window.midSelectMode = function(idx){
    document.querySelectorAll('[data-mid-mode]').forEach(function(el){ el.classList.toggle('active', (+el.dataset.midMode) === idx); });
    var rs = document.querySelectorAll('#mid-mode-radio input[type=radio]');
    // .click() đi qua trọn vẹn luồng sự kiện của Svelte (gr.Radio) -> cập nhật
    // state + bắn .change cho backend; bỏ qua nếu ô đã được chọn sẵn.
    if (rs[idx] && !rs[idx].checked){ rs[idx].click(); }
  };
  // Đồng bộ class .active của các thẻ chế độ (HTML) theo radio ẩn — cần khi
  // giá trị radio được đặt bằng backend (vd khôi phục từ BrowserState) chứ
  // không qua midSelectMode.
  window.midSyncModeCards = function(){
    var rs = document.querySelectorAll('#mid-mode-radio input[type=radio]'), idx = 0;
    rs.forEach(function(r, i){ if (r.checked) idx = i; });
    document.querySelectorAll('[data-mid-mode]').forEach(function(el){
      el.classList.toggle('active', (+el.dataset.midMode) === idx); });
  };

  function boardHTML(fen, px){
    var map = {p:'bp',n:'bn',b:'bb',r:'br',q:'bq',k:'bk',P:'wp',N:'wn',B:'wb',R:'wr',Q:'wq',K:'wk'};
    var rows = fen.split(/\s+/)[0].split('/');
    var sq = px / 8;
    function cell(r, f, p){
      var light = ((r + f) % 2) === 0;
      var img = (p && window.MID_PIECES[p]) ? '<img src="' + window.MID_PIECES[p] + '" style="width:' + (sq*0.82) + 'px;height:' + (sq*0.82) + 'px;display:block;">' : '';
      return '<div style="width:' + sq + 'px;height:' + sq + 'px;background:' + (light ? '#F6F2E4' : '#46B49A') + ';display:flex;align-items:center;justify-content:center;">' + img + '</div>';
    }
    var html = '<div class="mid-board" style="box-sizing:content-box;width:' + px + 'px;height:' + px + 'px;display:grid;grid-template-columns:repeat(8,1fr);grid-template-rows:repeat(8,1fr);border:5px solid #2B3990;border-radius:8px;overflow:hidden;box-shadow:0 8px 22px rgba(43,57,144,.22);flex:0 0 auto;">';
    for (var r = 0; r < rows.length; r++){
      var f = 0;
      for (var i = 0; i < rows[r].length; i++){
        var ch = rows[r][i];
        if (/\d/.test(ch)){ var n = +ch; for (var k = 0; k < n; k++){ html += cell(r, f, null); f++; } }
        else { html += cell(r, f, map[ch]); f++; }
      }
    }
    return html + '</div>';
  }
  window.midRenderBoards = function(){
    var prev = document.getElementById('mid-preview');
    if (!prev) return;
    prev.querySelectorAll('pre code').forEach(function(code){
      var pre = code.parentElement;
      if (!pre || pre.dataset.midBoard) return;
      var cls = code.className || '', txt = code.textContent || '';
      var isBoard = cls.indexOf('chessboard') >= 0 || /^\s*fen:/i.test(txt);
      if (!isBoard) return;
      var m = txt.match(/fen:\s*([^\n]+)/i);
      var fen = (m ? m[1] : txt).trim();
      if (!fen || fen.indexOf('/') < 0) return;
      pre.dataset.midBoard = '1';
      var wrap = document.createElement('div');
      wrap.className = 'mid-board-wrap';
      wrap.innerHTML = boardHTML(fen, 256);
      pre.parentNode.insertBefore(wrap, pre);
      pre.style.display = 'none';
    });
  };

  window.midDownloadedUrls = new Set();
  window.midResetDownloads = function(){
    window.midDownloadedUrls.clear();
  };

  window.midTriggerAutoDownloads = function(){
    var container = document.getElementById('mid-downloads');
    if (!container) return;
    var list = container.querySelector('.dl-list[data-auto-download="1"]');
    if (!list) {
      if (!container.innerHTML.trim()) {
        window.midDownloadedUrls.clear();
      }
      return;
    }
    var rows = list.querySelectorAll('.dl-row:not(.dl-all) a.dl-btn');
    var queue = [];
    rows.forEach(function(a){
      var href = a.getAttribute('href');
      var name = a.getAttribute('download') || '';
      if (href && !window.midDownloadedUrls.has(href)){
        window.midDownloadedUrls.add(href);
        queue.push({href: href, name: name});
      }
    });

    queue.forEach(function(item, idx){
      setTimeout(function(){
        var a = document.createElement('a');
        a.href = item.href;
        if (item.name) a.download = item.name;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(function(){
          if (a.parentNode) a.parentNode.removeChild(a);
        }, 1000);
      }, idx * 350);
    });
  };

  document.addEventListener('click', function(e){
    if (!e.target || !e.target.closest) return;
    var card = e.target.closest('[data-mid-mode]');
    if (card){ window.midSelectMode(+card.dataset.midMode); return; }
    var t = e.target.closest('[data-mid-action="toggle-theme"]');
    if (t){ window.midToggleTheme(); return; }
    var clr = e.target.closest('.mid-clear-btn');
    if (clr){ window.midResetDownloads(); }
  });

  function init(){
    if (!document.body.getAttribute('data-mid-theme')){
      var saved = '';
      try { saved = localStorage.getItem('mid-theme') || ''; } catch(e){}
      document.body.setAttribute('data-mid-theme', saved === 'dark' ? 'dark' : 'light');
    }
    setThemeBtn();
    window.midSyncModeCards();
    window.midRenderBoards();
    window.midTriggerAutoDownloads();
  }
  function start(){
    init();
    new MutationObserver(function(){
      setThemeBtn();
      window.midSyncModeCards();
      window.midRenderBoards();
      window.midTriggerAutoDownloads();
    }).observe(document.body, {childList:true, subtree:true});
  }
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})();
