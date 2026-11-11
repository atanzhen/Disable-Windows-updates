$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$dir  = 'C:\ProgramData\NoAutoRestart'
$task = 'NoAutoRestartGuard'
$au   = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
$wu   = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$ux   = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'

$isAdmin = [bool](([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
if (-not $isAdmin) { Write-Host '  错误：需要管理员权限。' -ForegroundColor Red; exit 1 }

function SetSvcMode([string]$n, [string]$mode) {
    $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$n"
    if (-not (Test-Path $key)) { return }
    $want = 3
    if ($mode -eq 'auto')     { $want = 2 }
    if ($mode -eq 'disabled') { $want = 4 }
    $null = & sc.exe config $n start= $mode 2>&1
    try {
        $cur = [int](Get-ItemProperty $key -Name Start -ErrorAction Stop).Start
        if ($cur -ne $want) { Set-ItemProperty $key -Name Start -Value $want -Type DWord -Force -ErrorAction SilentlyContinue }
    } catch { }
}

function RemoveVal([string]$path, [string]$name) {
    if (-not (Test-Path $path)) { return }
    try { Remove-ItemProperty -Path $path -Name $name -Force -ErrorAction Stop } catch { }
}

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor Yellow
Write-Host '   恢复配置：取消全部设置，让系统回到 Windows 默认状态' -ForegroundColor Yellow
Write-Host '  ================================================================' -ForegroundColor Yellow

Write-Host ''
Write-Host '  [1/7] 清除更新模式开关 ...' -ForegroundColor Cyan
if (Test-Path $dir) { Remove-Item (Join-Path $dir 'UPDATE_MODE.flag') -Force -ErrorAction SilentlyContinue }
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  [2/7] 注销守护计划任务 ...' -ForegroundColor Cyan
$gone = $false
try {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction Stop
    $gone = $true
} catch {
    $null = & schtasks /Delete /TN "\$task" /F 2>&1
    if ($LASTEXITCODE -eq 0) { $gone = $true }
}
if ($gone) { Write-Host '        已删除' -ForegroundColor Green }
else { Write-Host '        未找到守护任务（无需删除）' -ForegroundColor DarkGray }

Write-Host ''
Write-Host '  [3/7] 恢复更新服务启动类型 ...' -ForegroundColor Cyan
SetSvcMode 'wuauserv'     'demand'
SetSvcMode 'UsoSvc'       'auto'
SetSvcMode 'WaaSMedicSvc' 'demand'
SetSvcMode 'DoSvc'        'auto'
$null = & sc.exe start wuauserv 2>&1
$null = & sc.exe start UsoSvc 2>&1
Start-Sleep -Milliseconds 800
foreach ($s in @('wuauserv', 'UsoSvc', 'WaaSMedicSvc', 'DoSvc')) {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$s'" -ErrorAction SilentlyContinue
    if ($svc) { Write-Host ("        {0,-13} {1,-8} {2}" -f $svc.Name, $svc.State, $svc.StartMode) }
}

Write-Host ''
Write-Host '  [4/7] 删除更新策略注册表项 ...' -ForegroundColor Cyan
foreach ($n in @('NoAutoUpdate', 'AUOptions', 'NoAutoRebootWithLoggedOnUsers',
                 'AlwaysAutoRebootAtScheduledTime', 'AutoInstallMinorUpdates',
                 'RebootRelaunchTimeoutEnabled')) {
    RemoveVal $au $n
}
RemoveVal $wu 'SetDisableUXWUAccess'
# 空键清理：避免留下空壳策略键
foreach ($k in @($au, $wu)) {
    if (Test-Path $k) {
        $has = (Get-Item $k).GetValueNames()
        $sub = (Get-ChildItem $k -ErrorAction SilentlyContinue)
        if ((-not $has -or $has.Count -eq 0) -and (-not $sub -or $sub.Count -eq 0)) {
            Remove-Item $k -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  [5/7] 恢复界面 / 蓝屏 / 自动登录设置 ...' -ForegroundColor Cyan
foreach ($n in @('IsExpedited', 'RestartNotificationsAllowed2', 'SmartActiveHoursState')) { RemoveVal $ux $n }
if (Test-Path $ux) {
    try { Set-ItemProperty $ux -Name ActiveHoursStart -Value 8 -Type DWord -Force -ErrorAction SilentlyContinue } catch { }
    try { Set-ItemProperty $ux -Name ActiveHoursEnd   -Value 17 -Type DWord -Force -ErrorAction SilentlyContinue } catch { }
}
try { Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl' -Name AutoReboot -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue } catch { }
try { Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name DisableAutomaticRestartSignOn -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue } catch { }
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  [6/7] 恢复更新相关计划任务 ...' -ForegroundColor Cyan
$on = 0
foreach ($p in @('\Microsoft\Windows\UpdateOrchestrator\', '\Microsoft\Windows\WindowsUpdate\', '\Microsoft\Windows\InstallService\', '\Microsoft\Windows\WaaSMedic\')) {
    try {
        Get-ScheduledTask -TaskPath $p -ErrorAction Stop | ForEach-Object {
            try { Enable-ScheduledTask -TaskPath $_.TaskPath -TaskName $_.TaskName -ErrorAction Stop | Out-Null; $on++ } catch { }
        }
    } catch { }
}
Write-Host "        已恢复 $on 个任务" -ForegroundColor Green

Write-Host ''
Write-Host '  [7/7] 刷新策略并清理程序数据 ...' -ForegroundColor Cyan
$null = gpupdate /force 2>&1
if (Test-Path $dir) {
    Get-ChildItem $dir -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_.FullName -Force -Recurse -ErrorAction SilentlyContinue
    }
    Remove-Item $dir -Force -Recurse -ErrorAction SilentlyContinue
}
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor Green
Write-Host '   已恢复系统默认配置' -ForegroundColor Green
Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '   · 自动更新：恢复为系统默认（会重新自动检查 / 下载 / 安装）' -ForegroundColor White
Write-Host '   · 自动重启：恢复为系统默认（更新后可能自动重启）' -ForegroundColor White
Write-Host '   · 守护任务与程序数据：已全部删除' -ForegroundColor White
Write-Host '   · 本程序仍在，可随时重新点「一键锁死」' -ForegroundColor White
Write-Host '  ================================================================' -ForegroundColor Green
Write-Host ''
exit 0
