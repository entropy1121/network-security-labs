param(
    [ValidateSet('initial','single','medium','high')]
    [string]$Stage = 'initial',
    [string]$OutputDirectory = "$env:USERPROFILE\Lab06-VMnet8"
)
$ErrorActionPreference = 'Stop'
$adapters = @(Get-NetAdapter -IncludeHidden | Where-Object {
    $_.Name -match 'VMnet8' -or $_.InterfaceDescription -match 'VMnet8'
})
if ($adapters.Count -ne 1) {
    Get-NetAdapter -IncludeHidden | Select-Object Name, InterfaceDescription, Status | Out-Host
    throw "Expected one VMnet8 adapter; found $($adapters.Count)."
}
$nic = $adapters[0]
$idx = $nic.ifIndex
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$record = [ordered]@{
    Stage = $Stage
    Time = (Get-Date).ToString('o')
    Adapter = $nic | Select-Object Name, InterfaceDescription, ifIndex, Status, MacAddress
    IPv6Interface = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv6 |
        Select-Object InterfaceIndex, ConnectionState, RouterDiscovery, InterfaceMetric
    Addresses = @(Get-NetIPAddress -AddressFamily IPv6 -InterfaceIndex $idx -ErrorAction SilentlyContinue |
        Select-Object IPAddress, PrefixLength, PrefixOrigin, SuffixOrigin, AddressState)
    DefaultRoutes = @(Get-NetRoute -AddressFamily IPv6 -InterfaceIndex $idx -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
        Where-Object DestinationPrefix -eq '::/0' | Select-Object DestinationPrefix, NextHop, RouteMetric, Protocol)
    Privacy = @(netsh interface ipv6 show privacy)
}
$file = Join-Path $OutputDirectory ("{0}-{1}.json" -f $Stage,(Get-Date -Format yyyyMMdd-HHmmssfff))
$record | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $file
$record.Adapter | Format-List | Out-Host
$record.Addresses | Format-Table -AutoSize | Out-Host
$record.DefaultRoutes | Format-Table -AutoSize | Out-Host
Write-Output "Saved: $file"
