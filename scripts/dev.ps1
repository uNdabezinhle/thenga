# Northbound / Reka local helpers (Windows PowerShell)
# Usage:  .\scripts\dev.ps1 <command>
# Commands: setup | run | test | seed | migrate | e2e

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"

function Ensure-Venv {
    if (-not (Test-Path $Py)) {
        Write-Host "Creating venv..." -ForegroundColor Cyan
        Push-Location $Backend
        python -m venv .venv
        & .\.venv\Scripts\python.exe -m pip install --upgrade pip
        & .\.venv\Scripts\pip.exe install -r requirements.txt
        Pop-Location
    }
}

$cmd = if ($args.Count -gt 0) { $args[0] } else { "help" }

switch ($cmd) {
    "setup" {
        Ensure-Venv
        Push-Location $Backend
        & $Py manage.py migrate --noinput
        & $Py manage.py seed_northbound
        Pop-Location
        Write-Host "Ready. Run: .\scripts\dev.ps1 run" -ForegroundColor Green
    }
    "migrate" {
        Ensure-Venv
        Push-Location $Backend
        & $Py manage.py makemigrations
        & $Py manage.py migrate
        Pop-Location
    }
    "seed" {
        Ensure-Venv
        Push-Location $Backend
        & $Py manage.py seed_northbound
        Pop-Location
    }
    "run" {
        Ensure-Venv
        Push-Location $Backend
        Write-Host "API + SPA  http://127.0.0.1:8000/" -ForegroundColor Green
        Write-Host "Swagger    http://127.0.0.1:8000/api/docs/" -ForegroundColor Green
        & $Py manage.py runserver 127.0.0.1:8000
        Pop-Location
    }
    "test" {
        Ensure-Venv
        Push-Location $Backend
        & $Py manage.py test apps.pricing apps.accounts apps.cart apps.orders apps.payments apps.notifications -v 1
        Pop-Location
    }
    "e2e" {
        Ensure-Venv
        Push-Location $Backend
        & $Py scripts_e2e_test.py
        Pop-Location
    }
    "compose" {
        Push-Location $Root
        docker compose up --build
        Pop-Location
    }
    default {
        Write-Host @"
Northbound dev script

  .\scripts\dev.ps1 setup     Create venv, migrate, seed
  .\scripts\dev.ps1 run       Start Django (API + SPA on :8000)
  .\scripts\dev.ps1 test      Run unit/integration tests
  .\scripts\dev.ps1 e2e       Smoke script against test client
  .\scripts\dev.ps1 seed      Re-seed catalogue + demo users
  .\scripts\dev.ps1 migrate   makemigrations + migrate
  .\scripts\dev.ps1 compose   docker compose up --build

Compose extras: Mailpit UI http://localhost:8025  |  SPA http://localhost:3000
"@
    }
}
