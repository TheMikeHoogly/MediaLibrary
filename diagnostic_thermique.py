#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic THERMIQUE apres les deux arrets brutaux du 30-31/08.

MESURE seulement (famille diagnostic_, agent banc) :
  1. les evenements Windows des 7 derniers jours qui racontent les arrets :
     Kernel-Power 41 (arret brutal), 1074 (arret demande), Kernel-Thermal /
     ACPI (etranglement ou coupure thermique) ;
  2. l'etat GPU du moment (nvidia-smi : temperature, watts, horloges) ;
  3. la temperature CPU si la machine l'expose (souvent absente sous Windows).

N'ecrit rien, ne regle rien : la sortie est la matiere du verdict.
Usage : diagnostic_thermique.py [--jours 7]
"""
import argparse
import subprocess
import sys


def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return (p.stdout or b'').decode('utf-8', errors='replace').strip() or \
               (p.stderr or b'').decode('utf-8', errors='replace').strip()
    except Exception as e:                                     # noqa: BLE001
        return 'indisponible: %s' % e


def ps(script, timeout=90):
    return run(['powershell', '-NoProfile', '-Command', script], timeout)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--jours', type=int, default=7)
    a = ap.parse_args(argv)
    j = a.jours

    print('=== 1. Arrets des %d derniers jours (journal Windows System) ===' % j,
          flush=True)
    print(ps(
        "$d=(Get-Date).AddDays(-%d);"
        "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1074,6008; StartTime=$d} -ErrorAction SilentlyContinue |"
        " Sort-Object TimeCreated |"
        " ForEach-Object { '{0}  Id={1}  {2}' -f $_.TimeCreated, $_.Id,"
        " ($_.Message -split \"`n\")[0].Substring(0, [Math]::Min(110, ($_.Message -split \"`n\")[0].Length)) }"
        % j), flush=True)

    print('', flush=True)
    print('=== 2. Evenements THERMIQUES (Kernel-Thermal, ACPI, WHEA) ===', flush=True)
    print(ps(
        "$d=(Get-Date).AddDays(-%d);"
        "Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$d} -ErrorAction SilentlyContinue |"
        " Where-Object { $_.ProviderName -match 'Thermal|ACPI|WHEA' -or $_.Message -match 'thermique|thermal|temperature' } |"
        " Sort-Object TimeCreated | Select-Object -Last 25 |"
        " ForEach-Object { '{0}  {1}  Id={2}  {3}' -f $_.TimeCreated, $_.ProviderName, $_.Id,"
        " ($_.Message -split \"`n\")[0].Substring(0, [Math]::Min(100, ($_.Message -split \"`n\")[0].Length)) }"
        % j), flush=True)

    print('', flush=True)
    print('=== 3. GPU maintenant (nvidia-smi) ===', flush=True)
    print(run(['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,'
               'clocks.sm,power.draw,fan.speed',
               '--format=csv,noheader']), flush=True)

    print('', flush=True)
    print('=== 4. CPU : ce que la machine expose ===', flush=True)
    print(ps(
        "$t=Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue;"
        "if ($t) { $t | ForEach-Object { '{0}: {1:N1} C' -f $_.InstanceName, (($_.CurrentTemperature/10)-273.15) } }"
        " else { 'Zones ACPI non exposees (habituel sur portable MSI) - lire la temperature CPU demande HWiNFO ou MSI Center.' }"),
        flush=True)

    print('', flush=True)
    print('=== 5. Plan d alimentation actif ===', flush=True)
    print(ps('powercfg /getactivescheme'), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
