param([switch]$Silent)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$VER  = '1.1.0'
$dir  = 'C:\ProgramData\NoAutoRestart'
$log  = Join-Path $dir 'guard.log'
$flag = Join-Path $dir 'UPDATE_MODE.flag'
$last = Join-Path $dir 'last-run.txt'
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
Set-Content -Path (Join-Path $dir 'guard-version.txt') -Value $VER -Encoding ASCII -Force

# ---------- 采集系统信息，供主程序判断兼容性 ----------
$os      = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$build   = 0
$caption = ''
if ($os) {
    try { $build = [int]$os.BuildNumber } catch { $build = 0 }
    $caption = "$($os.Caption)"
}
$edition = ''
try { $edition = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -Name EditionID -ErrorAction Stop).EditionID } catch { }
@(
    "caption=$caption",
    "build=$build",
    "edition=$edition",
    "powershell=$($PSVersionTable.PSVersion)",
    "guard=$VER",
    "checked=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
) | Set-Content (Join-Path $dir 'sysinfo.txt') -Encoding UTF8

# ---------- 更新模式：守护任务主动休眠 ----------
if (Test-Path $flag) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  skipped (UPDATE_MODE.flag present)" | Set-Content $last -Encoding utf8
    exit 0
}

$changes = New-Object System.Collections.Generic.List[string]

function SetStrictDword([string]$path, [string]$name, [int]$val) {
    if (-not (Test-Path $path)) {
        try { New-Item -Path $path -Force -ErrorAction Stop | Out-Null } catch { $changes.Add("KEY-FAIL  $path"); return }
    }
    $cur = 'MISSING'
    try { $cur = (Get-ItemProperty -Path $path -Name $name -ErrorAction Stop).$name } catch { }
    if ("$cur" -eq "$val") { return }
    try {
        New-ItemProperty -Path $path -Name $name -Value $val -PropertyType DWord -Force -ErrorAction Stop | Out-Null
        $changes.Add("REG-REPAIR  $name : $cur -> $val")
    } catch {
        $changes.Add("REG-FAILED  $name")
    }
}

function GetSvcStart([string]$n) {
    try { return [int](Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$n" -Name Start -ErrorAction Stop).Start } catch { return -1 }
}

function SetSvcMode([string]$n, [string]$mode) {
    $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$n"
    if (-not (Test-Path $key)) { return 'absent' }
    $want = 3
    if ($mode -eq 'disabled') { $want = 4 }
    if ($mode -eq 'auto')     { $want = 2 }
    if ((GetSvcStart $n) -eq $want) { return 'ok' }

    if ($want -eq 4) {
        $s = Get-Service -Name $n -ErrorAction SilentlyContinue
        if ($s -and $s.Status -eq 'Running') {
            $null = & sc.exe stop $n 2>&1
            Start-Sleep -Milliseconds 700
        }
    }
    # 先走 SCM，失败再直接写注册表（部分被保护的服务只认其中一条路）
    $null = & sc.exe config $n start= $mode 2>&1
    if ((GetSvcStart $n) -ne $want) {
        try { Set-ItemProperty $key -Name Start -Value $want -Type DWord -Force -ErrorAction Stop } catch { }
    }
    if ((GetSvcStart $n) -eq $want) { return 'fixed' }
    return 'failed'
}

# ================= 1. Windows 更新策略（家庭版 / 专业版 / 企业版 通用） =================
$au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
SetStrictDword $au 'NoAutoUpdate'                    1
SetStrictDword $au 'AUOptions'                       1
SetStrictDword $au 'NoAutoRebootWithLoggedOnUsers'   1
SetStrictDword $au 'AlwaysAutoRebootAtScheduledTime' 0
SetStrictDword $au 'AutoInstallMinorUpdates'         0
SetStrictDword $au 'RebootRelaunchTimeoutEnabled'    0
SetStrictDword 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' 'SetDisableUXWUAccess' 0

# ================= 2. 界面层：重启只通知，不自动执行 =================
$ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
SetStrictDword $ux 'IsExpedited'                  0
SetStrictDword $ux 'RestartNotificationsAllowed2' 1
SetStrictDword $ux 'SmartActiveHoursState'        0
SetStrictDword $ux 'ActiveHoursStart'             6
SetStrictDword $ux 'ActiveHoursEnd'               23

# ================= 3. 任何路径都不自动重启 =================
SetStrictDword 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl' 'AutoReboot' 0
SetStrictDword 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'DisableAutomaticRestartSignOn' 1

# ================= 4. 服务（不存在的服务自动跳过，兼容各版本） =================
foreach ($n in @('wuauserv', 'UsoSvc', 'WaaSMedicSvc')) {
    $r = SetSvcMode $n 'disabled'
    if ($r -eq 'fixed')  { $changes.Add("SVC-DISABLE $n") }
    if ($r -eq 'failed') { $changes.Add("SVC-FAILED  $n (受系统保护，策略已生效)") }
}
$null = SetSvcMode 'DoSvc' 'demand'   # 传递优化降为手动，不再后台抢带宽

# ================= 5. 禁用更新 / 重启相关的全部计划任务 =================
$paths = @(
    '\Microsoft\Windows\UpdateOrchestrator\',
    '\Microsoft\Windows\WindowsUpdate\',
    '\Microsoft\Windows\InstallService\',
    '\Microsoft\Windows\WaaSMedic\'
)
$list = New-Object System.Collections.Generic.List[object]
foreach ($p in $paths) {
    try { Get-ScheduledTask -TaskPath $p -ErrorAction Stop | ForEach-Object { $list.Add($_) } } catch { }
}

if ($list.Count -gt 0) {
    foreach ($t in $list) {
        if ($t.State -eq 'Disabled') { continue }
        $full = "$($t.TaskPath)$($t.TaskName)"
        try {
            Disable-ScheduledTask -TaskPath $t.TaskPath -TaskName $t.TaskName -ErrorAction Stop | Out-Null
            $changes.Add("TASK-DISABLE $full")
        } catch {
            $null = & schtasks /Change /TN "$full" /Disable 2>&1
            if ($LASTEXITCODE -eq 0) { $changes.Add("TASK-DISABLE $full") }
            else { $changes.Add("TASK-FAILED  $full (受系统保护)") }
        }
    }
} else {
    # 极老版本没有 ScheduledTasks 模块时退回 schtasks
    foreach ($full in @(
        '\Microsoft\Windows\UpdateOrchestrator\Reboot',
        '\Microsoft\Windows\UpdateOrchestrator\Reboot_AC',
        '\Microsoft\Windows\UpdateOrchestrator\Reboot_Battery',
        '\Microsoft\Windows\UpdateOrchestrator\Schedule Scan',
        '\Microsoft\Windows\UpdateOrchestrator\USO_UxBroker',
        '\Microsoft\Windows\UpdateOrchestrator\Universal Orchestrator Start',
        '\Microsoft\Windows\WindowsUpdate\sih',
        '\Microsoft\Windows\WindowsUpdate\sihboot',
        '\Microsoft\Windows\WindowsUpdate\Scheduled Start',
        '\Microsoft\Windows\WaaSMedic\PerformRemediation'
    )) {
        $null = & schtasks /Change /TN "$full" /Disable 2>&1
        if ($LASTEXITCODE -eq 0) { $changes.Add("TASK-DISABLE $full") }
    }
}

# ================= 6. 自愈：确保守护任务本身没被停用 =================
$self = Get-ScheduledTask -TaskName 'NoAutoRestartGuard' -ErrorAction SilentlyContinue
if (-not $self) {
    $changes.Add('GUARD-TASK-MISSING  守护任务丢失，请重新运行主程序点「一键锁死」')
} elseif ($self.State -eq 'Disabled') {
    try { Enable-ScheduledTask -TaskName 'NoAutoRestartGuard' -ErrorAction Stop | Out-Null; $changes.Add('GUARD-TASK 已自动重新启用') } catch { }
}

# ================= 7. 日志 =================
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 512KB)) {
    $tail = Get-Content $log -Tail 300
    $tail | Set-Content $log -Encoding utf8
}

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
if ($changes.Count -gt 0) {
    "===== $stamp  REPAIRED $($changes.Count) item(s) =====" | Add-Content $log -Encoding utf8
    foreach ($c in $changes) { "    $c" | Add-Content $log -Encoding utf8 }
} elseif (-not $Silent) {
    "===== $stamp  all settings already OK =====" | Add-Content $log -Encoding utf8
}
"$stamp  changes=$($changes.Count)" | Set-Content $last -Encoding utf8

if (-not $Silent) {
    if ($changes.Count -gt 0) {
        foreach ($c in $changes) { Write-Host "  $c" }
    } else {
        Write-Host '  所有设置均已生效，无需修复'
    }
}
exit 0
