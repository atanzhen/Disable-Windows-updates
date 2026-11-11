param([int]$IntervalMinutes = 30)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$VER   = '1.1.0'
$src   = $PSScriptRoot
$dir   = 'C:\ProgramData\NoAutoRestart'
$task  = 'NoAutoRestartGuard'
$psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$au    = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'

$isAdmin = [bool](([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
if (-not $isAdmin) { Write-Host '  错误：需要管理员权限才能部署。' -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 系统信息
$os      = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$build   = 0
if ($os) { try { $build = [int]$os.BuildNumber } catch { $build = 0 } }
$editionId = ''
$display   = ''
try {
    $cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction Stop
    $editionId = "$($cv.EditionID)"
    $display   = "$($cv.DisplayVersion)"
} catch { }

$map = @{
    'Core' = '家庭版'; 'CoreSingleLanguage' = '家庭单语言版'; 'CoreCountrySpecific' = '家庭中文版'
    'Professional' = '专业版'; 'ProfessionalN' = '专业版 N'; 'ProfessionalWorkstation' = '专业工作站版'
    'ProfessionalEducation' = '专业教育版'; 'Enterprise' = '企业版'; 'EnterpriseN' = '企业版 N'
    'EnterpriseS' = '企业版 LTSC'; 'EnterpriseSN' = '企业版 LTSC N'
    'Education' = '教育版'; 'EducationN' = '教育版 N'
    'IoTEnterprise' = 'IoT 企业版'; 'ServerStandard' = 'Server 标准版'
    'ServerDatacenter' = 'Server 数据中心版'; 'Ultimate' = '旗舰版'; 'Starter' = '简易版'
}
$edName = $map[$editionId]
if (-not $edName) { $edName = $editionId }
if (-not $edName) { $edName = '未知版本' }

if ($build -ge 22000)     { $fam = 'Windows 11' }
elseif ($build -ge 10240) { $fam = 'Windows 10' }
else                      { $fam = '旧版 Windows' }

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor Cyan
Write-Host '   禁止自动重启工具 v1.1.0   正在部署' -ForegroundColor Cyan
Write-Host '  ================================================================' -ForegroundColor Cyan

Write-Host ''
Write-Host '  [1/6] 检测系统环境 ...' -ForegroundColor Cyan
Write-Host ("        系统      : {0} {1} (Build {2} {3})" -f $fam, $edName, $build, $display)
Write-Host ("        PowerShell: {0}" -f $PSVersionTable.PSVersion)
if ($build -ge 10240) {
    Write-Host '        兼容性    : 受支持（Win10 / Win11 全版本）' -ForegroundColor Green
} else {
    Write-Host '        兼容性    : 系统版本较低，仅应用可用部分策略' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '  [2/6] 安装守护脚本到 C:\ProgramData\NoAutoRestart ...' -ForegroundColor Cyan
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$guardSrc = Join-Path $src 'guard.ps1'
if (-not (Test-Path $guardSrc)) { Write-Host "        错误：缺少 $guardSrc" -ForegroundColor Red; exit 1 }
Copy-Item $guardSrc (Join-Path $dir 'guard.ps1') -Force
Set-Content -Path (Join-Path $dir 'guard-version.txt') -Value $VER -Encoding ASCII -Force
Remove-Item (Join-Path $dir 'UPDATE_MODE.flag') -Force -ErrorAction SilentlyContinue
Write-Host '        完成（脚本已固化到系统，与主程序是否保留无关）' -ForegroundColor Green

Write-Host ''
Write-Host ("  [3/6] 注册计划任务（SYSTEM 权限，开机 + 每 {0} 分钟）..." -f $IntervalMinutes) -ForegroundColor Cyan

$psArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$dir\guard.ps1`" -Silent"
$desc   = '保持“禁止自动更新、禁止自动重启”的设置不被系统改回。'
$registered = $false
$how = ''

# 方式一：计划任务模块（不依赖外部程序，Win10 / Win11 全版本可用）
for ($i = 0; $i -lt 2 -and -not $registered; $i++) {
    try {
        $action = New-ScheduledTaskAction -Execute $psExe -Argument $psArgs
        $tBoot  = New-ScheduledTaskTrigger -AtStartup
        if ($i -eq 0) {
            $tRep = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
                        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
                        -RepetitionDuration (New-TimeSpan -Days 3650)
        } else {
            # 个别版本不接受过长的重复时长，退回“无限重复”
            $tRep = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
                        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
        }
        $prin = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        $set  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
        $set.Hidden = $true
        Register-ScheduledTask -TaskName $task -Action $action -Trigger @($tBoot, $tRep) `
            -Principal $prin -Settings $set -Force -Description $desc -ErrorAction Stop | Out-Null
        $registered = $true
        $how = '模块 API'
    } catch { }
}

# 方式二：任务 XML（极少数环境模块不可用时兜底）
if (-not $registered) {
    $start = (Get-Date).AddMinutes(1).ToString('yyyy-MM-ddTHH:mm:ss')
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>NoAutoRestartGuard</Author>
    <Description>$desc</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT1M</Delay>
    </BootTrigger>
    <CalendarTrigger>
      <StartBoundary>$start</StartBoundary>
      <Enabled>true</Enabled>
      <Repetition>
        <Interval>PT${IntervalMinutes}M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartIfOnBatteries>true</AllowStartIfOnBatteries>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$psExe</Command>
      <Arguments>-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "$dir\guard.ps1" -Silent</Arguments>
    </Exec>
  </Actions>
</Task>
"@
    $xmlPath = Join-Path $env:TEMP 'noautorestart-guard.xml'
    Set-Content -Path $xmlPath -Value $xml -Encoding Unicode -Force
    $null = & schtasks /Create /TN "\$task" /XML "$xmlPath" /F 2>&1
    if ($LASTEXITCODE -eq 0) { $registered = $true; $how = '任务 XML' }
    Remove-Item $xmlPath -Force -ErrorAction SilentlyContinue
}

if (-not $registered) {
    Write-Host '        计划任务注册失败，请把本窗口内容反馈给作者。' -ForegroundColor Red
    exit 1
}

# 若任务被系统禁用过，重新启用
$t0 = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if ($t0 -and $t0.State -eq 'Disabled') {
    try { Enable-ScheduledTask -TaskName $task -ErrorAction Stop | Out-Null } catch { }
}
@(
    "deployed=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "version=$VER",
    "task=$task",
    "how=$how"
) | Set-Content (Join-Path $dir 'deployed.txt') -Encoding utf8
Write-Host ("        完成（{0}）" -f $how) -ForegroundColor Green

Write-Host ''
Write-Host '  [4/6] 立即执行加固 ...' -ForegroundColor Cyan
& $psExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dir 'guard.ps1') -Silent
Write-Host '        完成' -ForegroundColor Green

Write-Host ''
Write-Host '  [5/6] 逐项校验 ...' -ForegroundColor Cyan
$t = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if ($t) { Write-Host ("        守护任务  : 已注册 / {0}" -f $t.State) -ForegroundColor Green }
else    { Write-Host  '        守护任务  : 未找到' -ForegroundColor Red }

foreach ($s in @('wuauserv', 'UsoSvc', 'WaaSMedicSvc', 'DoSvc')) {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$s'" -ErrorAction SilentlyContinue
    if ($svc) { Write-Host ("        服务      : {0,-13} {1,-8} {2}" -f $svc.Name, $svc.State, $svc.StartMode) }
}
foreach ($n in @('NoAutoUpdate', 'NoAutoRebootWithLoggedOnUsers', 'AlwaysAutoRebootAtScheduledTime')) {
    $v = 'MISSING'
    try { $v = (Get-ItemProperty -Path $au -Name $n -ErrorAction Stop).$n } catch { }
    Write-Host ("        策略      : {0,-32} = {1}" -f $n, $v)
}
$cr = 'MISSING'
try { $cr = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl' -Name AutoReboot -ErrorAction Stop).AutoReboot } catch { }
Write-Host ("        策略      : {0,-32} = {1}" -f 'CrashControl.AutoReboot', $cr)
Write-Host ("        巡检记录  : {0}" -f (Join-Path $dir 'last-run.txt'))

Write-Host ''
Write-Host '  [6/6] 完成' -ForegroundColor Green
Write-Host ''
Write-Host '  ================================================================' -ForegroundColor Green
Write-Host '   已成功禁用自动更新与自动重启' -ForegroundColor Green
Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '   现在打开  设置 → Windows 更新  会显示：' -ForegroundColor Yellow
Write-Host '     “出现错误，请尝试稍后重新打开设置。”' -ForegroundColor Yellow
Write-Host '   这是正常现象 —— 更新引擎已被停用，不是系统故障。' -ForegroundColor Yellow
Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '   · 只有你自己手动点「重启 / 关机」，电脑才会重启。' -ForegroundColor White
Write-Host '   · 设置已写入系统，关闭本软件、删除本软件都不影响，电脑照常使用。' -ForegroundColor White
Write-Host '   · 以后重新下载本软件运行，仍会识别当前状态并继续生效。' -ForegroundColor White
Write-Host '  ================================================================' -ForegroundColor Green
Write-Host ''
exit 0
