@echo off
REM ============================================================
REM  Evaluer : assertions vs pixels pour le tagging
REM  Protocole : eval/PLAN_assertions_vs_pixels.md
REM ============================================================
REM  Prerequis : Ollama lance, et le modele qwen3-vl:2b present.
REM  Le banc ne fait que LIRE la base : il n'ecrit AUCUN tag XMP.
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

echo === Passe complete : 150 photos x 3 variantes ===
echo Pour un test rapide a la place, lance :  python eval_tagging.py --limit 20
echo.
python eval_tagging.py
echo.

echo === Termine ===
echo Ouvre eval\rating.html, note a l'aveugle, puis renvoie notes.json.
pause
