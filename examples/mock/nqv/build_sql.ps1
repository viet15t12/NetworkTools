# ============================================================
# build_sql.ps1
#
# Ghép các file SQL nguồn thành hai file SQL tổng hợp:
#
#   schema/*.sql
#       -> device_network.sql
#
#   info_collected/*.sql
#       -> info_collected.sql
#
# Các file SQL được sắp xếp tự nhiên theo tên:
#   01_..., 02_..., 10_..., 11_...
#
# Tên file có khoảng trắng vẫn được hỗ trợ.
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$SchemaDir = Join-Path $RootDir "schema"
$InfoDir = Join-Path $RootDir "info_collected"

$DeviceSql = Join-Path $RootDir "device_network.sql"
$InfoSql = Join-Path $RootDir "info_collected.sql"

# Ghi file SQL bằng UTF-8 không BOM.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)


# ============================================================
# Hàm hỗ trợ
# ============================================================

function Test-SourceDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DirectoryPath,

        [Parameter(Mandatory = $true)]
        [string]$DirectoryName
    )

    if (-not (Test-Path -LiteralPath $DirectoryPath -PathType Container)) {
        throw "Không tìm thấy thư mục $DirectoryName`: $DirectoryPath"
    }

    $SqlFiles = @(
        Get-ChildItem `
            -LiteralPath $DirectoryPath `
            -File `
            -Filter "*.sql"
    )

    if ($SqlFiles.Count -eq 0) {
        throw "Thư mục $DirectoryName không chứa file .sql."
    }
}


function Get-NaturalSortKey {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FileName
    )

    return [regex]::Replace(
        $FileName,
        '\d+',
        {
            param($Match)

            $Match.Value.PadLeft(20, '0')
        }
    )
}


function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Content
    )

    [System.IO.File]::WriteAllText(
        $Path,
        $Content,
        $Utf8NoBom
    )
}


function Add-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Content
    )

    [System.IO.File]::AppendAllText(
        $Path,
        $Content,
        $Utf8NoBom
    )
}


function Write-SqlHeader {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputFile,

        [Parameter(Mandatory = $true)]
        [string]$DatabaseName,

        [Parameter(Mandatory = $true)]
        [string]$SourceDirectory
    )

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"

    $Header = @"
-- ============================================================
-- $DatabaseName
-- ============================================================
-- File được tạo tự động bởi build_sql.ps1.
--
-- Không chỉnh sửa trực tiếp file này.
-- Hãy chỉnh sửa các file nguồn trong:
--   $SourceDirectory/
--
-- Thời điểm tạo:
--   $Timestamp
-- ============================================================

PRAGMA foreign_keys = ON;


"@

    Write-Utf8NoBom `
        -Path $OutputFile `
        -Content $Header
}


function Add-SqlDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDirectory,

        [Parameter(Mandatory = $true)]
        [string]$SourceDirectoryName,

        [Parameter(Mandatory = $true)]
        [string]$OutputFile
    )

    $SqlFiles = @(
        Get-ChildItem `
            -LiteralPath $SourceDirectory `
            -File `
            -Filter "*.sql" |
        Sort-Object {
            Get-NaturalSortKey -FileName $_.Name
        }
    )

    if ($SqlFiles.Count -eq 0) {
        throw "Không có file SQL trong $SourceDirectory."
    }

    foreach ($SqlFile in $SqlFiles) {
        $RelativePath = "$SourceDirectoryName/$($SqlFile.Name)"

        Write-Host "  Ghép: $RelativePath"

        $SqlContent = [System.IO.File]::ReadAllText(
            $SqlFile.FullName,
            [System.Text.Encoding]::UTF8
        )

        $Section = @"

-- ============================================================
-- BEGIN FILE: $RelativePath
-- ============================================================

$SqlContent

-- ============================================================
-- END FILE: $RelativePath
-- ============================================================


"@

        Add-Utf8NoBom `
            -Path $OutputFile `
            -Content $Section
    }

    Write-Host "  Tổng số file: $($SqlFiles.Count)"
}


# ============================================================
# Chương trình chính
# ============================================================

try {
    Test-SourceDirectory `
        -DirectoryPath $SchemaDir `
        -DirectoryName "schema"

    Test-SourceDirectory `
        -DirectoryPath $InfoDir `
        -DirectoryName "info_collected"

    Write-Host "============================================"
    Write-Host "TẠO DEVICE NETWORK SQL"
    Write-Host "============================================"

    Write-SqlHeader `
        -OutputFile $DeviceSql `
        -DatabaseName "DEVICE NETWORK SCHEMA" `
        -SourceDirectory "schema"

    Add-SqlDirectory `
        -SourceDirectory $SchemaDir `
        -SourceDirectoryName "schema" `
        -OutputFile $DeviceSql

    Write-Host ""
    Write-Host "============================================"
    Write-Host "TẠO INFO COLLECTED SQL"
    Write-Host "============================================"

    Write-SqlHeader `
        -OutputFile $InfoSql `
        -DatabaseName "INFO COLLECTED SCHEMA" `
        -SourceDirectory "info_collected"

    Add-SqlDirectory `
        -SourceDirectory $InfoDir `
        -SourceDirectoryName "info_collected" `
        -OutputFile $InfoSql

    Write-Host ""
    Write-Host "============================================"
    Write-Host "HOÀN TẤT"
    Write-Host "============================================"
    Write-Host "Đã tạo:"
    Write-Host "  $DeviceSql"
    Write-Host "  $InfoSql"
}
catch {
    Write-Error $_
    exit 1
}
