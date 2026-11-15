param(
    [string]$OutputDirectory = "assets/card-combinations"
)

$ErrorActionPreference = "Stop"

$generatorPath = Join-Path $PSScriptRoot "generate-card-example.ps1"
if (-not (Test-Path -LiteralPath $generatorPath)) {
    throw "Card generator not found: $generatorPath"
}

$outputFullDirectory = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    [System.IO.Path]::GetFullPath($OutputDirectory)
} else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
}
[System.IO.Directory]::CreateDirectory($outputFullDirectory) | Out-Null

# Read positions in row-major order: 1 2 3 / 4 5 6 / 7 8 9.
# A 1 is a red active point and a 0 is a black inactive point.
$patterns = @(
    for ($mask = 0; $mask -lt 512; $mask++) {
        $bits = @(
            for ($index = 0; $index -lt 9; $index++) {
                $bit = 1 -shl (8 - $index)
                if (($mask -band $bit) -ne 0) { "1" } else { "0" }
            }
        )

        $pattern = -join $bits
        if (($pattern.ToCharArray() | Where-Object { $_ -eq '1' }).Count -eq 3) {
            $pattern
        }
    }
) | Sort-Object

if ($patterns.Count -ne 84) {
    throw "Expected 84 combinations, but generated $($patterns.Count)."
}

if (($patterns | Select-Object -Unique).Count -ne 84) {
    throw "Duplicate card patterns were generated."
}

foreach ($pattern in $patterns) {
    $outputPath = Join-Path $outputFullDirectory "${pattern}_card.png"
    & $generatorPath -Pattern $pattern -OutputPath $outputPath | Out-Null
}

$generatedFiles = @(
    Get-ChildItem -LiteralPath $outputFullDirectory -File -Filter "*_card.png" |
        Where-Object { $_.Name -match "^[01]{9}_card[.]png$" }
)

if ($generatedFiles.Count -ne 84) {
    throw "Expected 84 card files, but found $($generatedFiles.Count) in $outputFullDirectory."
}

foreach ($pattern in $patterns) {
    $expectedPath = Join-Path $outputFullDirectory "${pattern}_card.png"
    if (-not (Test-Path -LiteralPath $expectedPath)) {
        throw "Missing generated card: $expectedPath"
    }
}

Write-Output "Generated and verified 84 unique card images."
Write-Output $outputFullDirectory
