[CmdletBinding()]
param(
    [switch]$StartServices,
    [string]$LogPath = "$env:ProgramData\AIProject\Logs\wsl-service-guard.log"
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[{0}] [{1}] {2}" -f $timestamp, $Level, $Message
    Add-Content -LiteralPath $LogPath -Value $line
    Write-Output $line
}

function Ensure-LogDirectory {
    $directory = Split-Path -Path $LogPath -Parent
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
}

function Test-IsElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Protect-Service {
    param(
        [string]$Name,
        [switch]$StartWhenNeeded
    )

    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        Write-Log "Service '$Name' was not found." "WARN"
        return
    }

    if ($service.StartType -eq "Disabled") {
        Set-Service -Name $Name -StartupType Manual
        Write-Log "Changed '$Name' startup type from Disabled to Manual."
        $service = Get-Service -Name $Name
    }
    else {
        Write-Log "No startup type change needed for '$Name' ($($service.StartType))."
    }

    if ($StartWhenNeeded -and $service.Status -ne "Running") {
        try {
            Start-Service -Name $Name
            $service = Get-Service -Name $Name
            Write-Log "Started '$Name' ($($service.Status))."
        }
        catch {
            Write-Log "Could not start '$Name': $($_.Exception.Message)" "WARN"
        }
    }
    elseif ($StartWhenNeeded) {
        Write-Log "'$Name' is already running."
    }
}

Ensure-LogDirectory

if (-not (Test-IsElevated)) {
    Write-Log "This script requires elevation." "ERROR"
    exit 1
}

Write-Log "WSL service guard run started. StartServices=$StartServices"

Protect-Service -Name "WslService" -StartWhenNeeded:$StartServices
Protect-Service -Name "vmcompute" -StartWhenNeeded:$StartServices
Protect-Service -Name "com.docker.service" -StartWhenNeeded:$StartServices

Write-Log "WSL service guard run completed."
