@echo off
REM ============================================================
REM  Publier MediaLibrary sur GitHub (premiere publication)
REM ============================================================
REM  AVANT de lancer ce script, cree le depot VIDE sur GitHub :
REM    1. va sur https://github.com/new
REM    2. Repository name : MediaLibrary
REM    3. coche "Private"
REM    4. NE COCHE RIEN d'autre (pas de README, pas de .gitignore,
REM       pas de licence) : le depot doit etre VIDE pour ce push.
REM    5. clique "Create repository"
REM ============================================================

cd /d "%~dp0"

echo.
echo === Etat du depot local ===
git status -s
echo.

echo === Ajout du remote "origin" ===
git remote remove origin 2>nul
git remote add origin https://github.com/TheMikeHoogly/MediaLibrary.git
git remote -v
echo.

echo === Branche principale renommee en "main" ===
git branch -M main
echo.

echo === Envoi vers GitHub (premier push) ===
echo Une fenetre de connexion GitHub peut s'ouvrir la premiere fois.
echo Connecte-toi dans le navigateur, puis reviens ici.
git push -u origin main
echo.

echo === Termine ===
echo Ouvre https://github.com/TheMikeHoogly/MediaLibrary pour verifier.
pause
