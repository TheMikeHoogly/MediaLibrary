# -*- coding: utf-8 -*-
"""Combien de server.py tournent ? Deux, et le NAS est balaye deux fois."""
import subprocess, sys
cmd = ['wmic', 'process', 'where', "name like '%python%'", 'get',
       'ProcessId,CreationDate,CommandLine', '/format:list']
try:
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=40).stdout
except Exception:
    out = ''
if not out.strip():
    ps = ('Get-CimInstance Win32_Process -Filter "name like \'%python%\'" | '
          'Select-Object ProcessId,CreationDate,CommandLine | Format-List')
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                         capture_output=True, text=True, timeout=60).stdout
bloc, n = [], 0
for ligne in out.splitlines():
    ligne = ligne.strip()
    if not ligne:
        if bloc:
            texte = ' | '.join(bloc)
            if 'server.py' in texte or 'pilotage' in texte or 'agent' in texte:
                n += 1
                print(texte[:300])
                print('-' * 60)
            bloc = []
        continue
    bloc.append(ligne)
print(f'{n} processus python du projet')
