<#
  App Factory - Fase 1 - Diagnostico de hardware e ferramentas (somente leitura).
  Nao altera nenhuma configuracao do sistema. Nao coleta nome de usuario nem nome da maquina.
  Uso (PowerShell, na raiz do projeto):
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\diagnostics\measure-hardware.ps1
  Saida: .appfactory\runtime\hardware\snapshot-<data>.json  (pasta ignorada pelo Git)
#>
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$outDir = Join-Path $root '.appfactory\runtime\hardware'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outFile = Join-Path $outDir "snapshot-$stamp.json"

function Try-Cmd([string]$exe, [string[]]$argv) {
  $cmd = Get-Command $exe -ErrorAction SilentlyContinue
  if (-not $cmd) { return @{ found = $false } }
  try { $out = & $exe @argv 2>&1 | Out-String } catch { $out = "ERRO: $($_.Exception.Message)" }
  return @{ found = $true; path = $cmd.Source; output = $out.Trim() }
}

# --- Sistema ---
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$system = [ordered]@{
  os_caption = $os.Caption; os_version = $os.Version; os_build = $os.BuildNumber; os_arch = $os.OSArchitecture
  manufacturer = $cs.Manufacturer; model = $cs.Model
  powershell = $PSVersionTable.PSVersion.ToString()
  uptime_hours = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours, 1)
}

# --- CPU (uso amostrado 5x, 1s) ---
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$samples = @()
for ($i = 0; $i -lt 5; $i++) {
  $p = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
  $samples += [int]$p.PercentProcessorTime
  Start-Sleep -Seconds 1
}
$cpuInfo = [ordered]@{
  name = $cpu.Name.Trim(); cores = $cpu.NumberOfCores; logical_processors = $cpu.NumberOfLogicalProcessors
  max_clock_mhz = $cpu.MaxClockSpeed; current_clock_mhz = $cpu.CurrentClockSpeed
  usage_samples_pct = $samples; usage_avg_pct = [math]::Round(($samples | Measure-Object -Average).Average, 1)
}

# --- RAM ---
$dimms = Get-CimInstance Win32_PhysicalMemory
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$ram = [ordered]@{
  installed_gb = [math]::Round((($dimms | Measure-Object Capacity -Sum).Sum) / 1GB, 2)
  visible_total_gb = $totalGB; available_gb = $freeGB
  used_gb = [math]::Round($totalGB - $freeGB, 2); used_pct = [math]::Round((($totalGB - $freeGB) / $totalGB) * 100, 1)
  commit_limit_gb = [math]::Round($os.TotalVirtualMemorySize / 1MB, 2); commit_free_gb = [math]::Round($os.FreeVirtualMemory / 1MB, 2)
  modules = @($dimms | ForEach-Object { [ordered]@{ capacity_gb = [math]::Round($_.Capacity / 1GB, 1); speed_mhz = $_.Speed; configured_speed_mhz = $_.ConfiguredClockSpeed; smbios_type = $_.SMBIOSMemoryType } })
}

# --- GPU ---
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { [ordered]@{ name = $_.Name; driver = $_.DriverVersion; adapter_ram_bytes_capped = $_.AdapterRAM } })
$nvq = Try-Cmd 'nvidia-smi' @('--query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,pstate', '--format=csv,noheader,nounits')
$nvApps = Try-Cmd 'nvidia-smi' @('--query-compute-apps=process_name,used_memory', '--format=csv,noheader,nounits')
$nvFull = Try-Cmd 'nvidia-smi' @()
$gpu = [ordered]@{ video_controllers = $gpus; nvidia_query = $nvq; nvidia_compute_apps = $nvApps; nvidia_smi_full = $nvFull }

# --- Disco ---
$disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
  [ordered]@{ drive = $_.DeviceID; fs = $_.FileSystem; size_gb = [math]::Round($_.Size / 1GB, 1); free_gb = [math]::Round($_.FreeSpace / 1GB, 1) } })
$phys = @(Get-PhysicalDisk | ForEach-Object { [ordered]@{ model = $_.FriendlyName; media = "$($_.MediaType)"; bus = "$($_.BusType)"; size_gb = [math]::Round($_.Size / 1GB, 1) } })

# --- Energia / bateria / temperatura ---
$bat = Get-CimInstance Win32_Battery | Select-Object -First 1
$power = [ordered]@{
  has_battery = [bool]$bat
  battery_charge_pct = $bat.EstimatedChargeRemaining
  battery_status_code = $bat.BatteryStatus
  battery_status_note = '1=descarregando(bateria) 2=na tomada 3..9=outros (Win32_Battery)'
  power_scheme = (powercfg /getactivescheme 2>&1 | Out-String).Trim()
}
$tz = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature
$thermal = [ordered]@{ acpi_zones_celsius = @($tz | ForEach-Object { [math]::Round($_.CurrentTemperature / 10 - 273.15, 1) }); note = 'Vazio = requer administrador ou nao exposto pelo firmware' }

# --- Atividade do usuario (segundos desde a ultima entrada) ---
$idle = $null
try {
  Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class AFIdle {
  [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO p);
  public static uint Seconds() { var l = new LASTINPUTINFO(); l.cbSize = (uint)Marshal.SizeOf(l); GetLastInputInfo(ref l); return ((uint)Environment.TickCount - l.dwTime) / 1000; }
}
'@
  $idle = [AFIdle]::Seconds()
} catch { $idle = "indisponivel" }

# --- Processos que mais usam memoria (somente nomes e MB) ---
$top = @(Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 | ForEach-Object { [ordered]@{ name = $_.ProcessName; ram_mb = [math]::Round($_.WorkingSet64 / 1MB) } })

# --- Ferramentas ---
$env:WSL_UTF8 = '1'
$tools = [ordered]@{
  git = Try-Cmd 'git' @('--version'); gh = Try-Cmd 'gh' @('--version')
  python = Try-Cmd 'python' @('--version'); py_launcher = Try-Cmd 'py' @('-0p')
  node = Try-Cmd 'node' @('--version'); npm = Try-Cmd 'npm' @('--version'); pnpm = Try-Cmd 'pnpm' @('--version')
  uv = Try-Cmd 'uv' @('--version')
  docker = Try-Cmd 'docker' @('--version'); docker_info = Try-Cmd 'docker' @('info', '--format', '{{.ServerVersion}} {{.OperatingSystem}}')
  wsl_status = Try-Cmd 'wsl' @('--status'); wsl_list = Try-Cmd 'wsl' @('-l', '-v')
  ollama = Try-Cmd 'ollama' @('--version'); ollama_list = Try-Cmd 'ollama' @('list'); ollama_ps = Try-Cmd 'ollama' @('ps')
}
$ollamaApi = $null
try { $ollamaApi = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 } catch { $ollamaApi = "sem resposta: $($_.Exception.Message)" }
$ollamaEnv = [ordered]@{
  OLLAMA_MODELS = $env:OLLAMA_MODELS; OLLAMA_MAX_LOADED_MODELS = $env:OLLAMA_MAX_LOADED_MODELS
  OLLAMA_NUM_PARALLEL = $env:OLLAMA_NUM_PARALLEL; OLLAMA_KEEP_ALIVE = $env:OLLAMA_KEEP_ALIVE
  OLLAMA_FLASH_ATTENTION = $env:OLLAMA_FLASH_ATTENTION; OLLAMA_KV_CACHE_TYPE = $env:OLLAMA_KV_CACHE_TYPE
}

$result = [ordered]@{
  schema_version = 1
  measured_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
  system = $system; cpu = $cpuInfo; ram = $ram; gpu = $gpu
  disks = $disks; physical_disks = $phys; power = $power; thermal = $thermal
  user_idle_seconds = $idle; top_processes_by_ram = $top
  tools = $tools; ollama_api_version = $ollamaApi; ollama_env = $ollamaEnv
}
$result | ConvertTo-Json -Depth 8 | Out-File -FilePath $outFile -Encoding utf8
Write-Host "OK - snapshot salvo em: $outFile"
Write-Host ("CPU {0} | {1} nucleos / {2} threads | uso medio {3}%" -f $cpuInfo.name, $cpuInfo.cores, $cpuInfo.logical_processors, $cpuInfo.usage_avg_pct)
Write-Host ("RAM total {0} GB | disponivel {1} GB | uso {2}%" -f $ram.visible_total_gb, $ram.available_gb, $ram.used_pct)
if ($nvq.found) { Write-Host "GPU (nvidia-smi): $($nvq.output)" } else { Write-Host "nvidia-smi NAO encontrado" }
