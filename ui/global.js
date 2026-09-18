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
        l'ouvrent jamais.
     6. la VEILLE (P1, Mike 14/09) : un compte connecté, cinq minutes sans
        un geste, et la page cède la place à ses photos, au hasard. */
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
    h += '<button type="button" class="item" data-veille role="menuitem">' +
      '<span aria-hidden="true">\uD83C\uDF19</span> Lancer la veille</button>';
    if (MOI.porte) {
      // Chacun change SON mot de passe (16/09) : le bouton ne vivait que
      // dans Reglages, que seul l'admin voit dans ce menu.
      h += '<div class="sep"></div><button type="button" class="item" data-mdp role="menuitem">' +
        '<span aria-hidden="true">\uD83D\uDD11</span> Changer mon mot de passe</button>';
      h += '<button type="button" class="item" data-sortir role="menuitem">' +
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
    var veille = m.querySelector('[data-veille]');
    if (veille) veille.addEventListener('click', function () {
      fermerMenu(); Veille.lancer(true);   // un GESTE : le plein ecran est permis
    });
    var mdp = m.querySelector('[data-mdp]');
    if (mdp) mdp.addEventListener('click', function () { fermerMenu(); MotDePasse.ouvrir(); });
    var sortir = m.querySelector('[data-sortir]');
    if (sortir) sortir.addEventListener('click', function () {
      fetch('/api/deconnexion', { method: 'POST' })
        .then(function () { location.href = '/connexion'; })
        .catch(function () { location.href = '/connexion'; });
    });
  }
  /* Le panneau MOT DE PASSE. Pas de `prompt()` : il affiche la saisie en
     clair et bloque la page. TROIS champs masques -- l'ACTUEL d'abord (17/09 :
     sans lui, une session ouverte suffisait a fermer la porte derriere soi),
     puis le nouveau deux fois -- la regle dite AVANT (8 caracteres), et une
     reponse ecrite dans le panneau. Meme coque que les raccourcis : fond,
     Echap, retour du focus. */
  var MotDePasse = (function () {
    var el = null, avant = null;
    function fermer() {
      if (!el || !el.classList.contains('on')) return;
      el.classList.remove('on');
      if (avant && avant.focus) avant.focus();
    }
    function construire() {
      el = document.createElement('div');
      el.className = 'raccourcis';
      el.innerHTML =
        '<form class="raccourcis__p mdp" role="dialog" aria-modal="true" aria-labelledby="mdp-titre">' +
        '<div class="raccourcis__t"><h2 id="mdp-titre">Changer mon mot de passe</h2>' +
        '<button type="button" class="btn" data-fermer>Fermer</button></div>' +
        '<p class="mdp__intro">8 caract\u00e8res au moins. Il remplace l\u2019ancien tout de suite.</p>' +
        '<label for="mdp-0">Mot de passe actuel</label>' +
        '<input id="mdp-0" type="password" autocomplete="current-password" required>' +
        '<label for="mdp-1">Nouveau mot de passe</label>' +
        '<input id="mdp-1" type="password" autocomplete="new-password" minlength="8" required>' +
        '<label for="mdp-2">Le m\u00eame, une seconde fois</label>' +
        '<input id="mdp-2" type="password" autocomplete="new-password" minlength="8" required>' +
        '<p class="mdp__msg" role="status" aria-live="polite"></p>' +
        '<div class="mdp__acts"><button type="submit" class="btn">Enregistrer</button></div>' +
        '</form>';
      document.body.appendChild(el);
      el.addEventListener('click', function (ev) {
        if (ev.target === el || ev.target.hasAttribute('data-fermer')) fermer();
      });
      el.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') { ev.preventDefault(); fermer(); }
      });
      var f = el.querySelector('form'), msg = el.querySelector('.mdp__msg');
      f.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var v = el.querySelector('#mdp-0').value;
        var a = el.querySelector('#mdp-1').value, b = el.querySelector('#mdp-2').value;
        if (!v) { msg.textContent = 'Donne d\u2019abord ton mot de passe actuel.'; return; }
        if (a.length < 8) { msg.textContent = 'Trop court : 8 caract\u00e8res au moins.'; return; }
        if (a !== b) { msg.textContent = 'Les deux saisies diff\u00e8rent. Retape-les.'; return; }
        msg.textContent = 'Enregistrement\u2026';
        fetch('/api/comptes/mdp', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mdp: a, actuel: v }) })
          .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
          .then(function (r) {
            if (r && r.ok) {
              msg.textContent = 'Mot de passe chang\u00e9. Il servira \u00e0 la prochaine connexion.';
              f.reset();
              if (MOI) MOI.mdp_temporaire = false;   // le panneau ne revient plus
            } else {
              msg.textContent = 'Refus\u00e9 : ' + ((r && r.error) || 'le serveur n\u2019a pas accept\u00e9') + '.';
            }
          })
          .catch(function () { msg.textContent = 'Le serveur n\u2019a pas r\u00e9pondu. R\u00e9essayer.'; });
      });
    }
    function ouvrir(motif) {
      if (!el) construire();
      // Le geste part du MENU, qui se ferme : rendre le focus a son bouton.
      avant = document.querySelector('.moi-bouton') || document.activeElement;
      el.querySelector('.mdp__msg').textContent = '';
      // Un mot de passe pose par l'admin est PROVISOIRE, et on le dit ici :
      // un panneau qui s'ouvre seul sans dire pourquoi passe pour une panne.
      el.querySelector('.mdp__intro').textContent = motif === 'temporaire'
        ? 'Ton mot de passe actuel a \u00e9t\u00e9 pos\u00e9 par l\u2019administrateur. '
          + 'Choisis-en un que lui seul ne conna\u00eet pas. 8 caract\u00e8res au moins.'
        : '8 caract\u00e8res au moins. Il remplace l\u2019ancien tout de suite.';
      el.classList.add('on');
      el.querySelector('#mdp-0').focus();
    }
    return { ouvrir: ouvrir };
  })();

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
      allumerLampe(d);
      Veille.armer();                     // un compte connecte, et seulement lui
      // Mot de passe pose par l'admin : le panneau s'ouvre tout de suite, a
      // chaque page, tant qu'il n'a pas ete remplace. Il reste FERMABLE -- on
      // ne met pas quelqu'un dehors de sa propre photoheque.
      if (d.mdp_temporaire) setTimeout(function () { MotDePasse.ouvrir('temporaire'); }, 400);
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

  /* La LAMPE des depots : allumee par la MEME reponse que le nom d'utilisateur.
     `/api/moi` est le seul appel que toutes les pages font deja -- la lampe
     n'en ajoute aucun, et elle ne peut pas se desynchroniser du compte.

     Elle ne s'allume que s'il y a quelque chose a decider : une lampe qui
     brille en permanence cesse d'etre lue (meme raison que l'onglet
     Sensibles, demande de Mike le 06/09). */
  function allumerLampe(d) {
    var l = document.querySelector('.appnav .lampe');
    var n = (d && d.depots && d.depots.a_trier) || 0;
    if (!l || !n) return;
    l.querySelector('.lampe__n').textContent = n;
    l.setAttribute('aria-label',
      n + ' depot(s) en attente de tri, le plus ancien depuis '
      + ((d.depots.jours || 0) + ' jour(s)'));
    l.hidden = false;
  }

  /* L'onglet « Sensibles » ne s'affiche QUE s'il y a quelque chose a juger.

     Deux raisons, et la seconde est la demande de Mike du 06/09. (1) Une
     phototheque de famille n'annonce pas en permanence qu'il existe un onglet
     « sensibles » : un onglet vide en permanence apprend a ne plus le
     regarder. (2) Quand il y a quelque chose, c'est l'application qui le DIT,
     avec le nombre — au lieu qu'on colle a Mike des liens a ouvrir un par un.

     Un echec est SILENCIEUX : sans reponse, l'onglet reste cache, exactement
     comme s'il n'y avait rien. Il ne faut pas qu'une panne reseau fasse
     clignoter une alerte sur un sujet pareil. */
  function poserSensibles() {
    var t = document.querySelector('.appnav .tab--sensibles');
    if (!t) return;
    fetch('/api/sensibles').then(function (r) { return r.json(); })
      .then(function (d) {
        var n = (d && d.photos && d.photos.length) || 0;
        if (!n) return;
        var pastille = t.querySelector('.n');
        if (pastille) pastille.textContent = n;
        t.setAttribute('aria-label', n + ' photo(s) en attente de votre verdict');
        t.hidden = false;
      })
      .catch(function () { /* silencieux : pas d'alerte sur une panne reseau */ });
  }

  /* ── 6. LA VEILLE ─────────────────────────────────────────────────────
     Ce qu'elle promet, et ce qu'elle se refuse.

     - Elle ne montre que ce que la VUE rend au compte (`/api/veille`) :
       jamais le PRIVE d'un autre, jamais une photo masquee. Elle ne s'arme
       qu'une fois `/api/moi` revenu avec un nom.
     - Elle ne part PAS si la page est cachee, si une video joue, si le
       diaporama de la galerie tourne, ou si un element est deja en plein
       ecran : quelqu'un regarde deja quelque chose.
     - Le vrai plein ecran exige un GESTE (`requestFullscreen`). Au bout de
       cinq minutes d'inaction il n'y en a pas : la veille couvre alors la
       FENETRE. Lancee depuis le menu, elle passe en plein ecran.
     - Elle ne tient pas le NAS eveille indefiniment : ses vignettes portent
       `veille=1` (le serveur ne suspend pas son travail de fond pour elle),
       et apres DUREE elle s'eteint en ecran noir, sans plus rien demander.
     - Le geste qui la reveille est AVALE : un « X » qui rejette une carte
       sur /tri ne doit pas partir parce qu'on voulait juste retrouver
       la page. */
  var Veille = (function () {
    var ATTENTE = 5 * 60 * 1000;      // inaction avant la veille
    var PAS = 8000;                    // une photo toutes les 8 s
    var DUREE = 30 * 60 * 1000;        // puis ecran noir, plus aucune requete
    var TIRAGE = 120;
    var MOIS = ['janvier', 'f\u00e9vrier', 'mars', 'avril', 'mai', 'juin', 'juillet',
                'ao\u00fbt', 'septembre', 'octobre', 'novembre', 'd\u00e9cembre'];
    var arme = false, minuteur = null, pas = null, fin = null;
    var ouverte = false, depuis = 0, liste = [], rang = 0, lock = null;
    var retour = null, calque = null, bouge = 0, pleinEcran = false;

    function occupee() {
      if (document.hidden || document.fullscreenElement) return true;
      if (document.querySelector('#ss.open')) return true;       // diaporama galerie
      var ms = document.querySelectorAll('video, audio');
      for (var i = 0; i < ms.length; i++) if (!ms[i].paused) return true;
      return false;
    }
    function rearmer() {
      clearTimeout(minuteur);
      if (arme && !ouverte) minuteur = setTimeout(declencher, ATTENTE);
    }
    function declencher() {
      if (occupee()) { rearmer(); return; }
      lancer(false);
    }
    function construire() {
      calque = document.createElement('div');
      calque.className = 'veille';
      calque.setAttribute('role', 'dialog');
      calque.setAttribute('aria-modal', 'true');
      calque.setAttribute('aria-label', 'Veille : vos photos au hasard');
      calque.tabIndex = -1;
      calque.hidden = true;
      calque.innerHTML =
        '<img class="veille__img" alt=""><img class="veille__img" alt="">' +
        '<p class="veille__date donnee" hidden></p>' +
        '<p class="veille__aide">Bouger la souris ou appuyer sur une touche pour reprendre</p>';
      document.body.appendChild(calque);
    }
    function dateDe(t) {
      if (!t) return '';
      var d = new Date(t * 1000);
      return MOIS[d.getMonth()] + ' ' + d.getFullYear();
    }
    function tirer(suite) {
      fetch('/api/veille?n=' + TIRAGE).then(function (r) { return r.json(); })
        .then(function (d) {
          liste = (d && d.items) || []; rang = 0;
          suite(liste.length > 0);
        }).catch(function () { suite(false); });
    }
    function suivante() {
      if (!ouverte) return;
      if (Date.now() - depuis > DUREE) { eteindre(); return; }
      if (rang >= liste.length) { tirer(function (ok) { if (ok) suivante(); else eteindre(); }); return; }
      var it = liste[rang++];
      var img = new Image();
      img.onload = function () {
        if (!ouverte) return;
        var imgs = calque.querySelectorAll('.veille__img');
        var avant = imgs[0].classList.contains('on') ? imgs[0] : imgs[1];
        var apres = avant === imgs[0] ? imgs[1] : imgs[0];
        apres.src = img.src;
        apres.classList.add('on'); avant.classList.remove('on');
        var dt = calque.querySelector('.veille__date');
        // « Lausanne · août 2021 » : le lieu d'abord, c'est lui qu'on cherche.
        dt.textContent = [it.l, dateDe(it.t)].filter(Boolean).join(' \u00b7 ');
        dt.hidden = !dt.textContent;
        pas = setTimeout(suivante, PAS);
      };
      img.onerror = function () { pas = setTimeout(suivante, 500); };   // une de moins, pas un arret
      img.src = '/api/thumb?s=1600&veille=1&key=' + encodeURIComponent(it.k);
    }
    function eteindre() {
      // Ecran noir : la veille reste la (on ne rend pas la page a un salon
      // vide), mais elle ne demande plus rien a personne.
      clearTimeout(pas);
      if (!calque) return;
      calque.classList.add('veille--eteinte');
      calque.querySelectorAll('.veille__img').forEach(function (i) {
        i.classList.remove('on'); i.removeAttribute('src');
      });
      calque.querySelector('.veille__date').hidden = true;
      if (lock) { try { lock.release(); } catch (e) {} lock = null; }
    }
    function lancer(geste) {
      if (ouverte) return;
      clearTimeout(minuteur);
      if (!calque) construire();
      // Le plein ecran se demande PENDANT le geste, avant tout aller-retour
      // reseau : apres un `fetch`, l'activation du clic peut etre perdue.
      if (geste && calque.requestFullscreen) {
        calque.hidden = false;            // un element cache ne passe pas en plein ecran
        calque.requestFullscreen().catch(function () {});
      }
      tirer(function (ok) {
        if (!ok) {                        // aucun compte, ou aucune photo : rien a montrer
          if (document.fullscreenElement === calque) document.exitFullscreen().catch(function () {});
          calque.hidden = true;
          rearmer(); return;
        }
        retour = document.activeElement;
        ouverte = true; depuis = Date.now(); bouge = 0;
        calque.classList.remove('veille--eteinte');
        calque.hidden = false;
        document.documentElement.classList.add('veille-ouverte');
        calque.focus();
        if (navigator.wakeLock) {
          navigator.wakeLock.request('screen').then(function (l) { lock = l; })
            .catch(function () {});
        }
        suivante();
      });
    }
    function fermer() {
      ouverte = false;
      clearTimeout(pas);
      if (lock) { try { lock.release(); } catch (e) {} lock = null; }
      if (document.fullscreenElement === calque && document.exitFullscreen) {
        document.exitFullscreen().catch(function () {});
      }
      calque.hidden = true;
      document.documentElement.classList.remove('veille-ouverte');
      // Le focus revient d'ou il venait -- sauf si c'etait l'entree d'un
      // menu referme depuis : alors au bouton qui ouvre ce menu.
      if (retour && (!retour.isConnected || retour.offsetParent === null)) {
        retour = document.querySelector('.moi-bouton');
      }
      if (retour && retour.focus) { try { retour.focus(); } catch (e) {} }
      rearmer();
    }
    // Un geste : pendant la veille il la ferme ET il est avale ; sinon il
    // relance le compte a rebours.
    function geste(ev) {
      if (!ouverte) { rearmer(); return; }
      if (ev.type === 'pointermove') {
        // Le passage en plein ecran deplace la fenetre sous la souris et le
        // navigateur en fait un mouvement : 1,5 s de grace, puis la reference.
        if (Date.now() - depuis < 1500) { bouge = 0; return; }
        // On compte ce que la SOURIS a parcouru (`movement`), pas l'ecart de
        // position : quand la fenetre change de taille (plein ecran), le
        // navigateur emet un mouvement sans deplacement -- observe le 16/09,
        // il refermait la veille a 2,3 s. Et une souris posee tremble : 8 px.
        bouge += Math.abs(ev.movementX || 0) + Math.abs(ev.movementY || 0);
        if (bouge < 8) return;
      }
      ev.preventDefault(); ev.stopPropagation();
      if (ev.type === 'pointerdown') avalerClic = true;
      fermer();
    }
    var avalerClic = false;
    function clic(ev) {
      if (!avalerClic) return;
      avalerClic = false;
      ev.preventDefault(); ev.stopPropagation();
    }
    function armer() {
      if (arme || /^\/connexion/.test(location.pathname)) return;
      arme = true;
      ['pointermove', 'pointerdown', 'keydown', 'wheel', 'touchstart'].forEach(function (t) {
        document.addEventListener(t, geste, { capture: true, passive: false });
      });
      document.addEventListener('click', clic, true);
      // Echap en plein ecran est pris par le NAVIGATEUR, la page ne voit pas
      // la touche : quitter le plein ecran que la veille avait pris, c'est la
      // quitter aussi.
      document.addEventListener('fullscreenchange', function () {
        if (ouverte && calque && pleinEcran && document.fullscreenElement !== calque) fermer();
        pleinEcran = !!calque && document.fullscreenElement === calque;
      });
      document.addEventListener('visibilitychange', function () {
        if (document.hidden && ouverte) fermer(); else rearmer();
      });
      rearmer();
    }
    return { armer: armer, lancer: lancer, fermer: function () { if (ouverte) fermer(); },
             ouverte: function () { return ouverte; } };
  })();
  window.Veille = Veille;

  function demarrer() {
    marquerOngletActif(); poserRecherche(); poserAide(); poserMoi();
    poserSensibles();
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
