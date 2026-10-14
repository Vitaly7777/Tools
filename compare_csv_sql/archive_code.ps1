# ===== CODE ARCHIVER (ASCII-safe) =====
$Extensions = @("py", "json")
$ExcludeDirs = @(
    ".venv", "venv", "tmp", ".git", ".gitignore",
    "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".egg-info", ".idea", ".vscode"
)

# Output file will be created in the same folder as this script
$OutputFile = Join-Path $PSScriptRoot "full_code_dump.txt"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Current folder: $PSScriptRoot"
Write-Host "Extensions: $($Extensions -join ', ')"
Write-Host "Excluded dirs: $($ExcludeDirs -join ', ')"

# Collect files
$files = Get-ChildItem -Path $PSScriptRoot -Recurse -File | Where-Object {
    $ext = $_.Extension.TrimStart('.')
    if ($Extensions -notcontains $ext) { return $false }
    $full = $_.FullName
    foreach ($dir in $ExcludeDirs) {
        if ($full -match "[\\/]$dir[\\/]") { return $false }
    }
    $true
}

Write-Host "Files found: $($files.Count)"
if ($files.Count -eq 0) {
    Write-Warning "No files to archive. Exiting."
    exit 0
}

# Write archive (UTF-8 without BOM)
try {
    Remove-Item $OutputFile -ErrorAction SilentlyContinue
    $writer = [System.IO.StreamWriter]::new($OutputFile, $false, [System.Text.UTF8Encoding]::new($false))
    foreach ($file in $files) {
        $relPath = $file.FullName.Substring($PSScriptRoot.Length + 1).Replace('\', '/')
        $writer.WriteLine("===== FILE: ./$relPath =====")
        try {
            $lines = Get-Content -Path $file.FullName -Encoding UTF8
            foreach ($line in $lines) { $writer.WriteLine($line) }
        }
        catch {
            Write-Warning "Error reading: $relPath"
            $writer.WriteLine("[Error reading file]")
        }
        $writer.WriteLine("")
    }
    $writer.Close()
}
catch {
    Write-Error "Failed to create $OutputFile. Check permissions."
    exit 1
}

# Statistics
if (Test-Path $OutputFile) {
    $lines = (Get-Content $OutputFile -Encoding UTF8 | Measure-Object -Line).Lines
    $size  = (Get-Item $OutputFile).Length
    if ($size -gt 1MB)      { $sizeStr = "{0:N1} MB" -f ($size/1MB) }
    elseif ($size -gt 1KB)  { $sizeStr = "{0:N1} KB" -f ($size/1KB) }
    else                    { $sizeStr = "$size B" }

    Write-Host "========================================"
    Write-Host "Archive: $OutputFile"
    Write-Host "Files: $($files.Count)"
    Write-Host "Lines: $lines"
    Write-Host "Size: $sizeStr"
    Write-Host "========================================"
}
else {
    Write-Error "Output file not created."
}