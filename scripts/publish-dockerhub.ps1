$ErrorActionPreference = "Stop"

Write-Host "SMART Irrigacao - publicacao Docker Hub" -ForegroundColor Cyan

try {
    docker info | Out-Null
} catch {
    Write-Host "Docker Desktop/daemon nao esta disponivel." -ForegroundColor Red
    Write-Host "Abra o Docker Desktop, aguarde o engine ficar verde e rode novamente." -ForegroundColor Yellow
    exit 1
}

Write-Host "Entrando no Docker Hub..." -ForegroundColor Cyan
docker login
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Buildando imagens..." -ForegroundColor Cyan
docker compose build --pull
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Publicando imagens..." -ForegroundColor Cyan
docker compose push
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Publicado:" -ForegroundColor Green
Write-Host "  dnredson/smart-irrigacao-api:v0.3.0"
Write-Host "  dnredson/smart-irrigacao-web:v0.3.0"
