$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$dir   = 'C:\ProgramData\NoAutoRestart'
$task  = 'NoAutoRestartGuard'
$psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$au    = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'

$isAdmin = [bool](([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
if (-not $isAdmin) { Write-Host '  错误：需要管理员权限。' -ForegroundColor Red; exit 1 }

function SetSvcMode([string]$n, [string]$mode) {
    $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$n"
    if (-not (Test-Path $key)) { return }
    $want = 3
    if ($mode -eq 'auto') { $want = 2 }
    if ($mode -eq 'disabled') { $want = 4 }
    $null = & sc.exe config $n start= $mode 2>&1
    try {
        $cur = [int](Get-ItemProperty $key -Name Start -ErrorAction Stop).Start
        if ($cur -ne $want) { Set-ItemProperty $key -Name Start -Value $want -Type DWord -Force -ErrorAction SilentlyContinue }
    } catch { }
}

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor Yellow
Write-Host '   临时恢复 Windows 更新（更新模式）' -ForegroundColor Yellow
Write-Host '   自动重启依然是禁止的，只是把“安装更新”放开。' -ForegroundColor Yellow
Write-Host '  ================================================================' -ForegroundColor Yellow

Write-Host ''
Write-Host '  [1/6] 写入更新模式开关（守护任务自动休眠）...' -ForegroundColor Cyan
New-Item -ItemType Directory -Path $dir -Force | Out-Null
"update-mode enabled $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Set-Content (Join-Path $dir 'UPDATE_MODE.flag') -Encoding utf8
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  [2/6] 暂停守护任务 ...' -ForegroundColor Cyan
$paused = $false
try {
    $t = Get-ScheduledTask -TaskName $task -ErrorAction Stop
    if ($t.State -ne 'Disabled') { Disable-ScheduledTask -TaskName $task -ErrorAction Stop | Out-Null }
    $paused = $true
} catch {
    $null = & schtasks /Change /TN "\$task" /Disable 2>&1
    if ($LASTEXITCODE -eq 0) { $paused = $true }
}
if ($paused) { Write-Host '        已暂停' -ForegroundColor Green }
else { Write-Host '        未找到守护任务（无需暂停）' -ForegroundColor DarkGray }

Write-Host ''
Write-Host '  [3/6] 恢复更新服务 ...' -ForegroundColor Cyan
SetSvcMode 'wuauserv'    'demand'
SetSvcMode 'UsoSvc'      'auto'
SetSvcMode 'WaaSMedicSvc' 'demand'
SetSvcMode 'DoSvc'       'auto'
$null = & sc.exe start UsoSvc 2>&1
$null = & sc.exe start wuauserv 2>&1
Start-Sleep -Milliseconds 800
foreach ($s in @('wuauserv', 'UsoSvc', 'WaaSMedicSvc', 'DoSvc')) {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$s'" -ErrorAction SilentlyContinue
    if ($svc) { Write-Host ("        {0,-13} {1,-8} {2}" -f $svc.Name, $svc.State, $svc.StartMode) }
}

Write-Host ''
Write-Host '  [4/6] 移除“永不检查更新”策略 ...' -ForegroundColor Cyan
foreach ($n in @('NoAutoUpdate', 'AUOptions')) {
    try { Remove-ItemProperty -Path $au -Name $n -Force -ErrorAction Stop; Write-Host "        已移除 $n" }
    catch { Write-Host "        跳过 $n（原本未设置）" -ForegroundColor DarkGray }
}
Write-Host '        保留 NoAutoRebootWithLoggedOnUsers = 1（仍然不自动重启）' -ForegroundColor Green

Write-Host ''
Write-Host '  [5/6] 恢复更新相关计划任务 ...' -ForegroundColor Cyan
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
Write-Host '  [6/6] 刷新策略 ...' -ForegroundColor Cyan
$null = gpupdate /force 2>&1
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  ----------------------------------------------------------------' -ForegroundColor Yellow
Write-Host '   现在可以打开：设置 → Windows 更新 → 检查更新' -ForegroundColor White
Write-Host '   装完更新后，请再运行本软件点「一键锁死」重新锁定。' -ForegroundColor White
Write-Host '   （更新装完也不会自己重启，仍然需要你手动重启）' -ForegroundColor White
Write-Host '  ----------------------------------------------------------------' -ForegroundColor Yellow
Write-Host ''
exit 0
