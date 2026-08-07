@echo off
REM ============================================================
REM  Rejouer SEULEMENT la variante V2 avec le prompt exigeant
REM  les noms/especes asserted. Reutilise V0 et V1 deja calcules
REM  dans eval/tagging_results.json (pas de GPU redepense dessus).
REM  L'ancien fichier est sauve en eval/tagging_results.v2avant.json
REM ============================================================
REM  Prerequis : Ollama lance, qwen3-vl:2b present, et une passe
REM  complete deja faite (tagging_results.json existant).
REM ============================================================

cd /d "%~dp0"

echo.
echo === Verification d'Ollama ===
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo Ollama ne repond pas sur http://localhost:11434
  echo Lance Ollama, puis relance ce script.
  pause
  exit /b 1
)
echo Ollama OK.
echo.

echo === Rejoue V2 : 150 photos, une variante ===
python eval_tagging.py --rerun-v2
echo.

echo === Termine ===
echo Ouvre eval\rating.html, note a l'aveugle, puis renvoie notes.json.
pause
