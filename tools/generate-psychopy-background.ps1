param(
    [string]$OutputPath = "assets/backgrounds/card-catcher-background-2880x1800.png",
    [string]$LayoutPath = "assets/backgrounds/card-catcher-background-2880x1800.layout.json"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

# Keep this script ASCII-safe for Windows PowerShell 5, which may parse UTF-8
# source files without a BOM using the current ANSI code page.
$textBrandSubtitle = -join @([char]0xAC19, [char]0xC740, [char]0x20, [char]0xCE74, [char]0xB4DC, [char]0x20, [char]0xCC3E, [char]0xAE30)
$textRound = -join @([char]0xB77C, [char]0xC6B4, [char]0xB4DC)
$textProgress = -join @([char]0xC9C4, [char]0xD589, [char]0xB960)
$textReferenceCard = -join @([char]0xAE30, [char]0xC900, [char]0x20, [char]0xCE74, [char]0xB4DC)
$textNewCard = -join @([char]0xC0C8, [char]0x20, [char]0xCE74, [char]0xB4DC)
$textCollectedCards = -join @([char]0xB0B4, [char]0xAC00, [char]0x20, [char]0xBAA8, [char]0xC740, [char]0x20, [char]0xCE74, [char]0xB4DC)
$textIfSame = -join @([char]0xAC19, [char]0xC73C, [char]0xBA74)
$textCollectCard = -join @([char]0xCE74, [char]0xB4DC, [char]0x20, [char]0xAC00, [char]0xC838, [char]0xC624, [char]0xAE30)
$textStar = [char]0x2605

function Resolve-OutputPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
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

function Draw-CenteredText {
    param(
        [System.Drawing.Graphics]$Graphics,
        [string]$Text,
        [System.Drawing.Font]$Font,
        [System.Drawing.Brush]$Brush,
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height
    )

    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $format.Trimming = [System.Drawing.StringTrimming]::EllipsisCharacter
    $Graphics.DrawString($Text, $Font, $Brush, [System.Drawing.RectangleF]::new($X, $Y, $Width, $Height), $format)
    $format.Dispose()
}

function Draw-CardBack {
    param(
        [System.Drawing.Graphics]$Graphics,
        [float]$CenterX,
        [float]$CenterY,
        [float]$Width,
        [float]$Height,
        [float]$Angle,
        [System.Drawing.Color]$BaseColor,
        [System.Drawing.Color]$StripeColor,
        [System.Drawing.Color]$BorderColor
    )

    $state = $Graphics.Save()
    $Graphics.TranslateTransform($CenterX, $CenterY)
    $Graphics.RotateTransform($Angle)
    $x = -$Width / 2
    $y = -$Height / 2
    $path = New-RoundedRectanglePath -X $x -Y $y -Width $Width -Height $Height -Radius 24

    $shadowPath = New-RoundedRectanglePath -X ($x + 10) -Y ($y + 18) -Width $Width -Height $Height -Radius 24
    $shadowBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(70, 3, 28, 24))
    $Graphics.FillPath($shadowBrush, $shadowPath)

    $baseBrush = [System.Drawing.SolidBrush]::new($BaseColor)
    $Graphics.FillPath($baseBrush, $path)
    $Graphics.SetClip($path)
    $stripePen = [System.Drawing.Pen]::new($StripeColor, 16)
    for ($offset = -$Height; $offset -lt $Width + $Height; $offset += 34) {
        $Graphics.DrawLine($stripePen, $x + $offset, $y + $Height, $x + $offset + $Height, $y)
    }
    $Graphics.ResetClip()
    $borderPen = [System.Drawing.Pen]::new($BorderColor, 10)
    $Graphics.DrawPath($borderPen, $path)

    $borderPen.Dispose()
    $stripePen.Dispose()
    $baseBrush.Dispose()
    $shadowBrush.Dispose()
    $shadowPath.Dispose()
    $path.Dispose()
    $Graphics.Restore($state)
}

$outputFullPath = Resolve-OutputPath $OutputPath
$layoutFullPath = Resolve-OutputPath $LayoutPath
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($outputFullPath)) | Out-Null
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($layoutFullPath)) | Out-Null

$width = 2880
$height = 1800
$bitmap = [System.Drawing.Bitmap]::new($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

# Warm website background.
$backgroundRect = [System.Drawing.Rectangle]::new(0, 0, $width, $height)
$backgroundBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    $backgroundRect,
    [System.Drawing.ColorTranslator]::FromHtml("#f7f3e9"),
    [System.Drawing.ColorTranslator]::FromHtml("#eee8dc"),
    145
)
$graphics.FillRectangle($backgroundBrush, $backgroundRect)

# Preserve the original 16:9 UI proportions inside the 16:10 canvas. Scaling
# 2560x1440 by 1.125 yields 2880x1620; the remaining 180 px is split vertically.
$contentState = $graphics.Save()
$graphics.TranslateTransform(0, 90)
$graphics.ScaleTransform(1.125, 1.125)

# Header and static brand.
$brandMarkPath = New-RoundedRectanglePath -X 106 -Y 48 -Width 68 -Height 68 -Radius 18
$brandMarkBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#1b6656"))
$graphics.FillPath($brandMarkBrush, $brandMarkPath)
$goldBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#f4b942"))
$graphics.FillEllipse($goldBrush, 124, 66, 32, 32)
$brandFont = [System.Drawing.Font]::new("Segoe UI", 19, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$brandSubFont = [System.Drawing.Font]::new("Malgun Gothic", 16, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$inkBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#17342f"))
$inkSoftBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#54716b"))
$graphics.DrawString("CARD CATCHER", $brandFont, $inkBrush, 194, 55)
$graphics.DrawString($textBrandSubtitle, $brandSubFont, $inkSoftBrush, 194, 83)

# Static HUD scaffolding. Dynamic round/progress/score text should be overlaid.
$hudTrackPath = New-RoundedRectanglePath -X 930 -Y 92 -Width 700 -Height 14 -Radius 7
$hudTrackBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(28, 20, 67, 58))
$graphics.FillPath($hudTrackBrush, $hudTrackPath)
$hudHintFont = [System.Drawing.Font]::new("Malgun Gothic", 18, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$graphics.DrawString($textRound, $hudHintFont, $inkBrush, 106, 145)
$graphics.DrawString($textProgress, $hudHintFont, $inkSoftBrush, 930, 121)

# Main table shadow and wooden frame.
$tableX = 78.0
$tableY = 190.0
$tableWidth = 2404.0
$tableHeight = 1172.0
$tableRadius = 58.0
$tableShadowPath = New-RoundedRectanglePath -X 94 -Y 218 -Width $tableWidth -Height $tableHeight -Radius $tableRadius
$tableShadowBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(52, 44, 35, 27))
$graphics.FillPath($tableShadowBrush, $tableShadowPath)
$tableOuterPath = New-RoundedRectanglePath -X $tableX -Y $tableY -Width $tableWidth -Height $tableHeight -Radius $tableRadius
$woodBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    [System.Drawing.RectangleF]::new($tableX, $tableY, $tableWidth, $tableHeight),
    [System.Drawing.ColorTranslator]::FromHtml("#956644"),
    [System.Drawing.ColorTranslator]::FromHtml("#70452b"),
    145
)
$graphics.FillPath($woodBrush, $tableOuterPath)

$feltX = 102.0
$feltY = 214.0
$feltWidth = 2356.0
$feltHeight = 1124.0
$feltPath = New-RoundedRectanglePath -X $feltX -Y $feltY -Width $feltWidth -Height $feltHeight -Radius 42
$feltBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    [System.Drawing.RectangleF]::new($feltX, $feltY, $feltWidth, $feltHeight),
    [System.Drawing.ColorTranslator]::FromHtml("#2a7d69"),
    [System.Drawing.ColorTranslator]::FromHtml("#0e473d"),
    145
)
$graphics.FillPath($feltBrush, $feltPath)

# Subtle felt texture and inset glow.
$feltState = $graphics.Save()
$graphics.SetClip($feltPath)
$texturePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(10, 255, 255, 255), 2)
for ($offset = -900; $offset -lt 3300; $offset += 34) {
    $graphics.DrawLine($texturePen, $offset, 1330, $offset + 660, 214)
}
$glowPath = [System.Drawing.Drawing2D.GraphicsPath]::new()
$glowPath.AddEllipse(620, 280, 1320, 840)
$glowBrush = [System.Drawing.Drawing2D.PathGradientBrush]::new($glowPath)
$glowBrush.CenterColor = [System.Drawing.Color]::FromArgb(20, 255, 255, 255)
$glowBrush.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 255, 255, 255))
$graphics.FillPath($glowBrush, $glowPath)
$graphics.Restore($feltState)

$stitchPath = New-RoundedRectanglePath -X 128 -Y 240 -Width 2304 -Height 1072 -Radius 34
$stitchPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(28, 255, 255, 255), 2)
$stitchPen.DashPattern = @(7.0, 9.0)
$graphics.DrawPath($stitchPen, $stitchPath)

# Zone labels.
$zoneFont = [System.Drawing.Font]::new("Malgun Gothic", 19, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$zoneBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(184, 255, 255, 255))
Draw-CenteredText -Graphics $graphics -Text $textReferenceCard -Font $zoneFont -Brush $zoneBrush -X 230 -Y 286 -Width 520 -Height 42
Draw-CenteredText -Graphics $graphics -Text $textNewCard -Font $zoneFont -Brush $zoneBrush -X 1010 -Y 286 -Width 540 -Height 42
Draw-CenteredText -Graphics $graphics -Text $textCollectedCards -Font $zoneFont -Brush $zoneBrush -X 1840 -Y 286 -Width 480 -Height 42

# Empty reference plaque. Target image is drawn above this background.
$referencePlaquePath = New-RoundedRectanglePath -X 304 -Y 374 -Width 372 -Height 548 -Radius 32
$referencePlaqueBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(58, 4, 41, 34))
$graphics.FillPath($referencePlaqueBrush, $referencePlaquePath)
$plaquePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(28, 255, 255, 255), 2)
$graphics.DrawPath($plaquePen, $referencePlaquePath)

# Empty central slot. Trial card is drawn above this background.
$stimulusSlotPath = New-RoundedRectanglePath -X 1050 -Y 350 -Width 460 -Height 642 -Radius 38
$slotPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(50, 255, 255, 255), 3)
$slotPen.DashPattern = @(10.0, 10.0)
$graphics.DrawPath($slotPen, $stimulusSlotPath)

# Static collection pile, safely baked into the background.
Draw-CardBack -Graphics $graphics -CenterX 2078 -CenterY 653 -Width 286 -Height 390 -Angle -6 `
    -BaseColor ([System.Drawing.ColorTranslator]::FromHtml("#cb8e26")) `
    -StripeColor ([System.Drawing.ColorTranslator]::FromHtml("#e1a737")) `
    -BorderColor ([System.Drawing.ColorTranslator]::FromHtml("#fff9e9"))
Draw-CardBack -Graphics $graphics -CenterX 2100 -CenterY 646 -Width 286 -Height 390 -Angle 5 `
    -BaseColor ([System.Drawing.ColorTranslator]::FromHtml("#cb8e26")) `
    -StripeColor ([System.Drawing.ColorTranslator]::FromHtml("#e1a737")) `
    -BorderColor ([System.Drawing.ColorTranslator]::FromHtml("#fff9e9"))
$starPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(222, 255, 255, 255), 6)
$graphics.DrawEllipse($starPen, 2037, 582, 126, 126)
$starFont = [System.Drawing.Font]::new("Segoe UI Symbol", 62, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$whiteBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(235, 255, 255, 255))
Draw-CenteredText -Graphics $graphics -Text $textStar -Font $starFont -Brush $whiteBrush -X 2037 -Y 577 -Width 126 -Height 126

# Static action guide below the trial slot.
$guidePath = New-RoundedRectanglePath -X 1040 -Y 1052 -Width 480 -Height 102 -Radius 24
$guideBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(58, 4, 39, 33))
$graphics.FillPath($guideBrush, $guidePath)
$keyPath = New-RoundedRectanglePath -X 1070 -Y 1074 -Width 142 -Height 58 -Radius 14
$keyBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(224, 255, 253, 246))
$graphics.FillPath($keyBrush, $keyPath)
$keyFont = [System.Drawing.Font]::new("Segoe UI", 20, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
Draw-CenteredText -Graphics $graphics -Text "SPACE" -Font $keyFont -Brush $inkBrush -X 1070 -Y 1074 -Width 142 -Height 58
$guideFont = [System.Drawing.Font]::new("Malgun Gothic", 20, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$guideTextBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(224, 255, 255, 255))
$goldTextBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#ffe09a"))
$graphics.DrawString($textIfSame, $guideFont, $goldTextBrush, 1240, 1087)
$graphics.DrawString($textCollectCard, $guideFont, $guideTextBrush, 1312, 1087)

$graphics.Restore($contentState)
$bitmap.Save($outputFullPath, [System.Drawing.Imaging.ImageFormat]::Png)

$layout = [ordered]@{
    canvas = [ordered]@{ width_px = 2880; height_px = 1800; psychopy_units = "pix" }
    background = [ordered]@{ center_px = @(0, 0); size_px = @(2880, 1800) }
    target_card = [ordered]@{
        center_from_top_left_px = @(551, 819)
        psychopy_position_px = @(-889, 81)
        size_px = @(374, 522)
    }
    stimulus_card = [ordered]@{
        center_from_top_left_px = @(1440, 845)
        psychopy_position_px = @(0, 55)
        size_px = @(473, 660)
    }
    progress_track = [ordered]@{
        top_left_px = @(1046, 194)
        size_px = @(788, 16)
        psychopy_center_px = @(0, 699)
    }
    notes = @(
        "PsychoPy pix coordinates use the screen center as (0,0), with positive y upward.",
        "The Target card, trial stimulus card, progress fill, trial counters, and feedback remain dynamic overlays.",
        "The table, labels, empty slots, action guide, and collection pile are baked into the background."
    )
}
$layout | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $layoutFullPath -Encoding UTF8

foreach ($resource in @(
    $guideTextBrush, $goldTextBrush, $guideFont, $keyFont, $keyBrush, $keyPath, $guideBrush, $guidePath,
    $whiteBrush, $starFont, $starPen, $zoneBrush, $zoneFont, $slotPen, $stimulusSlotPath, $plaquePen,
    $referencePlaqueBrush, $referencePlaquePath, $stitchPen, $stitchPath, $glowBrush, $glowPath, $texturePen,
    $feltBrush, $feltPath, $woodBrush, $tableOuterPath, $tableShadowBrush, $tableShadowPath, $hudHintFont,
    $hudTrackBrush, $hudTrackPath, $inkSoftBrush, $inkBrush, $brandSubFont, $brandFont, $goldBrush,
    $brandMarkBrush, $brandMarkPath, $backgroundBrush
)) {
    if ($null -ne $resource) { $resource.Dispose() }
}
$graphics.Dispose()
$bitmap.Dispose()

Write-Output $outputFullPath
Write-Output $layoutFullPath
