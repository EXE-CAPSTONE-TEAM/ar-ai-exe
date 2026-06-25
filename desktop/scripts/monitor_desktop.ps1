# monitor_desktop.ps1
# Script to launch and monitor KusShoes Editor Desktop resources (CPU, RAM, GPU)

# Set working directory to project root
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path $scriptPath -Parent
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$desktopDir = Join-Path $repoRoot "desktop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "        KUSSHOES EDITOR DESKTOP SYSTEM MONITOR" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Repository Root: $repoRoot" -ForegroundColor Gray
Write-Host "Desktop Directory: $desktopDir" -ForegroundColor Gray

# Get number of logical cores for CPU calculation
$numProcessors = $env:NUMBER_OF_PROCESSORS
if (-not $numProcessors) { $numProcessors = 2 }
Write-Host "Cores detected: $numProcessors logical processors" -ForegroundColor Gray

# Recursive function to get all child process IDs
function Get-ProcessDescendants {
    param([int]$ParentId)
    $descendants = @()
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        $descendants += $child.ProcessId
        $descendants += Get-ProcessDescendants -ParentId $child.ProcessId
    }
    return $descendants
}

# Wait for Tauri window process to start from USER
Write-Host "`n[1/2] Dang cho nguoi dung khoi chay ung dung 'kusshoes-editor-desktop'..." -ForegroundColor Yellow
Write-Host "Huong dan: Ban hay chay 'npm run dev' trong thu muc desktop hoac click dup file exe." -ForegroundColor Gray

$appProcess = $null
$timeout = 600 # 10 minutes
$elapsed = 0

while (-not $appProcess -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    $appProcess = Get-Process -Name "kusshoes-editor-desktop" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($elapsed % 15 -eq 0) {
        Write-Host "  Van dang cho ung dung khoi chay... ($elapsed giay / $timeout)" -ForegroundColor Gray
    }
}

if (-not $appProcess) {
    Write-Host "[Error] Khong tim thay tien trinh 'kusshoes-editor-desktop' sau $timeout giay." -ForegroundColor Red
    exit 1
}

$appPid = $appProcess.Id
Write-Host "[2/2] Tim thay ung dung voi PID: $appPid. Bat dau giam sat!" -ForegroundColor Green
Start-Sleep -Seconds 2

# Initial statistics variables
$peakRamBytes = 0
$peakCpuPercent = 0.0
$peakGpuPercent = 0.0

$prevCpuTimes = @{} # hashtable to store process TotalProcessorTime
$prevTicks = [DateTime]::UtcNow.Ticks

# Clear host and show monitor active status
Clear-Host
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "          MONITOR DANG HOAT DONG (REAL-TIME)" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "-> Hay tuong tac voi cua so ung dung KusShoes Editor."
Write-Host "-> Khi ban tat cua so ung dung, script se dung va xuat bao cao."
Write-Host "--------------------------------------------------------"
Write-Host "RAM peak se duoc cap nhat ngay lap tuc."
Write-Host "CPU/GPU se duoc tinh toan qua tung giay."
Write-Host "--------------------------------------------------------"

# Main Monitoring Loop
while ($true) {
    # Check if the main process is still running
    $appInstance = Get-Process -Id $appPid -ErrorAction SilentlyContinue
    if (-not $appInstance) {
        Write-Host "`n[!] Cua so ung dung da dong. Ket thuc giam sat." -ForegroundColor Yellow
        break
    }

    # Retrieve all processes in the tree (Tauri App + Python Sidecar + Blender + etc.)
    $pids = Get-ProcessDescendants -ParentId $appPid
    $pids += $appPid

    $activeProcesses = @()
    foreach ($p in $pids) {
        $pObj = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($pObj) {
            $activeProcesses += $pObj
        }
    }

    # 1. RAM Calculation (Working Set)
    $totalRamBytes = 0
    foreach ($proc in $activeProcesses) {
        $totalRamBytes += $proc.WorkingSet64
    }
    $totalRamMb = [Math]::Round($totalRamBytes / 1MB, 2)
    if ($totalRamBytes -gt $peakRamBytes) {
        $peakRamBytes = $totalRamBytes
    }

    # 2. CPU Calculation
    $currTicks = [DateTime]::UtcNow.Ticks
    $ticksDiff = $currTicks - $prevTicks
    if ($ticksDiff -le 0) { $ticksDiff = 1 }

    $totalCpuPercent = 0.0
    foreach ($proc in $activeProcesses) {
        $pidStr = $proc.Id.ToString()
        try {
            $currCpuTime = $proc.TotalProcessorTime
            if ($prevCpuTimes.ContainsKey($pidStr)) {
                $prevCpuTime = $prevCpuTimes[$pidStr]
                $cpuTimeDiff = $currCpuTime.TotalSeconds - $prevCpuTime.TotalSeconds
                $elapsedSeconds = $ticksDiff / 10000000.0
                if ($elapsedSeconds -gt 0) {
                    $processCpu = ($cpuTimeDiff / $elapsedSeconds) * 100 / $numProcessors
                    $totalCpuPercent += $processCpu
                }
            }
            $prevCpuTimes[$pidStr] = $currCpuTime
        } catch {
            # Skip processes that are terminating or locked
        }
    }
    $prevTicks = $currTicks
    $totalCpuPercent = [Math]::Round($totalCpuPercent, 2)
    if ($totalCpuPercent -gt $peakCpuPercent) {
        $peakCpuPercent = $totalCpuPercent
    }

    # 3. GPU Calculation (Performance Counter)
    $totalGpuPercent = 0.0
    try {
        $samples = Get-Counter '\GPU Engine(pid_*)\Utilization Percentage' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples
        if ($samples) {
            foreach ($p in $pids) {
                $pidStr = "pid_${p}_"
                $gpuSamples = $samples | Where-Object { $_.Path -match $pidStr }
                if ($gpuSamples) {
                    foreach ($sample in $gpuSamples) {
                        $totalGpuPercent += $sample.CookedValue
                    }
                }
            }
        }
    } catch {
        # Counter query fail, keep GPU usage at 0
    }
    $totalGpuPercent = [Math]::Round($totalGpuPercent, 2)
    # Ensure it doesn't exceed 100% per GPU engine unless multiple GPUs are fully active
    if ($totalGpuPercent -gt 100.0) { $totalGpuPercent = 100.0 }
    if ($totalGpuPercent -gt $peakGpuPercent) {
        $peakGpuPercent = $totalGpuPercent
    }

    # Render formatted real-time outputs in single line
    $peakRamMb = [Math]::Round($peakRamBytes / 1MB, 2)
    $printString = [string]::Format("CPU: {0,6}% (Peak: {1,6}%) | RAM: {2,7} MB (Peak: {3,7} MB) | GPU: {4,6}% (Peak: {5,6}%)", $totalCpuPercent, $peakCpuPercent, $totalRamMb, $peakRamMb, $totalGpuPercent, $peakGpuPercent)
    Write-Host -NoNewline "`r$printString"

    Start-Sleep -Seconds 1
}

# 4. Final Review & Report Generation
$peakRamMb = [Math]::Round($peakRamBytes / 1MB, 2)
Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "          REVIEW KET QUA HIEU NANG LON NHAT" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  * RAM cao nhat (Peak RAM):   $peakRamMb MB" -ForegroundColor Yellow
Write-Host "  * CPU cao nhat (Peak CPU):   $peakCpuPercent %" -ForegroundColor Yellow
Write-Host "  * GPU cao nhat (Peak GPU):   $peakGpuPercent %" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# Save report to markdown
$reportPath = Join-Path $repoRoot "desktop_performance_report.md"
$reportContent = @"
# Báo cáo Hiệu năng Desktop App (KusShoes Editor)

Báo cáo chi tiết về tài nguyên hệ thống (RAM, CPU, GPU) tiêu thụ lớn nhất trong suốt quá trình tương tác của người dùng trên phiên bản Desktop.

## Kết quả Đo lường Đỉnh điểm (Peak Performance)

| Chỉ số tài nguyên | Giá trị cao nhất ghi nhận (Peak Value) | Ghi chú |
| :--- | :--- | :--- |
| **RAM** | **$peakRamMb MB** | Tổng dung lượng RAM (Working Set) của Tauri shell và backend sidecar. |
| **CPU** | **$peakCpuPercent %** | Phần trăm CPU trung bình trên tổng số nhân xử lý. |
| **GPU** | **$peakGpuPercent %** | Tải GPU lớn nhất ghi nhận được thông qua các hoạt động kết xuất đồ họa 3D. |

## Thông tin Hệ thống & Môi trường
- **Ngày thực hiện**: $(Get-Date -Format "dd/MM/yyyy HH:mm:ss")
- **CPU**: $numProcessors logical cores
- **Tiến trình theo dõi**:
  - `kusshoes-editor-desktop.exe` (Tauri main UI)
  - `python.exe` (FastAPI backend sidecar)
  - `blender.exe` (Nếu chạy tác vụ render/cleanup mô hình)
- **Tệp báo cáo**: [desktop_performance_report.md](file:///$($reportPath.Replace('\', '/')))
"@

$reportContent | Out-File -FilePath $reportPath -Encoding utf8
Write-Host "Da luu bao cao vao file: $reportPath" -ForegroundColor Green
