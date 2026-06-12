<#
.SYNOPSIS
    Deploys the ITFlow Quick Ticket tray app via TacticalRMM.

.DESCRIPTION
    - Installs ITFlowQuickTicket.exe into C:\Program Files\ITFlowQuickTicket
    - Writes a per-client config.json into C:\ProgramData\ITFlowQuickTicket
    - Adds a shortcut to the All Users Startup folder so it launches on login
    - Starts the app immediately for the current session (if one is active)

.NOTES
    Run as a TacticalRMM script with type "powershell", running as System.

    Set the values below via TacticalRMM script arguments / custom fields
    (recommended), or edit the defaults directly per-client policy.

    Expected script arguments (in order):
        1. ExeSourceUrl   - URL to download ITFlowQuickTicket.exe from
                             (e.g. a TacticalRMM file share / your CDN)
        2. ItflowBaseUrl  - e.g. https://itflow.foleyit.com
        3. ApiKey         - ITFlow API key (Admin > API Keys)
        4. ClientId       - ITFlow client_id for this client
        5. ContactId      - (optional) ITFlow contact_id, or 0/blank
        6. Priority       - (optional) Low/Medium/High/Critical, default Medium
#>

param(
    [Parameter(Mandatory = $true)] [string]$ExeSourceUrl,
    [Parameter(Mandatory = $true)] [string]$ItflowBaseUrl,
    [Parameter(Mandatory = $true)] [string]$ApiKey,
    [Parameter(Mandatory = $true)] [int]$ClientId,
    [int]$ContactId = 0,
    [string]$Priority = "Medium"
)

$ErrorActionPreference = "Stop"

$installDir = "C:\Program Files\ITFlowQuickTicket"
$configDir  = "C:\ProgramData\ITFlowQuickTicket"
$exePath    = Join-Path $installDir "ITFlowQuickTicket.exe"
$configPath = Join-Path $configDir "config.json"
$startupDir = "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp"
$shortcutPath = Join-Path $startupDir "ITFlow Quick Ticket.lnk"

# 1. Install directory + binary
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Write-Host "Downloading ITFlowQuickTicket.exe from $ExeSourceUrl ..."
Invoke-WebRequest -Uri $ExeSourceUrl -OutFile $exePath -UseBasicParsing

# 2. Per-client config
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

$config = [ordered]@{
    itflow_base_url = $ItflowBaseUrl
    api_key         = $ApiKey
    client_id       = $ClientId
    contact_id      = if ($ContactId -gt 0) { $ContactId } else { $null }
    priority        = $Priority
}
$config | ConvertTo-Json | Set-Content -Path $configPath -Encoding UTF8

Write-Host "Wrote config to $configPath"

# 3. Start on login (All Users Startup folder)
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "ITFlow Quick Ticket"
$shortcut.Save()

Write-Host "Created startup shortcut at $shortcutPath"

# 4. Launch now for the active interactive session, if any
try {
    $explorer = Get-Process -Name explorer -IncludeUserName -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($explorer) {
        Start-Process -FilePath $exePath
        Write-Host "Launched ITFlowQuickTicket.exe"
    } else {
        Write-Host "No interactive session detected; app will start on next login."
    }
} catch {
    Write-Host "Could not auto-launch app (will start on next login): $_"
}

Write-Host "ITFlow Quick Ticket deployment complete."
