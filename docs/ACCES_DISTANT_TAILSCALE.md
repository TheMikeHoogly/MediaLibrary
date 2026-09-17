# Accès distant par Tailscale — Papa, en Bolivie (17/09)

> La photothèque n'écoute que le réseau de la maison. Papa y entre par
> **Tailscale** : on lui PARTAGE une seule machine, `msi-mike`
> (`100.75.59.40`), celle qui fait tourner le serveur. Il ne voit rien d'autre
> du réseau de Mike. Le serveur écoute sur toutes les interfaces
> (`QuietServer(('', PORT))`) : rien à changer côté code.

## Ce que Mike fait, une fois

1. **Partager `msi-mike`** : https://login.tailscale.com/admin/machines →
   `…` sur `msi-mike` → **Share** → onglet *Share by email* →
   `markushuegli@gmail.com` → **Share**. Papa reçoit l'e-mail d'invitation.
2. **Désactiver l'expiration de clé de `msi-mike`** : même menu `…` →
   **Disable key expiry**. Sans ça, l'accès de Papa tombe au bout de ~6 mois
   sans prévenir.
3. **(Recommandé) Limiter Papa au port 8080** : *Access controls*. Une
   machine partagée suit la politique du tailnet de Mike ; la règle par défaut
   (`*` → `*:*`) ouvre TOUS les ports de `msi-mike` (partage de fichiers,
   bureau à distance…). Remplacer la source `*` de la règle générale par
   `autogroup:member`, et ajouter :
   ```json
   {"action": "accept", "src": ["autogroup:shared"], "dst": ["100.75.59.40:8080"]}
   ```
   (forme `acls` ; en forme `grants` : `"src": ["autogroup:shared"],
   "dst": ["100.75.59.40"], "ip": ["tcp:8080"]`).
4. **Tester comme Papa** : téléphone en **4G, Wi-Fi coupé**, Tailscale
   allumé, ouvrir `100.75.59.40:8080`. Si la page ne vient pas alors que
   Tailscale est *Connected* : **pare-feu Windows** — la règle entrante de
   Python doit couvrir le profil du réseau Tailscale (souvent *Public*).
5. **`msi-mike` doit rester allumé et ne pas se mettre en veille** : c'est
   lui le serveur. Bolivie = UTC−4, six heures de moins que la Suisse l'été.
6. Envoyer le brouillon Gmail « Nos photos de famille, depuis la Bolivie »
   (le mode d'emploi de Papa est dedans), et le mot de passe **à part**.

## Pourquoi un lien `google.com/url?q=…` dans Gmail

Vérifié le 17/09 en relisant les brouillons : ce n'est PAS l'affichage.
Quand un brouillon est créé par l'API, Gmail **réécrit dans le contenu
enregistré** toute adresse reconnue en lien de redirection Google — en texte
brut, l'adresse entière est remplacée. Brouillon d'essai, quatre formes :
seules survivent intactes une adresse dont le texte est **coupé par des
balises** (`<b>100.75.59.40</b><b>:8080</b>`) et une adresse qui ne
ressemble pas à une URL. Un `<a href>` garde son texte visible, mais son
`href` est réécrit (sans gêne pour un site public comme tailscale.com, qui
passe la redirection).
D'où les deux brouillons : **HTML**, l'adresse de la photothèque en gros
caractères, NON cliquable, **à taper**. Tout nouvel e-mail au même usage doit
suivre cette forme — et se relire après création (`get_draft`).
