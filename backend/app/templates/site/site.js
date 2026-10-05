(function () {
  'use strict';
  var views = Array.prototype.slice.call(document.querySelectorAll('.view'));
  var byKey = {};
  views.forEach(function (v) { byKey[v.dataset.key] = v; });
  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.sidebar a[data-view]'));
  var sidebar = document.getElementById('sidebar');
  var menuBtn = document.getElementById('menu-btn');
  var baseTitle = document.title;

  // --- maths: typeset a part of the page once, when it is first shown ---------------------------
  var mj = window.MathJax && window.MathJax.startup ? window.MathJax.startup.promise : null;
  function typeset(el) {
    if (!mj || !el || el.dataset.typeset) return Promise.resolve();
    el.dataset.typeset = '1';
    mj = mj.then(function () { return window.MathJax.typesetPromise([el]); })
           .catch(function (e) { console.warn('MathJax', e); });
    return mj;
  }
  function retypeset(el) {
    if (!mj || !el) return Promise.resolve();
    mj = mj.then(function () {
      window.MathJax.typesetClear([el]);
      return window.MathJax.typesetPromise([el]);
    }).catch(function (e) { console.warn('MathJax', e); });
    return mj;
  }

  // --- views: #key or #key~anchor -------------------------------------------------------------
  function show() {
    var hash = decodeURIComponent(location.hash.replace(/^#/, ''));
    var parts = hash.split('~');
    var key = parts[0], anchor = parts[1];
    if (!byKey[key]) {           // a plain anchor such as #sida-12: find its view
      var target = hash && document.getElementById(hash);
      var owner = target && target.closest('.view');
      if (owner) { key = owner.dataset.key; anchor = hash; } else { key = 'hem'; }
    }
    var view = byKey[key];
    views.forEach(function (v) { v.hidden = v !== view; });
    navLinks.forEach(function (a) {
      if (a.dataset.view === key) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    document.title = key === 'hem' ? baseTitle : view.dataset.title + ' – ' + baseTitle;
    closeMenu();
    var el = anchor && document.getElementById(anchor);
    var jump = function () {
      if (el) {
        el.scrollIntoView({block: 'start'});
        el.classList.add('flash');
      } else {
        window.scrollTo(0, 0);
      }
    };
    jump();
    typeset(view).then(jump);
    if (key === 'kort') deck.start();
  }
  window.addEventListener('hashchange', show);

  // --- mobile menu ----------------------------------------------------------------------------
  function closeMenu() {
    sidebar.classList.remove('open');
    menuBtn.setAttribute('aria-expanded', 'false');
  }
  menuBtn.addEventListener('click', function () {
    var open = !sidebar.classList.contains('open');
    sidebar.classList.toggle('open', open);
    menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeMenu(); hideResults(); } });

  // --- exercises: solutions are typeset when opened ------------------------------------------
  function openSolution(d) {
    var body = d.querySelector('.mj-defer');
    if (body) { body.classList.remove('mj-defer'); delete body.dataset.typeset; typeset(body); }
  }
  document.querySelectorAll('.ex-sol').forEach(function (d) {
    d.addEventListener('toggle', function () { if (d.open) openSolution(d); });
  });
  var exOpen = document.getElementById('ex-open');
  if (exOpen) exOpen.addEventListener('change', function () {
    document.querySelectorAll('.ex-sol').forEach(function (d) { d.open = exOpen.checked; });
  });

  // --- bevislista: hide proofs to practise ----------------------------------------------------
  var hide = document.getElementById('hide-proofs');
  var bevis = byKey.bevis;
  if (hide && bevis) {
    hide.addEventListener('change', function () {
      bevis.classList.toggle('hide-proofs', hide.checked);
      bevis.querySelectorAll('.proof').forEach(function (p) { p.classList.remove('revealed'); });
    });
    bevis.addEventListener('click', function (e) {
      var p = e.target.closest('.proof');
      if (p && bevis.classList.contains('hide-proofs')) p.classList.add('revealed');
    });
  }

  // --- flashcards -----------------------------------------------------------------------------
  var deck = (function () {
    var dataEl = document.getElementById('deck-data');
    if (!dataEl) return {start: function () {}};
    var cards = JSON.parse(dataEl.textContent);
    var $ = function (id) { return document.getElementById(id); };
    var front = $('card-front'), back = $('card-back'), src = $('card-src'), count = $('deck-count');
    var flip = $('deck-flip'), yes = $('deck-yes'), no = $('deck-no'), onlyUnknown = $('deck-unknown');
    var known = {};
    try { known = JSON.parse(localStorage.getItem('known-cards') || '{}') || {}; } catch (e) { known = {}; }
    var order = cards.map(function (_, i) { return i; });
    var pos = 0, started = false;

    function save() { try { localStorage.setItem('known-cards', JSON.stringify(known)); } catch (e) {} }
    function list() {
      return onlyUnknown.checked ? order.filter(function (i) { return !known[i]; }) : order;
    }
    function render() {
      var l = list();
      if (!l.length) {
        front.innerHTML = '<p class="deck-empty">Du har markerat alla kort som kunda. Avmarkera filtret för att se dem igen.</p>';
        back.hidden = true; src.textContent = ''; count.textContent = '0 kort kvar';
        flip.hidden = yes.hidden = no.hidden = true;
        return;
      }
      pos = (pos + l.length) % l.length;
      var c = cards[l[pos]];
      front.innerHTML = c.f;
      back.innerHTML = c.b;
      back.hidden = true; flip.hidden = false; yes.hidden = no.hidden = true;
      src.textContent = 'sida ' + c.p;
      src.href = c.v ? '#' + c.v + '~sida-' + c.p : '#';
      var nKnown = Object.keys(known).length;
      count.textContent = 'Kort ' + (pos + 1) + ' av ' + l.length + ' · ' + nKnown + ' kunda';
      retypeset($('card'));
    }
    function turn() { back.hidden = false; flip.hidden = true; yes.hidden = no.hidden = false; }
    function mark(ok) {
      var i = list()[pos];
      if (ok) known[i] = 1; else delete known[i];
      save();
      if (!(ok && onlyUnknown.checked)) pos += 1;
      render();
    }
    flip.addEventListener('click', turn);
    yes.addEventListener('click', function () { mark(true); });
    no.addEventListener('click', function () { mark(false); });
    $('deck-next').addEventListener('click', function () { pos += 1; render(); });
    $('deck-prev').addEventListener('click', function () { pos -= 1; render(); });
    $('deck-shuffle').addEventListener('click', function () {
      for (var i = order.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1)), t = order[i]; order[i] = order[j]; order[j] = t;
      }
      pos = 0; render();
    });
    onlyUnknown.addEventListener('change', function () { pos = 0; render(); });
    $('card').addEventListener('keydown', function (e) {
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); if (back.hidden) turn(); }
      if (e.key === 'ArrowRight') { pos += 1; render(); }
      if (e.key === 'ArrowLeft') { pos -= 1; render(); }
    });
    return {start: function () { if (!started) { started = true; render(); } }};
  })();

  // --- search ---------------------------------------------------------------------------------
  var input = document.getElementById('search'), results = document.getElementById('results');
  var index = null;
  function norm(s) { return s.toLowerCase().normalize('NFC'); }
  function buildIndex() {
    index = [];
    views.forEach(function (v) {
      if (v.dataset.key === 'hem' || v.dataset.key === 'kort') return;
      var page = null, text = '';
      var flush = function () {
        if (text.trim()) index.push({view: v.dataset.key, title: v.dataset.title, page: page,
                                     text: text.replace(/\s+/g, ' ').trim()});
        text = '';
      };
      Array.prototype.forEach.call(v.childNodes, function (n) {
        if (n.nodeType === 1 && n.classList.contains('sida')) { flush(); page = n.id.replace('sida-', ''); return; }
        if (n.nodeType === 1 && n.matches('mjx-container')) return;
        text += ' ' + (n.nodeType === 1 ? sourceText(n) : n.textContent);
      });
      flush();
    });
  }
  function sourceText(el) {   // text with the TeX of typeset maths instead of the SVG
    var clone = el.cloneNode(true);
    clone.querySelectorAll('mjx-container').forEach(function (m) { m.remove(); });
    return clone.textContent;
  }
  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; });
  }
  function hideResults() { results.hidden = true; }
  function search() {
    var q = norm(input.value.trim());
    if (q.length < 2) { hideResults(); return; }
    if (!index) buildIndex();
    var hits = [];
    for (var i = 0; i < index.length && hits.length < 40; i++) {
      var at = norm(index[i].text).indexOf(q);
      if (at >= 0) hits.push([index[i], at]);
    }
    if (!hits.length) {
      results.innerHTML = '<p class="r-none">Inga träffar för ”' + escapeHtml(input.value.trim()) + '”.</p>';
    } else {
      results.innerHTML = hits.map(function (h) {
        var e = h[0], at = h[1], t = e.text;
        var a = Math.max(0, at - 60), b = Math.min(t.length, at + q.length + 80);
        var snip = (a ? '…' : '') + escapeHtml(t.slice(a, at)) + '<mark>' + escapeHtml(t.slice(at, at + q.length)) +
                   '</mark>' + escapeHtml(t.slice(at + q.length, b)) + (b < t.length ? '…' : '');
        var href = '#' + e.view + (e.page ? '~sida-' + e.page : '');
        return '<a href="' + href + '"><span class="r-where">' + escapeHtml(e.title) +
               (e.page ? ' · sida ' + e.page : '') + '</span><span class="r-text">' + snip + '</span></a>';
      }).join('');
    }
    results.hidden = false;
  }
  input.addEventListener('input', search);
  input.addEventListener('focus', search);
  results.addEventListener('click', function (e) { if (e.target.closest('a')) { hideResults(); input.blur(); } });
  document.addEventListener('click', function (e) { if (!e.target.closest('.search')) hideResults(); });

  show();
})();
