# Mindol 曼兜 — 语义记忆引擎 部署脚本
# 注意：使用 NoBOM 安全写入

$ErrorActionPreference = "Stop"
$script:utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
function Write-NoBOM { param([string]$Path, [string]$Content) [System.IO.File]::WriteAllText($Path, $Content, $script:utf8NoBOM) }
function Write-NoBOMJson { param([string]$Path, $Object, [int]$Depth=10) $j = $Object | ConvertTo-Json -Depth $Depth; [System.IO.File]::WriteAllText($Path, $j, $script:utf8NoBOM) }

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Mindol 曼兜 部署" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$srcRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$agentsDir = "$env:USERPROFILE\.agents"
$pluginMarketDir = "$agentsDir\plugins\mindol"

Write-Host "[1/2] 注册 Marketplace..." -ForegroundColor Cyan
$c = Get-Content "$srcRoot\.codex-plugin\plugin.json" -Encoding UTF8 -Raw
$ver = ($c | ConvertFrom-Json).version
$ts = Get-Date -Format "yyyyMMddHHmmss"
$c = $c -replace '"version":\s*"[^"]+"', '"version": "'+$ver+'+codex.'+$ts+'"'
New-Item -ItemType Directory -Path "$pluginMarketDir\.codex-plugin" -Force | Out-Null
Write-NoBOM -Path "$pluginMarketDir\.codex-plugin\plugin.json" -Content $c
Write-Host "  版本: $ver+codex.$ts" -ForegroundColor Green

$mktplFile = "$agentsDir\.agents\plugins\marketplace.json"
if (-not (Test-Path $mktplFile)) {
    New-Item -ItemType Directory -Path "$agentsDir\.agents\plugins" -Force | Out-Null
    $m = @{ name="personal"; interface=@{displayName="Personal"}; plugins=@(
        @{ name="diegin"; source=@{source="local"; path="./plugins/diegin"}; policy=@{installation="AVAILABLE";authentication="ON_INSTALL"}; category="Productivity" },
        @{ name="mindol"; source=@{source="local"; path="./plugins/mindol"}; policy=@{installation="AVAILABLE";authentication="ON_INSTALL"}; category="Productivity" }
    )}
    Write-NoBOMJson -Path $mktplFile -Object $m
} else {
    $m = Get-Content $mktplFile -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($m.plugins.name -notcontains "mindol") {
        $m.plugins += @{ name="mindol"; source=@{source="local"; path="./plugins/mindol"}; policy=@{installation="AVAILABLE";authentication="ON_INSTALL"}; category="Productivity" }
        Write-NoBOMJson -Path $mktplFile -Object $m
    }
}
Write-Host "  marketplace 已注册" -ForegroundColor Green

Write-Host "[2/2] 安装插件..." -ForegroundColor Cyan
$cli = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin" -Recurse -Filter "codex.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if ($cli) {
    & $cli plugin remove "mindol@personal" 2>&1 | Out-Null
    & $cli plugin add "mindol@personal" 2>&1 | Out-Null
    Write-Host "  mindol@personal 安装完成" -ForegroundColor Green
}
Write-Host "============================================" -ForegroundColor Green
Write-Host "  重启 Codex 生效" -ForegroundColor Green