@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d octets.
echo ==============================================================
echo   RESTAURER LES PHOTOS SANS JUMEAU CONNU
echo ==============================================================
echo.
echo   La corbeille de rangement garde 44 groupes que le bat 24
echo   refuse de purger. Le tri du 06/09 les a separes en comparant
echo   les PIXELS, comme le bat 40 a dedoublonne - pas le sha256,
echo   qui declarait a tort 30 doublons comme dernieres copies.
echo.
echo     36 ont un jumeau ailleurs   -> purgeables par le bat 24
echo      4 sont des coquilles vides -> rien dedans
echo      3 n ont AUCUN jumeau connu -> a rendre au fonds
echo.
echo   Cet outil rend ces 3 photos a leur dossier d origine. Il ne
echo   supprime rien, il n ecrase jamais un fichier existant, et
echo   tout se defait - journal d annulation dans docs\.
echo.
echo   Les 3 photos : Florine a un mariage, un paysage de Bolivie
echo   avec un herisson en peluche, trois personnes sous un arbre
echo   en fleurs. Le collage : _planches_corbeille\les_7_a_juger.jpg
echo --------------------------------------------------------------
echo   Etape 1 : APERCU, rien ne bouge.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" restaurer_corbeille.py
if errorlevel 1 goto refus

echo.
echo   Etape 2 : pour DEPLACER les photos listees ci-dessus,
echo   reponds O. Sinon reponds N et rien ne bougera.
echo.
choice /c ON /n /m "Restaurer maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto annule

"%PY%" restaurer_corbeille.py --appliquer
if errorlevel 1 goto partiel
echo.
echo   Termine. Les 3 photos sont revenues dans le fonds ; le
echo   serveur les reprendra a son prochain scan.
echo   Lance ensuite le bat 24 pour purger ce qui reste.
pause
exit /b 0

:partiel
echo.
echo   Une ou plusieurs photos ont ete REFUSEES. Lis les lignes
echo   marquees refus ci-dessus : chacune dit pourquoi. Rien n a
echo   ete ecrase. Ne relance pas a l aveugle.
pause
exit /b 1

:refus
echo.
echo   L apercu s est arrete. Rien n a bouge. Lis la raison
echo   ci-dessus avant de recommencer.
pause
exit /b 1

:annule
echo   Annule. Rien n a bouge.
pause
exit /b 0
