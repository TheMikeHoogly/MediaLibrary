@echo off
chcp 65001 >nul
title Moniteur GPU NVIDIA
echo Rafraichissement toutes les 2 s. Ferme la fenetre ou Ctrl+C pour arreter.
echo Regarde la colonne "GPU-Util" et la liste des Processes (python.exe / ollama).
echo.
nvidia-smi -l 2
