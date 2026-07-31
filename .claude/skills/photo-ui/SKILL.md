---
name: photo-ui
description: Design system et conventions UI de la photothèque locale (server.py). À utiliser dès qu'une page, un composant, du CSS ou du JS de l'interface est créé ou modifié — galerie, planche contact, pages Personnes / Chats / Carte / Parcourir, panneaux de nommage, états de pipeline IA. Contient les tokens de couleur et de typographie, les composants canoniques, le plancher d'accessibilité obligatoire et les contraintes d'architecture (zéro build step, zéro dépendance npm). Utiliser aussi pour relire une UI existante et détecter les écarts au système.
---

# Design system — Photothèque « chambre noire »

## Contexte non négociable

Ce projet est **un serveur Python en stdlib pure** (`http.server`). Il n'y a ni npm, ni build
step, ni framework, et cela ne changera pas. Toute proposition impliquant React, Vue, Svelte,
Tailwind, Vite ou un `package.json` est hors sujet — refuse-la et propose l'équivalent en
CSS/JS natif.

Les pages vivent aujourd'hui en chaînes littérales dans `server.py`
(`GALLERY_PAGE`, `PEOPLE_PAGE`, `PETS_PAGE`, `FACES_PAGE`, `MAP_PAGE`, `BROWSE_PAGE`,
`HTML_PAGE`). Cible : les extraire vers `ui/`. En attendant, **toute nouvelle règle CSS passe
par les tokens ci-dessous**, jamais par une valeur en dur.

Interface en **français**. Les libellés, messages d'erreur et états vides sont en français,
sans jargon technique exposé à l'utilisateur.

## Direction visuelle

L'archive photographique et son atelier : la chambre noire. Deux registres alternent —
la **salle sombre** pour regarder, les **surfaces de papier** pour travailler. Cette
alternance est fonctionnelle, pas décorative : une page de visionnage est sombre, un panneau
de nommage est du papier.

## Tokens

Déclarés une seule fois, dans `ui/tokens.css` (ou en tête du bloc `<style>` partagé) :

```css
:root {
  /* ─── Surfaces ─── */
  --salle:        #0C0B0A;  /* fond : noir CHAUD, jamais gris neutre */
  --salle-2:      #14120F;  /* élévation 1 : barres, en-têtes */
  --salle-3:      #1C1916;  /* élévation 2 : cartes, cellules */
  --papier:       #EDE7DC;  /* surfaces de travail : panneaux de nommage */
  --papier-2:     #DDD5C6;  /* bordures et séparateurs sur papier */

  /* ─── Accents (un sens chacun, jamais décoratifs) ─── */
  --veilleuse:    #FF7A1A;  /* lampe inactinique : « l'IA travaille », en attente */
  --veilleuse-d:  #7A3908;  /* variante sombre : liserés, fonds de badge */
  --encre:        #C8321E;  /* destructif, correction, erreur */
  --fixateur:     #4A8C7B;  /* confirmé, succès, assigné */

  /* ─── Texte ─── */
  --texte:        #F2EDE6;  /* sur --salle */
  --graphite:     #A39C93;  /* secondaire sur --salle — 4,6:1, AA conforme */
  --texte-papier: #1A1714;  /* sur --papier */
  --graphite-p:   #5C554C;  /* secondaire sur --papier */

  /* ─── Typographie ─── */
  --f-affichage: "Archivo Narrow", "Roboto Condensed", ui-sans-serif, system-ui, sans-serif;
  --f-texte:     -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --f-donnees:   ui-monospace, "SF Mono", "Cascadia Mono", Consolas, monospace;

  --t-xs: 0.75rem; --t-sm: 0.85rem; --t-md: 0.95rem;
  --t-lg: 1.2rem;  --t-xl: 1.75rem;

  /* ─── Espacement (échelle 4px, pas de valeurs libres) ─── */
  --e-1: 4px; --e-2: 8px; --e-3: 12px; --e-4: 16px; --e-6: 24px; --e-8: 32px;

  /* ─── Formes ─── */
  --r-sm: 3px;   /* vignettes : coins presque nets, comme du film */
  --r-md: 6px;
  --r-pill: 999px;
  --trait: 1px solid #26221E;  /* gouttière de planche contact */

  /* ─── Cibles tactiles ─── */
  --touch: 44px;  /* minimum absolu pour tout élément interactif */
}
```

### Sémantique des accents — à respecter strictement

| Token | Signifie uniquement | Exemples |
|---|---|---|
| `--veilleuse` | *En cours / en attente de traitement IA* | photo non taguée, cluster en construction, file d'embeddings, `:focus-visible` |
| `--fixateur` | *Confirmé / assigné par un humain* | tag `personne:` écrit, chat nommé, chip de filtre actif |
| `--encre` | *Destructif ou en erreur* | supprimer un nom, retirer un tag, échec d'exiftool |

N'utilise **jamais** un accent pour « mettre en valeur » sans que ce sens s'applique.
Un bouton principal neutre utilise `--papier` sur `--salle`, pas un accent.

### Interdits explicites

- `#0a84ff` et toute la palette iOS système. C'est le défaut que ce système remplace.
- Les dégradés violets / indigo, les fonds `#F4F1EA` crème + serif contrasté + terracotta :
  ce sont les signatures visuelles du design généré par IA.
- Les gris neutres (`#0f0f0f`, `#161616`, `#555`, `#666`). Le noir de ce projet est chaud, et
  `#555` sur `#0f0f0f` échoue au contraste AA.
- `outline: none` sans remplacement.

## Typographie

- **Affichage** (`--f-affichage`) : grotesque condensée, interlettrage serré
  (`letter-spacing: -0.01em`), casse normale. Réservée aux titres de section, noms de personnes
  et de chats, compteurs de tête. Elle porte le caractère de la page — utilisée avec retenue.
- **Texte** (`--f-texte`) : pile système. Libellés, boutons, messages.
- **Données** (`--f-donnees`) : **obligatoire** pour tout ce qui est mesure ou identifiant —
  scores de similarité (`sim 0.62`), EXIF, coordonnées GPS, dimensions, dates ISO, compteurs de
  file, tailles de fichier. Justification : ce sont des données, elles s'alignent en colonnes et
  se comparent verticalement. Une monospace le rend lisible ; une sans-serif le déguise en prose.

## Composants canoniques

### Planche contact (galerie)

La signature de l'interface. Une planche contact, pas une grille de cartes.

```css
.planche {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(clamp(96px, 18vw, 168px), 1fr));
  gap: var(--e-1);
  padding: var(--e-2);
  background: var(--salle);
}
.vue {
  position: relative;
  aspect-ratio: 1;
  background: var(--salle-3);
  border-radius: var(--r-sm);
  overflow: hidden;
  content-visibility: auto;              /* gain de rendu sur les grandes planches */
  contain-intrinsic-size: 160px 160px;   /* évite les sauts de scrollbar */
}
.vue--attente { box-shadow: inset 0 0 0 2px var(--veilleuse); }  /* « encore dans le bain » */
.vue__num {                              /* numéro de vue, en marge, comme sur un film */
  position: absolute; bottom: 2px; left: 4px;
  font: var(--t-xs)/1 var(--f-donnees);
  color: var(--graphite); text-shadow: 0 1px 2px #000;
}
```

Règles :

- **Densité par `auto-fill` + `clamp()`**, jamais un nombre de colonnes en dur.
  Interdit : `grid-template-columns: repeat(5, 1fr)`.
- Quand la planche est dans un panneau et non dans la page, utilise une **container query**
  (`container-type: inline-size` sur le parent) et non une media query.
- Le liseré `--veilleuse` remplace la bannière de statut globale : **le statut du pipeline est
  une propriété de la photo**, visible là où elle compte.
- Au-delà de ~2 000 vignettes, `content-visibility` ne suffit plus : passer au virtual scroll
  (fenêtre glissante sur un conteneur de hauteur calculée).

### Surface de travail (papier)

Tout panneau où l'utilisateur **décide** — nommer un cluster, valider des propositions,
corriger une attribution.

```css
.feuille {
  background: var(--papier);
  color: var(--texte-papier);
  border-radius: var(--r-md);
  padding: var(--e-4);
  margin: var(--e-3) var(--e-4);
  box-shadow: 0 1px 0 var(--papier-2), 0 8px 24px #0008;
}
.feuille h3 { font: 600 var(--t-lg)/1.2 var(--f-affichage); }
.feuille .aide { color: var(--graphite-p); font-size: var(--t-sm); }
```

Ne mets **jamais** de contenu photographique en grande taille sur du papier : les photos se
regardent sur `--salle`. Le papier accueille les vignettes de tri, les champs, les boutons.

### Contrôles

```css
.btn {
  min-height: var(--touch); padding: 0 var(--e-4);
  font: 500 var(--t-sm)/1 var(--f-texte);
  border: var(--trait); border-radius: var(--r-md);
  background: var(--salle-3); color: var(--texte); cursor: pointer;
}
.btn--principal { background: var(--papier); color: var(--texte-papier); border-color: var(--papier); }
.btn--confirmer { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.btn--destructif { background: transparent; border-color: var(--encre); color: var(--encre); }

.chip { min-height: 32px; padding: 0 var(--e-3); border-radius: var(--r-pill);
        border: var(--trait); background: var(--salle-3); color: var(--graphite); }
.chip[aria-pressed="true"] { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.chip .n { font-family: var(--f-donnees); font-size: var(--t-xs); opacity: 0.7; }
```

Un chip de filtre est un **bouton bascule** : `<button aria-pressed="true|false">`, pas un
`<div class="on">`. L'état doit être lisible par un lecteur d'écran.

### Centre de tâches

Remplace le bandeau `#pending`. Affiche, avec `--f-donnees` pour les nombres :
tâche en cours, restant à faire, appareil (`CPU` / `GPU`), et un bouton **Pause**.
Les données existent déjà côté serveur : `PET_EMBED_STATE`, `hw_state()`, `system_busy()`,
et la taille des files `TAG_QUEUE` / `FACE_QUEUE` / `ANIMAL_QUEUE` / `PERSON_QUEUE`.

### Toast d'annulation

Toute action destructive est **différée de 10 secondes** et annulable.

```html
<div class="toast" role="status" aria-live="polite">
  <span>Luna retirée de 12 photos.</span>
  <button class="btn" data-annuler>Annuler</button>
</div>
```

`role="status"` + `aria-live="polite"` : l'annonce ne coupe pas la parole au lecteur d'écran.
Le compte à rebours n'est pas affiché en animation — un simple délai suffit et évite le stress.

## Plancher d'accessibilité — bloquant

Aucune UI ne part sans ces sept points. Traite-les comme des tests, pas des intentions.

1. **`:focus-visible` visible partout.**
   `:focus-visible { outline: 2px solid var(--veilleuse); outline-offset: 2px; }`
   Si tu écris `outline: none`, tu dois fournir un remplacement dans la même règle.
2. **Contraste AA** : 4,5:1 pour le texte courant, 3:1 pour les gros titres et les bordures
   porteuses de sens. `--graphite` sur `--salle` est calibré pour passer ; toute nouvelle
   couleur de texte doit être vérifiée.
3. **Cibles tactiles ≥ 44 px.** Une case à cocher de vignette ne fait pas 18 px : c'est la
   **vignette entière** qui est cliquable, avec un indicateur visuel de sélection.
4. **Mouvement réduit :**
   `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }`
   Cela couvre les survols `transform: scale()` et les diaporamas à défilement automatique.
5. **Sémantique** : `<button>` pour les actions, `<a>` pour la navigation. Jamais un `<div>`
   avec un `onclick`. Les images de contenu ont un `alt` ; les vignettes décoratives ont `alt=""`.
6. **Navigation clavier** dans les tâches répétitives de tri : `1`–`9` pour assigner à une
   personne connue, `Espace` pour confirmer, `X` pour rejeter, `Z` pour annuler,
   `Maj+clic` pour sélectionner une plage. Documente les raccourcis dans l'interface elle-même.
7. **États vides et erreurs rédigés.** Un écran vide est une invitation à agir, pas un blanc.
   Une erreur dit ce qui s'est passé et comment le réparer, sans s'excuser et sans être vague.
   « Impossible d'écrire les tags : le NAS n'a pas répondu. Réessayer » — pas « Une erreur est
   survenue ».

## Écriture des libellés

- Le nom d'une action ne change pas au cours du flux : le bouton « Confirmer » produit
  « Confirmé », pas « Enregistré ».
- Nomme les choses par ce que l'utilisateur contrôle, jamais par la mécanique interne.
  « Photos en attente d'analyse », pas « TAG_QUEUE : 412 ». Le nombre en monospace suffit.
- Voix active, casse phrase, verbes simples. Pas de point d'exclamation.
- Le vocabulaire de la chambre noire est disponible et cohérent avec la direction visuelle,
  mais il ne doit jamais coûter en clarté. « En attente d'analyse » bat « Dans le bain ».

## Transitions

- **View Transitions API** en mode multi-document pour galerie → photo → personne. Le serveur
  rend des pages complètes ; cette API donne des transitions natives **sans SPA**. Une
  vignette qui devient la photo plein écran via `view-transition-name` est la seule animation
  qui mérite d'exister ici.
- Toute autre animation doit se justifier. En cas de doute, retire-la : l'excès de mouvement
  est l'un des signaux les plus fiables d'une interface générée sans intention.

## Procédure de revue

Avant de déclarer une UI terminée :

1. Relis le CSS produit contre la liste des **interdits explicites**. Une seule occurrence de
   `#0a84ff` ou d'un nombre de colonnes en dur invalide la livraison.
2. Vérifie les sept points du plancher d'accessibilité, un par un.
3. Vérifie que chaque accent utilisé porte bien son sens (`--veilleuse` = en cours,
   `--fixateur` = confirmé, `--encre` = destructif).
4. Vérifie la spécificité CSS : les sélecteurs de type (`.section`) et d'élément (`.btn`)
   s'annulent facilement sur les marges et les paddings. C'est la panne la plus fréquente
   quand on génère du CSS en volume.
5. Si la skill `web-design-guidelines` est installée, passe-la en porte de revue finale.
