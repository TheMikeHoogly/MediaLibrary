/* global.js — la brique JS COMMUNE, injectée sur chaque page par
   server._send_html (juste après la barre <!--APPNAV-->, sinon avant </body>).
   Même contrat que tokens.css / base.css : une seule source, relue à chaud,
   cuite par bundle.py, absente sans casser le serveur. Zéro dépendance.

   Quatre rôles, et rien d'autre :
     1. l'onglet ACTIF de la barre (« vous êtes ici ») ;
     2. le sablier réseau (.netbusy) qui enrobe window.fetch ;
     3. le champ de recherche de la barre : masqué sur /files (la galerie a
        la sienne), et le raccourci « / » y met le focus depuis tout onglet ;
     4. le panneau « ? » des raccourcis (point 6 du plancher) : la touche ?
        ou le bouton de la barre, Échap ferme ; le contenu est
        docs/RACCOURCIS.md servi par /api/raccourcis — UNE source, la doc
        n'est pas recopiée ici ;
     5. MON COMPTE (Mike, 31/08) : qui regarde, et le peu qui se règle.
        Un seul appel à /api/moi par page, et le menu se construit à
        l'ouverture — pas au chargement : la plupart des visites ne
        l'ouvrent jamais. */
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
  // UN SEUL outil de recherche par page (Mike, 31/08) : sur /files la galerie
  // porte déjà sa barre (tags, IA), sur /map la carte porte la sienne (même
  // moteur /api/search, mais elle FILTRE la carte) — on masque celui de la
  // barre là où la page a le sien.
  function poserRecherche() {
    var form = document.querySelector('.appnav-q');
    if (!form) return;
    if (p.indexOf('/files') === 0 || p.indexOf('/map') === 0) { form.hidden = true; return; }
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

  // ── 4. le panneau « ? » des raccourcis ───────────────────────────────────
  // Rend le Markdown de docs/RACCOURCIS.md : titres `##`, paragraphes,
  // tableaux « | Touche | Effet | », listes « - ». Le préambule (citation
  // « > ») et tout ce qui suit le marqueur « <!-- panneau: fin --> » ne sont
  // pas montrés. Les sections qui parlent de la page courante remontent en
  // tête avec une pastille « ici ».
  var ICI = {
    '/files': ['Galerie', '/files'], '/map': ['Carte', '/map'],
    '/pets': ['Animaux', '/pets'], '/people': ['Personnes', '/people'],
    '/sujets': ['/sujets'], '/tranche': ['/tranche'], '/residu': ['/residu']
  };
  function echapper(t) {
    return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function enLigne(t) {
    // `touche` → <kbd>, **gras** → <strong>, le reste échappé.
    return echapper(t)
      .replace(/`([^`]+)`/g, function (_, k) { return '<kbd>' + k + '</kbd>'; })
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }
  function sections(md) {
    var fin = md.indexOf('<!-- panneau: fin -->');
    if (fin >= 0) md = md.slice(0, fin);
    var out = [], cur = null, vide = true, lignes = md.split(/\r?\n/);
    for (var i = 0; i < lignes.length; i++) {
      var l = lignes[i];
      if (/^## /.test(l)) { cur = { titre: l.slice(3).trim(), blocs: [] }; out.push(cur); continue; }
      if (!cur || /^>/.test(l) || /^# /.test(l)) continue;
      if (/^\|/.test(l)) {
        if (/^\|\s*-+/.test(l) || /^\|\s*Touche/i.test(l)) continue;
        var cells = l.replace(/^\||\|$/g, '').split('|').map(function (c) { return c.trim(); });
        var dernier = cur.blocs[cur.blocs.length - 1];
        if (!dernier || dernier.type !== 'table') { dernier = { type: 'table', lignes: [] }; cur.blocs.push(dernier); }
        dernier.lignes.push(cells);
      } else if (/^- /.test(l)) {
        var d2 = cur.blocs[cur.blocs.length - 1];
        if (!d2 || d2.type !== 'liste') { d2 = { type: 'liste', items: [] }; cur.blocs.push(d2); }
        d2.items.push(l.slice(2));
      } else if (l.trim()) {
        var d3 = cur.blocs[cur.blocs.length - 1];
        if (d3 && d3.type === 'p' && !vide) d3.texte += ' ' + l.trim();
        else if (d3 && d3.type === 'liste' && !vide) d3.items[d3.items.length - 1] += ' ' + l.trim();
        else cur.blocs.push({ type: 'p', texte: l.trim() });
      }
      vide = !l.trim();
    }
    return out;
  }
  function estIci(titre) {
    var cles = null;
    for (var k in ICI) if (p.indexOf(k) === 0) { cles = ICI[k]; break; }
    if (!cles) return false;
    for (var j = 0; j < cles.length; j++) if (titre.indexOf(cles[j]) >= 0) return true;
    return false;
  }
  function rendre(md) {
    var secs = sections(md), avant = [], apres = [];
    secs.forEach(function (s) {
      s.ici = estIci(s.titre);
      (s.ici || /^Partout/.test(s.titre) ? avant : apres).push(s);
    });
    var h = '';
    avant.concat(apres).forEach(function (s) {
      h += '<h3>' + enLigne(s.titre) + (s.ici ? '<span class="ici">ici</span>' : '') + '</h3>';
      s.blocs.forEach(function (b) {
        if (b.type === 'table') {
          h += '<table>' + b.lignes.map(function (c) {
            return '<tr>' + c.map(function (x) { return '<td>' + enLigne(x) + '</td>'; }).join('') + '</tr>';
          }).join('') + '</table>';
        } else if (b.type === 'liste') {
          h += '<ul>' + b.items.map(function (x) { return '<li>' + enLigne(x) + '</li>'; }).join('') + '</ul>';
        } else h += '<p>' + enLigne(b.texte) + '</p>';
      });
    });
    return h || '<p>Aucun raccourci relevé.</p>';
  }
  var panneau = null, contenuCharge = false, focusAvant = null;
  function bouton() { return document.querySelector('.appnav-aide'); }
  function construirePanneau() {
    panneau = document.createElement('div');
    panneau.className = 'raccourcis';
    panneau.innerHTML =
      '<div class="raccourcis__p" role="dialog" aria-modal="true" aria-labelledby="raccourcis-titre">' +
      '<div class="raccourcis__t"><h2 id="raccourcis-titre">Raccourcis clavier</h2>' +
      '<button type="button" class="btn" data-fermer>Fermer</button></div>' +
      '<div class="raccourcis__c"><p>Chargement\u2026</p></div></div>';
    document.body.appendChild(panneau);
    panneau.addEventListener('click', function (ev) {
      if (ev.target === panneau || ev.target.hasAttribute('data-fermer')) fermerPanneau();
    });
  }
  function ouvrirPanneau() {
    if (!panneau) construirePanneau();
    focusAvant = document.activeElement;
    panneau.classList.add('on');
    var b = bouton(); if (b) b.setAttribute('aria-expanded', 'true');
    panneau.querySelector('[data-fermer]').focus();
    if (contenuCharge) return;
    var c = panneau.querySelector('.raccourcis__c');
    fetch('/api/raccourcis').then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (md) {
      c.innerHTML = rendre(md); contenuCharge = true;
    }).catch(function () {
      c.innerHTML = '<p>Le pense-b\u00eate n\u2019a pas pu \u00eatre lu (docs/RACCOURCIS.md). R\u00e9essayer.</p>';
    });
  }
  function fermerPanneau() {
    if (!panneau || !panneau.classList.contains('on')) return;
    panneau.classList.remove('on');
    var b = bouton(); if (b) b.setAttribute('aria-expanded', 'false');
    if (focusAvant && focusAvant.focus) focusAvant.focus();
  }
  function poserAide() {
    var b = bouton();
    if (b) b.addEventListener('click', function () {
      if (panneau && panneau.classList.contains('on')) fermerPanneau(); else ouvrirPanneau();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && panneau && panneau.classList.contains('on')) { ev.preventDefault(); fermerPanneau(); return; }
      if (ev.key !== '?' || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      var t = ev.target;
      var tag = t && t.tagName ? t.tagName.toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || (t && t.isContentEditable)) return;
      ev.preventDefault();
      if (panneau && panneau.classList.contains('on')) fermerPanneau(); else ouvrirPanneau();
    });
  }

  // Injecté juste APRÈS la barre, la brique la trouve déjà : on marque tout de
  // suite, sans attendre la fin de l'analyse (un onglet qui s'allume en retard
  // se voit sur une grande galerie). Sinon — page sans barre — on attend.
  // ── 5. mon compte ────────────────────────────────────────────────────────
  // La DENSITÉ de la planche est le seul réglage vraiment personnel du site :
  // elle change ce qu'on voit d'un coup d'œil, et elle ne regarde que celui
  // qui la choisit. Elle vit donc dans son navigateur (localStorage), posée
  // sur :root avant tout rendu — la galerie et les Dossiers lisent `--vig`
  // avec leur propre clamp en repli, donc l'absence de réglage ne casse rien.
  var CRANS = { serre: '86px', normal: '', large: '210px' };
  function densiteLue() {
    try { return localStorage.getItem('densite') || 'normal'; } catch (e) { return 'normal'; }
  }
  function poserDensite(cran) {
    var v = CRANS[cran] === undefined ? '' : CRANS[cran];
    if (v) document.documentElement.style.setProperty('--vig', v);
    else document.documentElement.style.removeProperty('--vig');
    try { localStorage.setItem('densite', cran); } catch (e) {}
  }
  poserDensite(densiteLue());          // AVANT le premier rendu de la planche

  var MOI = null, MENU_OUVERT = false;
  function zoneMoi() { return document.querySelector('.appnav-moi'); }
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function construireMenu() {
    var m = document.getElementById('moi-menu');
    var h = '<div class="tete"><b>' + esc(MOI.nom) + '</b><span>' +
      (MOI.admin ? 'Administrateur' : 'Compte') + '</span></div>';
    h += '<a href="/files?q=' + encodeURIComponent('personne:' + MOI.nom) +
      '" role="menuitem"><span aria-hidden="true">\uD83D\uDC64</span> Mes photos</a>';
    // Le dossier privé n'apparaît QUE s'il existe (le serveur le dit) :
    // ouvrir une porte sur une page vide serait pire que ne rien offrir.
    if (MOI.prive) {
      h += '<a href="' + esc(MOI.prive) + '" role="menuitem">' +
        '<span aria-hidden="true">\uD83D\uDD12</span> Mon dossier priv\u00e9</a>';
    }
    h += '<div class="sep"></div><div class="titre">Taille des vignettes</div>' +
      '<div class="crans">';
    ['serre', 'normal', 'large'].forEach(function (c) {
      h += '<button type="button" data-cran="' + c + '" aria-pressed="' +
        (densiteLue() === c) + '">' +
        { serre: 'Serr\u00e9', normal: 'Normal', large: 'Large' }[c] + '</button>';
    });
    h += '</div><div class="sep"></div>' +
      '<button type="button" class="item" data-aide role="menuitem">' +
      '<span aria-hidden="true">\u2328\uFE0F</span> Raccourcis clavier</button>' +
      '<a href="/aide" role="menuitem">' +
      '<span aria-hidden="true">\uD83D\uDCD6</span> Comment \u00e7a marche</a>';
    if (MOI.admin) {
      h += '<a href="/reglages" role="menuitem"><span aria-hidden="true">\u2699\uFE0F</span> R\u00e9glages</a>' +
        '<a href="/sante" role="menuitem"><span aria-hidden="true">\uD83E\uDE7A</span> Sant\u00e9 du serveur</a>';
    }
    if (MOI.porte) {
      h += '<div class="sep"></div><button type="button" class="item" data-sortir role="menuitem">' +
        '<span aria-hidden="true">\u21AA</span> Se d\u00e9connecter</button>';
    }
    m.innerHTML = h;
    m.querySelectorAll('[data-cran]').forEach(function (b) {
      b.addEventListener('click', function () {
        var c = b.getAttribute('data-cran');
        poserDensite(c);
        m.querySelectorAll('[data-cran]').forEach(function (x) {
          x.setAttribute('aria-pressed', String(x === b));
        });
      });
    });
    var aide = m.querySelector('[data-aide]');
    if (aide) aide.addEventListener('click', function () { fermerMenu(); ouvrirPanneau(); });
    var sortir = m.querySelector('[data-sortir]');
    if (sortir) sortir.addEventListener('click', function () {
      fetch('/api/deconnexion', { method: 'POST' })
        .then(function () { location.href = '/connexion'; })
        .catch(function () { location.href = '/connexion'; });
    });
  }
  function ouvrirMenu() {
    var z = zoneMoi(); if (!z || !MOI) return;
    construireMenu();
    z.querySelector('.moi-menu').hidden = false;
    z.querySelector('.moi-bouton').setAttribute('aria-expanded', 'true');
    MENU_OUVERT = true;
  }
  function fermerMenu() {
    var z = zoneMoi(); if (!z || !MENU_OUVERT) return;
    z.querySelector('.moi-menu').hidden = true;
    z.querySelector('.moi-bouton').setAttribute('aria-expanded', 'false');
    MENU_OUVERT = false;
  }
  function poserMoi() {
    var z = zoneMoi(); if (!z) return;
    fetch('/api/moi').then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.nom) return;          // porte ouverte, personne connecté
      MOI = d;
      z.querySelector('.moi-pastille').textContent = d.nom.trim().charAt(0);
      z.querySelector('.moi-nom').textContent = d.nom;
      z.querySelector('.moi-bouton').setAttribute(
        'aria-label', 'Mon compte : ' + d.nom);
      z.hidden = false;
      z.querySelector('.moi-bouton').addEventListener('click', function () {
        if (MENU_OUVERT) fermerMenu(); else ouvrirMenu();
      });
      // controle: redondant -- fermer en cliquant ailleurs ; le meme geste a
      // son bouton (rappuyer) et sa touche (Echap).
      document.addEventListener('click', function (ev) {
        if (MENU_OUVERT && !z.contains(ev.target)) fermerMenu();
      });
      document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && MENU_OUVERT) { fermerMenu(); }
      });
    }).catch(function () { /* sans identite, la barre reste telle quelle */ });
  }

  function demarrer() {
    marquerOngletActif(); poserRecherche(); poserAide(); poserMoi();
  }
  if (document.querySelector('.appnav') || document.readyState !== 'loading') demarrer();
  else document.addEventListener('DOMContentLoaded', demarrer);
})();

/* ──────────────────────────────────────────────────────────────────────────
   VIGNETTES — chargement paresseux, et surtout BORNE (Mike, 06/09)

   Ce qu'on a mesuré ce jour-là. La vue Dossiers d'un dossier de 2 139 photos
   demandait une vignette 512 px pour CHAQUE fichier. Les images portaient
   pourtant `loading="lazy"` : l'attribut natif ne suffit pas, pour deux
   raisons distinctes.

   1. Sa marge est décidée par le navigateur, pas par nous. Sur une liaison
      rapide, Chrome charge en pratique presque tout d'un coup.
   2. Et surtout, `loading="lazy"` ne borne RIEN. Une fois qu'il a décidé de
      charger N images, il pose N requêtes. Or un navigateur n'ouvre que six
      connexions vers un même hôte : les six sont restées prises une seconde
      par vignette (lecture NAS à froid), pendant des dizaines de minutes.
      Conséquence observée : un AUTRE onglet vers le même serveur n'a jamais
      obtenu de connexion — sa requête n'apparaît même pas dans le journal du
      serveur. La photothèque entière semblait plantée.

   D'où les deux mécanismes ci-dessous, et il en faut deux :
     • un IntersectionObserver, avec une marge à NOUS (400 px, soit un peu
       d'avance au défilement) — déterministe, pas au gré du navigateur ;
     • une file d'attente qui ne laisse QUE `EN_VOL_MAX` requêtes en l'air.
       Quatre sur six : il en reste deux pour naviguer, c'est-à-dire pour que
       l'interface réponde encore pendant qu'une planche se remplit.

   La file est UNIQUE pour la page : c'est la contrainte du navigateur qui est
   globale, une file par planche ne bornerait rien. */
window.Vignettes = (function () {
  'use strict';
  var EN_VOL_MAX = 4;        // sur les six connexions du navigateur
  var MARGE = '400px';       // un peu d'avance, pas toute la page
  var file = [], enVol = 0;

  function libere(img) {
    if (img._vEnVol) { img._vEnVol = false; enVol--; servir(); }
  }
  function servir() {
    while (enVol < EN_VOL_MAX && file.length) {
      var img = file.shift();
      if (!img || !img.dataset.src) continue;
      enVol++;
      img._vEnVol = true;
      // `addEventListener` et pas `onload` : la page garde SES propres
      // handlers (classe « loaded », repli sur l'original quand la vignette
      // serveur ne sait pas rendre). On compte, on ne décide pas.
      img.addEventListener('load', function () { libere(this); }, { once: true });
      img.addEventListener('error', function () { libere(this); }, { once: true });
      img.src = img.dataset.src;
      delete img.dataset.src;
    }
  }

  /* Mettre une image en file. Rend `false` si elle n'a rien à charger. */
  function charger(img) {
    if (!img || !img.dataset || !img.dataset.src) return false;
    file.push(img);
    servir();
    return true;
  }

  /* Un observateur prêt à l'emploi : il met en file l'image de l'entrée qui
     entre en vue, puis cesse de la surveiller. */
  function observateur(marge) {
    return new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        var img = e.target.tagName === 'IMG' ? e.target
                                             : e.target.querySelector('img');
        if (img) charger(img);
        this.unobserve(e.target);
      }, this);
    }, { rootMargin: marge || MARGE });
  }

  /* Brancher toutes les `img[data-src]` d'une racine. Sans
     IntersectionObserver (navigateur ancien), on charge tout de suite : mieux
     vaut une page lente qu'une page vide. */
  function brancher(racine, marge) {
    var imgs = (racine || document).querySelectorAll('img[data-src]');
    if (!('IntersectionObserver' in window)) {
      for (var i = 0; i < imgs.length; i++) charger(imgs[i]);
      return null;
    }
    var obs = observateur(marge);
    for (var j = 0; j < imgs.length; j++) obs.observe(imgs[j]);
    return obs;
  }

  return { charger: charger, observateur: observateur, brancher: brancher,
           enVolMax: EN_VOL_MAX };
})();
