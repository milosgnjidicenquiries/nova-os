param([string]$Folder = ".")

$ErrorActionPreference = "Stop"
$iso = Join-Path $Folder "nova-os-0.1.0-amd64.iso"
$parts = @(Get-ChildItem -LiteralPath $Folder -Filter "nova-os-0.1.0-amd64.iso.*.part" | Sort-Object Name)

if ($parts.Count -gt 0) {
    if (Test-Path -LiteralPath $iso) {
        Write-Error "nova-os-0.1.0-amd64.iso vec postoji u $Folder. Pomeri taj fajl pre spajanja delova."
    }
    $output = [IO.File]::Create($iso)
    try {
        foreach ($part in $parts) {
            Write-Host ("Spajam " + $part.Name)
            $partStream = [IO.File]::OpenRead($part.FullName)
            try { $partStream.CopyTo($output) } finally { $partStream.Dispose() }
        }
    } finally { $output.Dispose() }
}
elseif (-not (Test-Path -LiteralPath $iso)) {
    Write-Error "Nema ni ISO-a ni .part delova u $Folder. Preuzmi ih iz iste GitHub Release stavke."
}

$sums = Join-Path $Folder "SHA256SUMS"
if (-not (Test-Path -LiteralPath $sums)) {
    Write-Error "Nedostaje SHA256SUMS pored ISO-a. Preuzmi ga iz iste GitHub Release stavke."
}
$line = Select-String -LiteralPath $sums -Pattern ([regex]::Escape("nova-os-0.1.0-amd64.iso") + "$") | Select-Object -First 1
if (-not $line) {
    Write-Error "SHA256SUMS ne sadrzi zapis za nova-os-0.1.0-amd64.iso."
}
$wanted = ($line.Line -split "\s+")[0].ToLowerInvariant()
$actual = (Get-FileHash -LiteralPath $iso -Algorithm SHA256).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $iso).Length

if ($actual -eq $wanted) {
    Write-Host ("OK: " + $iso)
    Write-Host ("Velicina: " + $size + " bajtova")
    Write-Host ("SHA256:   " + $actual)
}
else {
    Write-Error ("SHA256 se ne poklapa. Ocekivano " + $wanted + "; dobijeno " + $actual + ". Nemoj pisati ovaj ISO na USB.")
}
