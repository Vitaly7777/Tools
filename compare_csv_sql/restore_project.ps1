# ===== CODE RESTORER =====
# Восстанавливает проект из текстового дампа, созданного CODE ARCHIVER'ом.
# Использование:
#   .\restore_project.ps1                              # дамп рядом со скриптом, вывод в .\restored_project
#   .\restore_project.ps1 -DumpFile "dump.txt" -OutputDir "C:\temp\proj"

param(
    [string]$DumpFile,
    [string]$OutputDir
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Пути по умолчанию
if (-not $DumpFile)  { $DumpFile  = Join-Path $PSScriptRoot "full_code_dump.txt" }
if (-not $OutputDir) { $OutputDir = Join-Path $PSScriptRoot "restored_project" }

if (-not (Test-Path $DumpFile)) {
    Write-Error "Dump file not found: $DumpFile"
    exit 1
}

# Не даём перезаписать существующую папку по ошибке
if (Test-Path $OutputDir) {
    Write-Error "Output directory already exists: $OutputDir. Remove or rename it first."
    exit 1
}

Write-Host "Dump file:   $DumpFile"
Write-Host "Output dir:  $OutputDir"
Write-Host "----------------------------------------"

$markerRegex = '^===== FILE: (.+) =====$'

$restoredCount = 0
$failedCount   = 0
$restoredFiles = New-Object System.Collections.Generic.List[string]

# Читаем дамп целиком (UTF-8), дальше работаем построчно
$lines = Get-Content -Path $DumpFile -Encoding UTF8

# Обрабатываем построчно с буфером: содержимое файла копим,
# а при встрече следующего маркера — сбрасываем буфер на диск
$buffer      = New-Object System.Collections.Generic.List[string]
$currentPath = $null


function Flush-Buffer {
    if ($script:currentPath) {
        # Нормализуем путь и защищаемся от выхода за пределы выходной папки
        $rel = $script:currentPath.TrimStart('.', '/').Replace('/', '\')
        if ($rel -match '\.\.' -or [System.IO.Path]::IsPathRooted($rel)) {
            Write-Warning "Skipping suspicious path: $($script:currentPath)"
            $script:failedCount++
            return
        }

        $target = Join-Path $OutputDir $rel
        $targetDir = Split-Path $target -Parent
        try {
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            $writer = [System.IO.StreamWriter]::new($target, $false, [System.Text.UTF8Encoding]::new($false))
            foreach ($line in $script:buffer) { $writer.WriteLine($line) }
            $writer.Close()
            $script:restoredCount++
            $script:restoredFiles.Add($rel)
        }
        catch {
            Write-Warning "Failed to write: $rel ($($_.Exception.Message))"
            $script:failedCount++
        }
    }
}

foreach ($line in $lines) {
    if ($line -match $markerRegex) {
        # Встретили новый маркер — сначала сбрасываем предыдущий файл
        Flush-Buffer
        $currentPath = $Matches[1]
        $buffer.Clear()
        Write-Host "Restoring: $currentPath"
    }
    elseif ($currentPath) {
        $buffer.Add($line)
    }
    # Строки до первого маркера (например, служебные) игнорируем
}

# Последний файл в дампе
Flush-Buffer

Write-Host "========================================"
Write-Host "Restored files: $restoredCount"
if ($failedCount -gt 0) { Write-Host "Failed:         $failedCount" }
Write-Host "Output:         $OutputDir"
Write-Host "========================================"

if ($restoredCount -eq 0) {
    Write-Warning "Nothing restored. Check that the dump was created by the archiver (markers like '===== FILE: ./... =====')."
    exit 1
}
