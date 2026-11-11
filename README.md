# 禁止自动重启工具

> 把「什么时候重启、什么时候关机」的决定权交还给你的 Windows 小工具。
> 彻底禁止自动更新与自动重启，设置写入系统后长期生效。

**版本** `v1.1.0` · **平台** Windows 10 / 11 全版本 · **许可** 永久免费 · 开放源码 · **出品** [atusu.cn](https://atusu.cn)

软件包自行从  [Releases](https://github.com/atanzhen/Disable-Windows-updates/releases/tag/v1.1.0)下载

从网盘下载: https://pan.baidu.com/s/1HxR_ynTRGc7k0hCIuJuoDg?pwd=2xm9 提取码: 2xm9 

---

## 目录

- [简介](#简介)
- [功能特性](#功能特性)
- [支持系统](#支持系统)
- [快速开始](#快速开始)
- [三个按钮分别是做什么的](#三个按钮分别是做什么的)
- [锁死之后会看到什么](#锁死之后会看到什么)
- [为什么删掉程序设置依然有效](#为什么删掉程序设置依然有效)
- [不影响什么](#不影响什么)
- [目录结构](#目录结构)
- [从源码构建](#从源码构建)
- [技术原理](#技术原理)
- [兼容性处理](#兼容性处理)
- [常见问题](#常见问题)
- [恢复与卸载](#恢复与卸载)
- [开源许可](#开源许可)
- [免责声明](#免责声明)

---

## 简介

Windows 更新会在你工作、开会、渲染、挂机的时候强制重启，丢掉没保存的东西。
本工具把这件事变成：**只有你手动点「重启」，电脑才会重启**。

它不改系统镜像、不装驱动、不常驻后台，只做三件事：

1. 关掉 Windows 更新引擎（检查 / 下载 / 安装全部停止）；
2. 堵死所有自动重启路径（更新、蓝屏、计划任务、开机续装）；
3. 留一个 SYSTEM 守护任务，每 30 分钟检查设置有没有被系统改回去。

---

## 功能特性

| 特性 | 说明 |
|---|---|
| 禁止自动更新 | 关闭自动检查、自动下载、自动安装；Windows Update / 更新协调器 / 更新修复服务三个引擎全部停用 |
| 禁止自动重启 | 更新装完、蓝屏崩溃、计划任务、开机续装，四条路径全部堵死 |
| 自愈守护 | SYSTEM 权限计划任务，开机 + 每 30 分钟巡检，被系统改回来自动修复并记日志 |
| 取消更新计划 | `UpdateOrchestrator` / `WindowsUpdate` / `InstallService` / `WaaSMedic` 下 20 多个任务全部禁用 |
| 设置固化 | 写入注册表 + 服务 + 计划任务，不常驻后台，删掉程序也生效 |
| 随时还原 | 「恢复配置」一键取消全部改动，回到 Windows 默认状态 |
| 零依赖 | 不联网、不上传数据、无遥测、无开机自启项 |

---

## 支持系统

- **Windows 11**：21H2 / 22H2 / 23H2 / 24H2 及后续版本
- **Windows 10**：1507 起的全部版本（含 1809 / 1909 / 21H2 / 22H2）
- **版本类型**：家庭版、家庭单语言版、家庭中文版、专业版、专业工作站版、企业版、教育版、企业版 LTSC、IoT 企业版
- **服务器**：Windows Server 2016 / 2019 / 2022（策略同上）
- **架构**：x86 / x64 / ARM64

> 系统里不存在的服务或计划任务会自动跳过，不会报错。程序启动时会在「系统环境」一栏显示当前系统与兼容性。

---

## 快速开始

```text
1. 双击 禁止自动重启工具.exe      → UAC 弹窗点「是」
2. 点「一键禁用更新和重启」                 → 五项状态全部变绿
                                    → 主按钮变绿显示「已配置完成锁定」
3. 之后不用管它，程序无需常驻
```

需要打补丁时：点「临时恢复更新」→ 设置里检查更新 → 装完再点「一键禁用更新和重启」。

---

## 三个按钮分别是做什么的

| 按钮 | 作用 |
|---|---|
| **一键禁用更新和重启** | 禁止自动更新与自动重启，并把设置写进系统长期生效。第一次使用点它。配置成功后按钮变为绿色 **「已配置完成锁定」**，不可再点。 |
| **临时恢复更新** | 只放开更新，**自动重启仍然禁止**。装完补丁后再点主按钮锁回去。**仅在已启用锁定时可用**，未启用时灰显。 |
| **恢复配置** | 取消本程序的全部设置，回到 Windows 默认状态：删除守护任务与程序数据、恢复更新服务、删除**本工具自己写入的**注册表策略（系统其它注册表项不动）。**自动重启也会恢复默认**。执行前有二次确认。**仅在已启用锁定时可用**，未启用时灰显。 |

辅助按钮：

| 按钮 | 作用 |
|---|---|
| **查看日志** | 守护任务只在修复了被篡改的设置时才写记录，空日志＝一切正常。 |
| **使用说明** | 软件内完整帮助（支持系统、按钮说明、副作用、免责）。 |

---

## 锁死之后会看到什么

打开 **设置 → Windows 更新**，会显示：

> 出现错误，请尝试稍后重新打开设置。

**这是预期现象**：更新引擎已被停用，设置页读不到更新状态。它不是系统故障，不影响电脑运行、不影响装软件、不影响日常使用。

---

## 为什么删掉程序设置依然有效

所有改动都直接写进系统三层，与 exe 位置无关：

```text
注册表策略   HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU
服务          wuauserv / UsoSvc / WaaSMedicSvc 的启动类型
计划任务      NoAutoRestartGuard（SYSTEM，开机 + 每 30 分钟）
守护脚本      C:\ProgramData\NoAutoRestart\guard.ps1
```

所以：关掉程序 → 有效；删掉程序 → 有效；以后重新下载运行 → 自动识别当前状态，接着用。

---

## 不影响什么

本次完全没有改动以下部分，保持原样：

- **CBS / TrustedInstaller** —— 启用或关闭 Windows 功能、安装系统组件正常
- **Windows Installer (msiserver)** —— 安装 `.msi` 软件正常
- **BITS 后台传输服务** —— 下载行为正常
- **驱动** —— 显卡、声卡、网卡、打印机安装正常
- **系统还原、其他服务与注册表** —— 未改动

唯一被改动的是「更新引擎」和「自动重启」，也就是本软件存在的意义。

---

## 目录结构

```text
禁止自动重启工具 v1.1.0/
├─ 禁止自动重启工具.exe     主程序（单文件，无需安装）
├─ 使用说明.txt             用户手册
├─ README.md                本文件（开源说明 / 构建说明）
└─ 源码/
   ├─ main.py               图形界面（PySide6）
   ├─ build.bat             一键打包（PyInstaller）
   ├─ ensure_bom.py         修正 ps1 编码
   ├─ make_icon.py          生成图标（Pillow 绘制）
   ├─ version.txt           exe 版本资源
   ├─ app.ico / icon_preview.png
   └─ scripts/
      ├─ guard.ps1          加固核心（守护任务执行）
      ├─ deploy.ps1         部署 + 校验
      ├─ restore.ps1        临时恢复更新
      └─ reset.ps1          恢复配置（彻底还原）
```

---

## 从源码构建

```bat
pip install PySide6 pyinstaller pillow
python ensure_bom.py
python make_icon.py
python -m PyInstaller --onefile --windowed --uac-admin ^
  --name NoAutoRestartTool --icon app.ico ^
  --version-file version.txt ^
  --add-data "scripts;scripts" ^
  --add-data "icon_preview.png;." --add-data "app.ico;." main.py
```

或直接双击 `build.bat`。

> **注意**：`scripts` 下的 `.ps1` 必须为 **UTF-8 带 BOM**。
> PowerShell 5.1 会把无 BOM 的 UTF-8 当 ANSI 解析，中文会乱码（`ensure_bom.py` 负责处理）。

---

## 技术原理

| 层 | 内容 |
|---|---|
| 注册表策略 | `WindowsUpdate\AU`：`NoAutoUpdate=1`、`AUOptions=1`、`NoAutoRebootWithLoggedOnUsers=1`、`AlwaysAutoRebootAtScheduledTime=0`、`AutoInstallMinorUpdates=0`、`RebootRelaunchTimeoutEnabled=0` |
| 注册表 UX | `WindowsUpdate\UX\Settings`：`IsExpedited=0`、`RestartNotificationsAllowed2=1`、`SmartActiveHoursState=0`、`ActiveHours 6–23` |
| 服务 | `wuauserv` / `UsoSvc` / `WaaSMedicSvc` → 禁用；`DoSvc` → 手动 |
| 计划任务 | 四个更新相关目录下的任务全部禁用 |
| 崩溃 / 登录 | `CrashControl.AutoReboot=0`、`DisableAutomaticRestartSignOn=1` |

**WaaSMedicSvc 是关键**：它专门负责把被关掉的更新服务「修」回来。不一起禁掉，`wuauserv` 会被复活——这也是多数同类工具失效的原因。

---

## 兼容性处理

- 不存在的服务 / 计划任务**自动跳过**，不会因版本差异报错
- 服务启动类型先走 SCM（`sc config`），失败再直接写注册表 `Services\<名>\Start`
- 计划任务优先用 `ScheduledTasks` 模块注册，失败退回任务 XML
- 家庭版无组策略编辑器，直接写注册表策略同样生效
- 任务是否已部署，直接查 `%SystemRoot%\System32\Tasks\NoAutoRestartGuard`，不依赖 `schtasks.exe`

---

## 常见问题

**Q：点「一键禁用更新和重启」提示执行失败？**
多半没有管理员权限。右键 exe → 「以管理员身份运行」。

**Q：「守护任务」显示"版本过期"？**
系统里部署的是旧版守护脚本，重新点一次「一键禁用更新和重启」即可更新。

**Q：会被 Windows 改回去吗？**
Windows 的更新修复服务、大版本升级确实会尝试恢复设置。守护任务每 30 分钟比对一次，被改回来自动修回；「查看日志」能看到每次修复记录。

**Q：怎么确认它真的在跑？**
点「查看日志」，或看 `C:\ProgramData\NoAutoRestart\last-run.txt` 的修改时间（每 30 分钟刷新）。

**Q：会不会影响升级 Windows 大版本？**
大版本升级需要更新服务，请先点「临时恢复更新」再升级，升级完再锁回去。

**Q：Store 应用更新、Defender 病毒库还能更新吗？**
会一并停止。需要时点「临时恢复更新」，更新完再锁回去。

---

## 恢复与卸载

**只恢复更新**（保留防自动重启）：点「临时恢复更新」。

**彻底还原系统**：点「恢复配置」，二次确认后会自动：

1. 删除守护计划任务 `NoAutoRestartGuard`
2. 更新服务恢复默认，本程序写入的注册表策略删除（系统其它注册表项不动）
3. 更新与重启相关计划任务重新启用
4. 恢复 `AutoReboot=1`、`DisableAutomaticRestartSignOn=0`
5. 删除 `C:\ProgramData\NoAutoRestart`

之后直接删掉本文件夹即可，系统不留残余。

---

## 开源许可

1. **源码公开**：可查看、学习、修改、自行编译，个人与公司电脑均可使用。
2. **自由分发**：原版或修改版都可转发、放到自己网站上。
3. **保留署名**：再分发须保留版权声明与出处，并附本说明全文。
4. **标明改动**：发布修改版需注明「基于 atusu.cn 的禁止自动重启工具修改」。
5. **禁止售卖**：不得将本软件（含修改版）作为商品出售、付费下载或捆绑收费。
6. **禁止冒名**：不得以本软件名义发布虚假信息、诱导付费，或声称提供官方技术支持。

## 免责声明

本软件按「现状」提供，不附带任何明示或暗示担保。
关闭自动更新意味着系统不再自动获得安全补丁，建议每 1～2 个月手动恢复一次更新。
使用本工具属个人选择，由此产生的安全风险由使用者自行承担。

---

Copyright (C) 2026 atusu.cn · 永久免费 · 开放源码 · 禁止售卖
