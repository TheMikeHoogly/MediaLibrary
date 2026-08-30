/* global.js — la brique JS COMMUNE, injectée sur chaque page par
   server._send_html (juste après la barre <!--APPNAV-->, sinon avant </body>).
   Même contrat que tokens.css / base.css : une seule source, relue à chaud,
   cuite par bundle.py, absente sans casser le serveur. Zéro dépendance.

   Trois rôles, et rien d'autre :
     1. l'onglet ACTIF de la barre (« vous êtes ici ») ;
     2. le sablier réseau (.netbusy) qui enrobe window.fetch ;
     3. le champ de recherche de la barre : masqué sur /files (la galerie a
        la sienne), et le raccourci « / » y met le focus depuis tout onglet.
   Le panneau « ? » des raccourcis viendra ici, sur la même brique. */
(function () {
  'use strict';
  var p = location.pathname;

  // ── 1. onglet actif ──────────────────────────────────────────────────────
  // Fusion « Sujets » (ROADMAP #4) : /people et /pets sont des vues
  // spécialisées de Sujets — l'onglet Sujets reste allumé quand on y est.
  var pNav = (p.indexOf('/people') === 0 || p.indexOf('/pets') === 0) ? '/sujets' : p;
  function marquerOngletActif() {
    var tabs = document.querySelectorAll('.appnav a.tab');
    for (var i = 0; i < tabs.length; i++) {
      var d = tabs[i].getAttribute('data-p');
      if (pNav === d || (d !== '/' && pNav.indexOf(d) === 0)) tabs[i].classList.add('active');
    }
  }

  // ── 2. sablier réseau ────────────────────────────────────────────────────
  // Enrobe window.fetch pour compter les requêtes en vol (tous les appels de
  // l'appli passent par fetch, y compris post()). Un délai de 250 ms évite un
  // clignotement sur les requêtes instantanées (sondages de statut) ; seul un
  // vrai temps d'attente affiche le sablier. Les vignettes se chargent via
  // <img>, pas fetch → elles ne le déclenchent pas. Installé TOUT DE SUITE :
  // les scripts de page qui suivent doivent déjà passer par l'enrobage.
  (function () {
    if (!window.fetch || window.fetch.__uiGlobal) return;
    var pending = 0, timer = null;
    function el() { return document.querySelector('.netbusy'); }
    function show() { var b = el(); if (b) { b.classList.add('on'); b.setAttribute('aria-hidden', 'false'); } }
    function hide() { var b = el(); if (b) { b.classList.remove('on'); b.setAttribute('aria-hidden', 'true'); } }
    var orig = window.fetch;
    var enrobe = function () {
      pending++;
      if (pending === 1) { clearTimeout(timer); timer = setTimeout(show, 250); }
      function done() { pending--; if (pending <= 0) { pending = 0; clearTimeout(timer); hide(); } }
      return orig.apply(this, arguments).then(
        function (r) { done(); return r; },
        function (e) { done(); throw e; });
    };
    enrobe.__uiGlobal = true;
    window.fetch = enrobe;
  })();

  // ── 3. la recherche dans la barre ────────────────────────────────────────
  // Le champ est un vrai <form action="/files"> : Entrée suffit, sans JS.
  // Sur /files la galerie porte déjà sa barre (tags, IA) : deux champs sur
  // une même page se contrediraient — on masque celui de la barre.
  function poserRecherche() {
    var form = document.querySelector('.appnav-q');
    if (!form) return;
    if (p.indexOf('/files') === 0) { form.hidden = true; return; }
    var champ = form.querySelector('input[name="q"]');
    if (!champ) return;
    // Un envoi vide renverrait la galerie entière : on le retient.
    form.addEventListener('submit', function (ev) {
      if (!champ.value.trim()) { ev.preventDefault(); champ.focus(); }
    });
    // « / » met le focus dans le champ — jamais quand on tape déjà quelque
    // part (un champ, une zone de texte, un contenu éditable) : les pages de
    // tri écoutent les lettres, pas la barre oblique, donc pas de conflit.
    document.addEventListener('keydown', function (ev) {
      if (ev.key !== '/' || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      var t = ev.target;
      var tag = t && t.tagName ? t.tagName.toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || (t && t.isContentEditable)) return;
      ev.preventDefault();
      champ.focus();
      champ.select();
    });
  }

  // Injecté juste APRÈS la barre, la brique la trouve déjà : on marque tout de
  // suite, sans attendre la fin de l'analyse (un onglet qui s'allume en retard
  // se voit sur une grande galerie). Sinon — page sans barre — on attend.
  function demarrer() { marquerOngletActif(); poserRecherche(); }
  if (document.querySelector('.appnav') || document.readyState !== 'loading') demarrer();
  else document.addEventListener('DOMContentLoaded', demarrer);
})();
