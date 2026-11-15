param(
    [ValidatePattern("^[01]{9}$")]
    [string]$Pattern = "010010100",
    [string]$OutputPath = ""
)

Add-Type -AssemblyName System.Drawing

if (($Pattern.ToCharArray() | Where-Object { $_ -eq '1' }).Count -ne 3) {
    throw "Pattern must contain exactly three active points (1): $Pattern"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = "assets/card-examples/${Pattern}_card.png"
}

function New-RoundedRectanglePath {
    param(
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height,
        [float]$Radius
    )

    $diameter = $Radius * 2
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
    $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
    $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

$outputFullPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    [System.IO.Path]::GetFullPath($OutputPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
}
$outputDirectory = [System.IO.Path]::GetDirectoryName($outputFullPath)
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null

$bitmap = [System.Drawing.Bitmap]::new(664, 928, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$graphics.Clear([System.Drawing.Color]::Transparent)

$cardX = 0.0
$cardY = 0.0
$cardWidth = 664.0
$cardHeight = 928.0
$cornerRadius = 80.0

# Warm-white outer card border.
$outerPath = New-RoundedRectanglePath -X $cardX -Y $cardY -Width $cardWidth -Height $cardHeight -Radius $cornerRadius
$outerBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#fffdf6"))
$graphics.FillPath($outerBrush, $outerPath)

# Slightly warm face, equivalent to the existing CSS card background.
$faceX = 32.0
$faceY = 32.0
$faceWidth = 600.0
$faceHeight = 864.0
$facePath = New-RoundedRectanglePath -X $faceX -Y $faceY -Width $faceWidth -Height $faceHeight -Radius 54
$faceBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#f7f0df"))
$graphics.FillPath($faceBrush, $facePath)

# Soft upper-left sheen from the current web design.
$sheenPath = [System.Drawing.Drawing2D.GraphicsPath]::new()
$sheenPath.AddEllipse(-40, -38, 530, 440)
$sheenBrush = [System.Drawing.Drawing2D.PathGradientBrush]::new($sheenPath)
$sheenBrush.CenterColor = [System.Drawing.Color]::FromArgb(155, 255, 255, 255)
$sheenBrush.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 255, 255, 255))
$graphics.SetClip($facePath)
$graphics.FillPath($sheenBrush, $sheenPath)
$graphics.ResetClip()

# Small corner marks retained from the local/web playing-card appearance.
$markBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(56, 29, 79, 69))
$markOne = New-RoundedRectanglePath -X 48 -Y 52 -Width 72 -Height 12 -Radius 6
$markTwo = New-RoundedRectanglePath -X 544 -Y 864 -Width 72 -Height 12 -Radius 6
$graphics.FillPath($markBrush, $markOne)
$graphics.FillPath($markBrush, $markTwo)

$patternCharacters = $Pattern.ToCharArray()
$dotCentersX = @(176.0, 332.0, 488.0)
$dotCentersY = @(308.0, 464.0, 620.0)
$dotDiameter = 96.0
$dotRadius = $dotDiameter / 2

for ($row = 0; $row -lt 3; $row++) {
    for ($column = 0; $column -lt 3; $column++) {
        $patternIndex = $row * 3 + $column
        $isActive = $patternCharacters[$patternIndex] -eq '1'
        $left = $dotCentersX[$column] - $dotRadius
        $top = $dotCentersY[$row] - $dotRadius

        $shadowColor = if ($isActive) {
            [System.Drawing.Color]::FromArgb(92, 105, 18, 13)
        } else {
            [System.Drawing.Color]::FromArgb(88, 0, 0, 0)
        }
        $dotShadow = [System.Drawing.SolidBrush]::new($shadowColor)
        $graphics.FillEllipse($dotShadow, $left + 5, $top + 8, $dotDiameter, $dotDiameter)

        $dotColor = if ($isActive) {
            [System.Drawing.ColorTranslator]::FromHtml("#e24f43")
        } else {
            [System.Drawing.ColorTranslator]::FromHtml("#202322")
        }
        $dotBrush = [System.Drawing.SolidBrush]::new($dotColor)
        $graphics.FillEllipse($dotBrush, $left, $top, $dotDiameter, $dotDiameter)

        $highlight = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(56, 255, 255, 255))
        $graphics.FillEllipse($highlight, $left + 17, $top + 14, 29, 22)

        $dotShadow.Dispose()
        $dotBrush.Dispose()
        $highlight.Dispose()
    }
}

$bitmap.Save($outputFullPath, [System.Drawing.Imaging.ImageFormat]::Png)

$markOne.Dispose()
$markTwo.Dispose()
$markBrush.Dispose()
$sheenBrush.Dispose()
$sheenPath.Dispose()
$faceBrush.Dispose()
$facePath.Dispose()
$outerBrush.Dispose()
$outerPath.Dispose()
$graphics.Dispose()
$bitmap.Dispose()

Write-Output $outputFullPath
