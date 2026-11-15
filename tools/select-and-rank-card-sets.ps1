param(
    [string]$SourceDirectory = "assets/card-combinations",
    [string]$OutputDirectory = "assets/sets",
    [ValidateSet("D4Representatives", "AllPatterns")]
    [string]$TargetMode = "D4Representatives",
    [int]$Seed = 20260721
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-WorkspacePath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
}

function Get-D4Patterns {
    param([string]$Pattern)

    $forms = @()
    for ($transform = 0; $transform -lt 8; $transform++) {
        $output = @("0", "0", "0", "0", "0", "0", "0", "0", "0")
        for ($index = 0; $index -lt 9; $index++) {
            if ($Pattern[$index] -ne '1') { continue }

            $row = [int][math]::Floor($index / 3)
            $column = $index % 3

            # Transforms 4-7 are a left/right reflection followed by 0-3 rotations.
            if ($transform -ge 4) {
                $column = 2 - $column
            }

            $rotationCount = $transform % 4
            for ($rotation = 0; $rotation -lt $rotationCount; $rotation++) {
                $previousRow = $row
                $row = $column
                $column = 2 - $previousRow
            }

            $output[$row * 3 + $column] = "1"
        }
        $forms += (-join $output)
    }
    return @($forms)
}

function Get-HammingDistance {
    param([string]$Left, [string]$Right)
    $distance = 0
    for ($index = 0; $index -lt 9; $index++) {
        if ($Left[$index] -ne $Right[$index]) { $distance++ }
    }
    return $distance
}

function Get-D4MinimumDistance {
    param([string]$Target, [string[]]$CandidateD4Forms)
    $minimum = 9
    foreach ($form in $CandidateD4Forms) {
        $distance = Get-HammingDistance -Left $Target -Right $form
        if ($distance -lt $minimum) { $minimum = $distance }
    }
    return $minimum
}

function Get-ComponentCount {
    param([int[]]$ActiveIndices, [ValidateSet(4, 8)][int]$NeighborMode)

    $active = @{}
    foreach ($index in $ActiveIndices) { $active[$index] = $true }
    $visited = @{}
    $components = 0

    $directions = @(@(-1, 0), @(1, 0), @(0, -1), @(0, 1))
    if ($NeighborMode -eq 8) {
        $directions += @(@(-1, -1), @(-1, 1), @(1, -1), @(1, 1))
    }

    foreach ($start in $ActiveIndices) {
        if ($visited.ContainsKey($start)) { continue }
        $components++
        $queue = [System.Collections.Generic.Queue[int]]::new()
        $queue.Enqueue($start)
        $visited[$start] = $true

        while ($queue.Count -gt 0) {
            $current = $queue.Dequeue()
            $row = [int][math]::Floor($current / 3)
            $column = $current % 3

            foreach ($direction in $directions) {
                $nextRow = $row + $direction[0]
                $nextColumn = $column + $direction[1]
                if ($nextRow -lt 0 -or $nextRow -gt 2 -or $nextColumn -lt 0 -or $nextColumn -gt 2) {
                    continue
                }
                $next = $nextRow * 3 + $nextColumn
                if ($active.ContainsKey($next) -and -not $visited.ContainsKey($next)) {
                    $visited[$next] = $true
                    $queue.Enqueue($next)
                }
            }
        }
    }
    return $components
}

function New-PatternRecord {
    param([string]$Pattern, [System.IO.FileInfo]$File)

    $activeIndices = @()
    $coordinates = @()
    $rowCounts = @(0, 0, 0)
    $columnCounts = @(0, 0, 0)

    for ($index = 0; $index -lt 9; $index++) {
        if ($Pattern[$index] -ne '1') { continue }
        $activeIndices += $index
        $row = [int][math]::Floor($index / 3)
        $column = $index % 3
        $coordinates += [pscustomobject]@{ Row = $row; Column = $column }
        $rowCounts[$row]++
        $columnCounts[$column]++
    }

    $d4Forms = @(Get-D4Patterns -Pattern $Pattern)
    $uniqueD4Forms = @($d4Forms | Sort-Object -Unique)
    $canonical = ($uniqueD4Forms | Sort-Object)[0]
    $symmetryCount = @($d4Forms | Where-Object { $_ -eq $Pattern }).Count

    $orthogonalPairs = 0
    $diagonalPairs = 0
    $pairDistancesSquared = @()
    for ($left = 0; $left -lt $coordinates.Count; $left++) {
        for ($right = $left + 1; $right -lt $coordinates.Count; $right++) {
            $rowDelta = [math]::Abs($coordinates[$left].Row - $coordinates[$right].Row)
            $columnDelta = [math]::Abs($coordinates[$left].Column - $coordinates[$right].Column)
            if (($rowDelta + $columnDelta) -eq 1) { $orthogonalPairs++ }
            if ($rowDelta -eq 1 -and $columnDelta -eq 1) { $diagonalPairs++ }
            $pairDistancesSquared += ($rowDelta * $rowDelta + $columnDelta * $columnDelta)
        }
    }
    $pairDistancesSquared = @($pairDistancesSquared | Sort-Object)

    $rows = @($coordinates | ForEach-Object { $_.Row })
    $columns = @($coordinates | ForEach-Object { $_.Column })
    $centroidRow = ($rows | Measure-Object -Average).Average
    $centroidColumn = ($columns | Measure-Object -Average).Average
    $minRow = ($rows | Measure-Object -Minimum).Minimum
    $maxRow = ($rows | Measure-Object -Maximum).Maximum
    $minColumn = ($columns | Measure-Object -Minimum).Minimum
    $maxColumn = ($columns | Measure-Object -Maximum).Maximum

    $cornerIndices = @(0, 2, 6, 8)
    $cornerCount = @($activeIndices | Where-Object { $cornerIndices -contains $_ }).Count
    $centerIncluded = $activeIndices -contains 4
    $edgeCount = 3 - $cornerCount - $(if ($centerIncluded) { 1 } else { 0 })

    return [pscustomobject]@{
        Pattern = $Pattern
        File = $File
        ActiveIndices = @($activeIndices)
        ActiveIndicesOneBased = @( $activeIndices | ForEach-Object { $_ + 1 } )
        D4Forms = @($d4Forms)
        Canonical = $canonical
        OrbitSize = $uniqueD4Forms.Count
        SymmetryCount = $symmetryCount
        CenterIncluded = [bool]$centerIncluded
        CornerCount = $cornerCount
        EdgeCount = $edgeCount
        RowCounts = @($rowCounts)
        ColumnCounts = @($columnCounts)
        OrthogonalPairs = $orthogonalPairs
        DiagonalPairs = $diagonalPairs
        Components4 = Get-ComponentCount -ActiveIndices $activeIndices -NeighborMode 4
        Components8 = Get-ComponentCount -ActiveIndices $activeIndices -NeighborMode 8
        PairDistancesSquared = @($pairDistancesSquared)
        PairDistanceMean = ($pairDistancesSquared | Measure-Object -Average).Average
        CentroidRow = [double]$centroidRow
        CentroidColumn = [double]$centroidColumn
        BoundingWidth = $maxColumn - $minColumn + 1
        BoundingHeight = $maxRow - $minRow + 1
        BoundingArea = ($maxColumn - $minColumn + 1) * ($maxRow - $minRow + 1)
    }
}

function Get-ArrayL1Distance {
    param([object[]]$Left, [object[]]$Right)
    $total = 0.0
    for ($index = 0; $index -lt $Left.Count; $index++) {
        $total += [math]::Abs([double]$Left[$index] - [double]$Right[$index])
    }
    return $total
}

function Get-LowLevelDistance {
    param($Target, $Candidate)

    $distance = 0.0
    if ($Target.CenterIncluded -ne $Candidate.CenterIncluded) { $distance += 5.0 }
    $distance += 1.5 * [math]::Abs($Target.CornerCount - $Candidate.CornerCount)
    $distance += 0.75 * (Get-ArrayL1Distance -Left $Target.RowCounts -Right $Candidate.RowCounts)
    $distance += 0.75 * (Get-ArrayL1Distance -Left $Target.ColumnCounts -Right $Candidate.ColumnCounts)
    $distance += 1.5 * [math]::Sqrt(
        [math]::Pow($Target.CentroidRow - $Candidate.CentroidRow, 2) +
        [math]::Pow($Target.CentroidColumn - $Candidate.CentroidColumn, 2)
    )
    $distance += 0.5 * [math]::Abs($Target.BoundingArea - $Candidate.BoundingArea)
    return [math]::Round($distance, 4)
}

function Get-StructuralDistance {
    param($Target, $Candidate)

    $distance = 0.0
    $distance += 2.0 * [math]::Abs($Target.OrthogonalPairs - $Candidate.OrthogonalPairs)
    $distance += 1.5 * [math]::Abs($Target.DiagonalPairs - $Candidate.DiagonalPairs)
    $distance += 2.0 * [math]::Abs($Target.Components4 - $Candidate.Components4)
    $distance += 1.0 * [math]::Abs($Target.Components8 - $Candidate.Components8)
    $distance += 0.5 * [math]::Abs($Target.SymmetryCount - $Candidate.SymmetryCount)
    $distance += 0.75 * (Get-ArrayL1Distance -Left $Target.PairDistancesSquared -Right $Candidate.PairDistancesSquared)
    return [math]::Round($distance, 4)
}

function New-RelationshipRecord {
    param($Target, $Candidate, [string]$SetName)

    $fixedHamming = Get-HammingDistance -Left $Target.Pattern -Right $Candidate.Pattern
    $d4Minimum = Get-D4MinimumDistance -Target $Target.Pattern -CandidateD4Forms $Candidate.D4Forms
    $overlap = 3 - [int]($fixedHamming / 2)
    $lowLevelDistance = Get-LowLevelDistance -Target $Target -Candidate $Candidate
    $structuralDistance = Get-StructuralDistance -Target $Target -Candidate $Candidate
    $similarityScore = 100.0 / (1.0 + $fixedHamming + 0.5 * $d4Minimum + $lowLevelDistance + 0.75 * $structuralDistance)
    $nearPriority = $similarityScore
    $farPriority = 4.0 * ($fixedHamming + $d4Minimum) + 3.0 * $structuralDistance - 2.0 * $lowLevelDistance

    $classification = if ($d4Minimum -eq 0) {
        "target_d4_equivalent"
    } elseif ($fixedHamming -eq 2 -and $d4Minimum -eq 2) {
        "near"
    } elseif ($fixedHamming -ge 4 -and $d4Minimum -ge 4) {
        "far"
    } elseif ($fixedHamming -ge 4 -and $d4Minimum -eq 2) {
        "rotation_dependent"
    } else {
        "intermediate"
    }

    return [pscustomobject]@{
        SetName = $SetName
        TargetPattern = $Target.Pattern
        CandidatePattern = $Candidate.Pattern
        Classification = $classification
        FixedOverlap = $overlap
        FixedHamming = $fixedHamming
        D4MinimumDistance = $d4Minimum
        LowLevelDistance = $lowLevelDistance
        StructuralDistance = $structuralDistance
        SimilarityScore = [math]::Round($similarityScore, 6)
        NearPriority = [math]::Round($nearPriority, 6)
        FarPriority = [math]::Round($farPriority, 6)
        Candidate = $Candidate
    }
}

function Select-TargetLibrary {
    param(
        [object[]]$PatternRecords,
        [ValidateSet("D4Representatives", "AllPatterns")][string]$Mode,
        [int]$RandomSeed
    )

    if ($Mode -eq "AllPatterns") {
        return @($PatternRecords | Sort-Object Pattern)
    }

    # Keep one actual display orientation from each D4 class. The orientation is
    # seeded instead of choosing the lexicographically smallest form, which would
    # systematically push active points toward the bottom/right of the card.
    $random = [System.Random]::new($RandomSeed)
    $representatives = @()
    foreach ($group in ($PatternRecords | Group-Object Canonical | Sort-Object Name)) {
        $items = @($group.Group | Sort-Object Pattern)
        $representatives += $items[$random.Next(0, $items.Count)]
    }
    return @($representatives | Sort-Object Canonical)
}

$sourceFullDirectory = Resolve-WorkspacePath $SourceDirectory
$outputFullDirectory = Resolve-WorkspacePath $OutputDirectory

if (-not (Test-Path -LiteralPath $sourceFullDirectory -PathType Container)) {
    throw "Source card directory not found: $sourceFullDirectory"
}
if (Test-Path -LiteralPath $outputFullDirectory) {
    $existingItems = @(Get-ChildItem -LiteralPath $outputFullDirectory -Force)
    if ($existingItems.Count -gt 0) {
        throw "Output directory is not empty. Use a new directory or remove it first: $outputFullDirectory"
    }
}
[System.IO.Directory]::CreateDirectory($outputFullDirectory) | Out-Null

$sourceFiles = @(
    Get-ChildItem -LiteralPath $sourceFullDirectory -File -Filter "*_card.png" |
        Where-Object { $_.Name -match "^([01]{9})_card[.]png$" } |
        Sort-Object Name
)

if ($sourceFiles.Count -ne 84) {
    throw "Expected exactly 84 valid source files, but found $($sourceFiles.Count)."
}

$records = @()
$seenPatterns = @{}
foreach ($file in $sourceFiles) {
    $null = $file.Name -match "^([01]{9})_card[.]png$"
    $pattern = $Matches[1]
    if (($pattern.ToCharArray() | Where-Object { $_ -eq '1' }).Count -ne 3) {
        throw "Source pattern does not contain exactly three active points: $($file.Name)"
    }
    if ($seenPatterns.ContainsKey($pattern)) {
        throw "Duplicate source pattern: $pattern"
    }
    $seenPatterns[$pattern] = $true
    $records += New-PatternRecord -Pattern $pattern -File $file
}

if (@($records.Canonical | Sort-Object -Unique).Count -ne 16) {
    throw "Expected 16 D4 equivalence classes for the 84 patterns."
}

$targets = @(Select-TargetLibrary -PatternRecords $records -Mode $TargetMode -RandomSeed $Seed)
$setNames = @(for ($index = 1; $index -le $targets.Count; $index++) { "set{0:D2}" -f $index })

$relationships = @()
for ($setIndex = 0; $setIndex -lt $targets.Count; $setIndex++) {
    foreach ($candidate in $records) {
        $relationships += New-RelationshipRecord -Target $targets[$setIndex] -Candidate $candidate -SetName $setNames[$setIndex]
    }
}

# This is a target-relative candidate library. A source pattern may therefore be
# copied into several target sets, but it may occur at most once inside each set.
$assigned = @()
$unassigned = @()
foreach ($relation in $relationships) {
    if ($relation.Classification -eq "near") {
        $assigned += [pscustomobject]@{ Role = "Near"; Relation = $relation }
    } elseif ($relation.Classification -eq "far") {
        $assigned += [pscustomobject]@{ Role = "Far"; Relation = $relation }
    } else {
        $unassigned += [pscustomobject]@{
            Set = $relation.SetName
            TargetPattern = $relation.TargetPattern
            Pattern = $relation.CandidatePattern
            Classification = $relation.Classification
            Reason = $(switch ($relation.Classification) {
                "target_d4_equivalent" { "D4-equivalent to this set's Target" }
                "rotation_dependent" { "Similar only after rotation/reflection" }
                default { "Intermediate or ambiguous distance" }
            })
        }
    }
}

$masterManifest = @()
for ($setIndex = 0; $setIndex -lt $targets.Count; $setIndex++) {
    $setName = $setNames[$setIndex]
    $target = $targets[$setIndex]
    $setDirectory = Join-Path $outputFullDirectory $setName
    $targetDirectory = Join-Path $setDirectory "Target"
    $nearDirectory = Join-Path $setDirectory "Near"
    $farDirectory = Join-Path $setDirectory "Far"
    foreach ($roleDirectory in @($targetDirectory, $nearDirectory, $farDirectory)) {
        [System.IO.Directory]::CreateDirectory($roleDirectory) | Out-Null
    }

    $targetFileName = "$($target.Pattern)_${setName}_Target.png"
    $targetRelativePath = Join-Path "Target" $targetFileName
    $targetDestination = Join-Path $setDirectory $targetRelativePath
    Copy-Item -LiteralPath $target.File.FullName -Destination $targetDestination

    $setManifest = @(
        [pscustomobject]@{
            set = $setName
            role = "Target"
            rank = ""
            pattern = $target.Pattern
            active_indices = $target.ActiveIndicesOneBased -join "|"
            source_file = $target.File.Name
            copied_file = $targetRelativePath
            canonical_d4 = $target.Canonical
            fixed_overlap = 3
            fixed_hamming = 0
            d4_min_distance = 0
            low_level_distance = 0
            structural_distance = 0
            similarity_score = 100
            selection_priority = ""
            center_included = $target.CenterIncluded
            orthogonal_pairs = $target.OrthogonalPairs
            diagonal_pairs = $target.DiagonalPairs
            components_4 = $target.Components4
            components_8 = $target.Components8
            symmetry_count = $target.SymmetryCount
            orbit_size = $target.OrbitSize
        }
    )

    $nearItems = @(
        $assigned |
            Where-Object { $_.Role -eq "Near" -and $_.Relation.SetName -eq $setName } |
            Sort-Object @{ Expression = { $_.Relation.NearPriority }; Descending = $true },
                        @{ Expression = { $_.Relation.CandidatePattern } }
    )
    $farItems = @(
        $assigned |
            Where-Object { $_.Role -eq "Far" -and $_.Relation.SetName -eq $setName } |
            Sort-Object @{ Expression = { $_.Relation.FarPriority }; Descending = $true },
                        @{ Expression = { $_.Relation.CandidatePattern } }
    )

    foreach ($roleGroup in @(
        [pscustomobject]@{ Role = "Near"; Items = $nearItems },
        [pscustomobject]@{ Role = "Far"; Items = $farItems }
    )) {
        for ($rankIndex = 0; $rankIndex -lt $roleGroup.Items.Count; $rankIndex++) {
            $item = $roleGroup.Items[$rankIndex]
            $relation = $item.Relation
            $candidate = $relation.Candidate
            $rank = $rankIndex + 1
            $rankLabel = "{0:D2}" -f $rank
            $fileName = "$($candidate.Pattern)_${setName}_$($roleGroup.Role)_${rankLabel}.png"
            $relativePath = Join-Path $roleGroup.Role $fileName
            $destination = Join-Path $setDirectory $relativePath
            Copy-Item -LiteralPath $candidate.File.FullName -Destination $destination

            $setManifest += [pscustomobject]@{
                set = $setName
                role = $roleGroup.Role
                rank = $rank
                pattern = $candidate.Pattern
                active_indices = $candidate.ActiveIndicesOneBased -join "|"
                source_file = $candidate.File.Name
                copied_file = $relativePath
                canonical_d4 = $candidate.Canonical
                fixed_overlap = $relation.FixedOverlap
                fixed_hamming = $relation.FixedHamming
                d4_min_distance = $relation.D4MinimumDistance
                low_level_distance = $relation.LowLevelDistance
                structural_distance = $relation.StructuralDistance
                similarity_score = $relation.SimilarityScore
                selection_priority = $(if ($roleGroup.Role -eq "Near") { $relation.NearPriority } else { $relation.FarPriority })
                center_included = $candidate.CenterIncluded
                orthogonal_pairs = $candidate.OrthogonalPairs
                diagonal_pairs = $candidate.DiagonalPairs
                components_4 = $candidate.Components4
                components_8 = $candidate.Components8
                symmetry_count = $candidate.SymmetryCount
                orbit_size = $candidate.OrbitSize
            }
        }
    }

    $setManifestPath = Join-Path $setDirectory "manifest.csv"
    $setManifest | Export-Csv -LiteralPath $setManifestPath -NoTypeInformation -Encoding UTF8
    $masterManifest += $setManifest
}

$catalog = $records | ForEach-Object {
    [pscustomobject]@{
        pattern = $_.Pattern
        active_indices = $_.ActiveIndicesOneBased -join "|"
        source_file = $_.File.Name
        canonical_d4 = $_.Canonical
        orbit_size = $_.OrbitSize
        symmetry_count = $_.SymmetryCount
        center_included = $_.CenterIncluded
        corner_count = $_.CornerCount
        edge_count = $_.EdgeCount
        row_counts = $_.RowCounts -join "|"
        column_counts = $_.ColumnCounts -join "|"
        orthogonal_pairs = $_.OrthogonalPairs
        diagonal_pairs = $_.DiagonalPairs
        components_4 = $_.Components4
        components_8 = $_.Components8
        pair_distances_squared = $_.PairDistancesSquared -join "|"
        pair_distance_mean = $_.PairDistanceMean
        centroid_row = $_.CentroidRow
        centroid_column = $_.CentroidColumn
        bounding_width = $_.BoundingWidth
        bounding_height = $_.BoundingHeight
        bounding_area = $_.BoundingArea
    }
}
$catalog | Export-Csv -LiteralPath (Join-Path $outputFullDirectory "source_catalog.csv") -NoTypeInformation -Encoding UTF8

# Compare every selected Target class with every other Target class. The D4
# minimum is the primary shape distance; the composite score also records how
# different their low-level and structural feature profiles are.
$targetPairs = @()
$targetPairLookup = @{}
for ($left = 0; $left -lt $targets.Count; $left++) {
    for ($right = $left + 1; $right -lt $targets.Count; $right++) {
        $leftTarget = $targets[$left]
        $rightTarget = $targets[$right]
        $fixedHamming = Get-HammingDistance -Left $leftTarget.Pattern -Right $rightTarget.Pattern
        $d4Minimum = Get-D4MinimumDistance -Target $leftTarget.Pattern -CandidateD4Forms $rightTarget.D4Forms
        $lowLevelDistance = Get-LowLevelDistance -Target $leftTarget -Candidate $rightTarget
        $structuralDistance = Get-StructuralDistance -Target $leftTarget -Candidate $rightTarget
        $uniquenessScore = 10.0 * $d4Minimum + 2.0 * $structuralDistance + $lowLevelDistance

        $pair = [pscustomobject]@{
            target_1_set = $setNames[$left]
            target_1_pattern = $leftTarget.Pattern
            target_2_set = $setNames[$right]
            target_2_pattern = $rightTarget.Pattern
            fixed_hamming = $fixedHamming
            d4_min_distance = $d4Minimum
            low_level_distance = $lowLevelDistance
            structural_distance = $structuralDistance
            uniqueness_score = [math]::Round($uniquenessScore, 4)
        }
        $targetPairs += $pair
        $targetPairLookup["${left}|${right}"] = $pair
    }
}
$targetPairs |
    Sort-Object @{ Expression = { $_.uniqueness_score }; Descending = $true }, target_1_set, target_2_set |
    Export-Csv -LiteralPath (Join-Path $outputFullDirectory "target_pairwise_distances.csv") -NoTypeInformation -Encoding UTF8

$targetUniquenessSummary = @()
for ($targetIndex = 0; $targetIndex -lt $targets.Count; $targetIndex++) {
    $setName = $setNames[$targetIndex]
    $targetPattern = $targets[$targetIndex].Pattern
    $relatedPairs = @($targetPairs | Where-Object {
        $_.target_1_set -eq $setName -or $_.target_2_set -eq $setName
    })
    $nearestPair = $relatedPairs | Sort-Object uniqueness_score | Select-Object -First 1
    $farthestPair = $relatedPairs | Sort-Object @{ Expression = { $_.uniqueness_score }; Descending = $true } | Select-Object -First 1
    $nearestSet = if ($nearestPair.target_1_set -eq $setName) { $nearestPair.target_2_set } else { $nearestPair.target_1_set }
    $nearestPattern = if ($nearestPair.target_1_set -eq $setName) { $nearestPair.target_2_pattern } else { $nearestPair.target_1_pattern }
    $farthestSet = if ($farthestPair.target_1_set -eq $setName) { $farthestPair.target_2_set } else { $farthestPair.target_1_set }
    $farthestPattern = if ($farthestPair.target_1_set -eq $setName) { $farthestPair.target_2_pattern } else { $farthestPair.target_1_pattern }

    $targetUniquenessSummary += [pscustomobject]@{
        set = $setName
        target_pattern = $targetPattern
        minimum_d4_distance = ($relatedPairs | Measure-Object d4_min_distance -Minimum).Minimum
        average_d4_distance = [math]::Round(($relatedPairs | Measure-Object d4_min_distance -Average).Average, 4)
        minimum_uniqueness_score = ($relatedPairs | Measure-Object uniqueness_score -Minimum).Minimum
        average_uniqueness_score = [math]::Round(($relatedPairs | Measure-Object uniqueness_score -Average).Average, 4)
        nearest_target_set = $nearestSet
        nearest_target_pattern = $nearestPattern
        farthest_target_set = $farthestSet
        farthest_target_pattern = $farthestPattern
    }
}
$targetUniquenessSummary |
    Sort-Object @{ Expression = { $_.average_uniqueness_score }; Descending = $true } |
    Export-Csv -LiteralPath (Join-Path $outputFullDirectory "target_uniqueness_summary.csv") -NoTypeInformation -Encoding UTF8

# Evaluate every 3-Target combination. Ranking first maximizes the weakest D4
# pair, then the average D4 distance, then the composite pairwise uniqueness.
$targetTriplets = @()
for ($first = 0; $first -lt $targets.Count; $first++) {
    for ($second = $first + 1; $second -lt $targets.Count; $second++) {
        for ($third = $second + 1; $third -lt $targets.Count; $third++) {
            $pairs = @(
                $targetPairLookup["${first}|${second}"],
                $targetPairLookup["${first}|${third}"],
                $targetPairLookup["${second}|${third}"]
            )
            $minimumD4 = ($pairs | Measure-Object d4_min_distance -Minimum).Minimum
            $averageD4 = ($pairs | Measure-Object d4_min_distance -Average).Average
            $minimumPairUniqueness = ($pairs | Measure-Object uniqueness_score -Minimum).Minimum
            $averagePairUniqueness = ($pairs | Measure-Object uniqueness_score -Average).Average
            $tripletScore = 100.0 * $minimumD4 + 10.0 * $averageD4 + $minimumPairUniqueness + 0.1 * $averagePairUniqueness

            $targetTriplets += [pscustomobject]@{
                target_1_set = $setNames[$first]
                target_1_pattern = $targets[$first].Pattern
                target_2_set = $setNames[$second]
                target_2_pattern = $targets[$second].Pattern
                target_3_set = $setNames[$third]
                target_3_pattern = $targets[$third].Pattern
                minimum_pair_d4_distance = $minimumD4
                average_pair_d4_distance = [math]::Round($averageD4, 4)
                minimum_pair_uniqueness = [math]::Round($minimumPairUniqueness, 4)
                average_pair_uniqueness = [math]::Round($averagePairUniqueness, 4)
                triplet_uniqueness_score = [math]::Round($tripletScore, 4)
            }
        }
    }
}
$rankedTargetTriplets = @(
    $targetTriplets |
        Sort-Object `
            @{ Expression = { $_.minimum_pair_d4_distance }; Descending = $true },
            @{ Expression = { $_.average_pair_d4_distance }; Descending = $true },
            @{ Expression = { $_.minimum_pair_uniqueness }; Descending = $true },
            @{ Expression = { $_.average_pair_uniqueness }; Descending = $true },
            target_1_pattern, target_2_pattern, target_3_pattern
)
for ($rank = 0; $rank -lt $rankedTargetTriplets.Count; $rank++) {
    $rankedTargetTriplets[$rank] | Add-Member -NotePropertyName rank -NotePropertyValue ($rank + 1)
}
$rankedTargetTriplets |
    Select-Object rank,
                  target_1_set, target_1_pattern,
                  target_2_set, target_2_pattern,
                  target_3_set, target_3_pattern,
                  minimum_pair_d4_distance, average_pair_d4_distance,
                  minimum_pair_uniqueness, average_pair_uniqueness,
                  triplet_uniqueness_score |
    Export-Csv -LiteralPath (Join-Path $outputFullDirectory "target_triplets_ranked.csv") -NoTypeInformation -Encoding UTF8
$rankedTargetTriplets |
    Select-Object -First 10 |
    Select-Object rank,
                  target_1_set, target_1_pattern,
                  target_2_set, target_2_pattern,
                  target_3_set, target_3_pattern,
                  minimum_pair_d4_distance, average_pair_d4_distance,
                  minimum_pair_uniqueness, average_pair_uniqueness,
                  triplet_uniqueness_score |
    Export-Csv -LiteralPath (Join-Path $outputFullDirectory "top_10_target_triplets.csv") -NoTypeInformation -Encoding UTF8

$audit = $relationships | ForEach-Object {
    [pscustomobject]@{
        set = $_.SetName
        target_pattern = $_.TargetPattern
        candidate_pattern = $_.CandidatePattern
        classification = $_.Classification
        fixed_overlap = $_.FixedOverlap
        fixed_hamming = $_.FixedHamming
        d4_min_distance = $_.D4MinimumDistance
        low_level_distance = $_.LowLevelDistance
        structural_distance = $_.StructuralDistance
        similarity_score = $_.SimilarityScore
        near_priority = $_.NearPriority
        far_priority = $_.FarPriority
    }
}
$audit | Export-Csv -LiteralPath (Join-Path $outputFullDirectory "relationship_audit.csv") -NoTypeInformation -Encoding UTF8
$unassigned | Export-Csv -LiteralPath (Join-Path $outputFullDirectory "unassigned_candidates.csv") -NoTypeInformation -Encoding UTF8
$masterManifest | Export-Csv -LiteralPath (Join-Path $outputFullDirectory "all_sets_manifest.csv") -NoTypeInformation -Encoding UTF8

$configuration = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    source_directory = $sourceFullDirectory
    output_directory = $outputFullDirectory
    source_pattern_count = $records.Count
    d4_class_count = @($records.Canonical | Sort-Object -Unique).Count
    target_mode = $TargetMode
    set_count = $targets.Count
    seed = $Seed
    target_patterns = @($targets.Pattern)
    near_rule = "fixed_hamming=2 and d4_min_distance=2"
    far_rule = "fixed_hamming>=4 and d4_min_distance>=4"
    rotation_dependent_rule = "fixed_hamming>=4 and d4_min_distance=2; excluded from that Target set"
    ranking = [ordered]@{
        Near_01 = "highest similarity_score"
        Far_01 = "highest far_priority: structural distance rewarded, low-level mismatch penalized"
    }
    candidate_library = "Candidates are ranked independently for every Target. A source pattern may appear in multiple sets, but only once within each set."
    target_uniqueness = "pair_score = 10*d4_min + 2*structural_distance + low_level_distance; triplets maximize their weakest pair first"
}
$configuration | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outputFullDirectory "selection_config.json") -Encoding UTF8

# Final integrity checks.
foreach ($setName in $setNames) {
    $setRows = @($masterManifest | Where-Object { $_.set -eq $setName })
    if (@($setRows | Where-Object { $_.role -eq "Target" }).Count -ne 1) {
        throw "$setName does not contain exactly one Target."
    }
    if (@($setRows.pattern | Sort-Object -Unique).Count -ne $setRows.Count) {
        throw "$setName contains the same exact pattern in more than one role."
    }
    $targetRow = $setRows | Where-Object { $_.role -eq "Target" }
    if (@($setRows | Where-Object { $_.role -ne "Target" -and $_.canonical_d4 -eq $targetRow.canonical_d4 }).Count -gt 0) {
        throw "$setName contains a Candidate that is D4-equivalent to its Target."
    }
    foreach ($row in $setRows) {
        $expectedPath = Join-Path (Join-Path $outputFullDirectory $setName) $row.copied_file
        if (-not (Test-Path -LiteralPath $expectedPath -PathType Leaf)) {
            throw "Missing copied file: $expectedPath"
        }
    }
}

$summary = @()
foreach ($setName in $setNames) {
    $rows = @($masterManifest | Where-Object { $_.set -eq $setName })
    $summary += [pscustomobject]@{
        Set = $setName
        Target = ($rows | Where-Object { $_.role -eq "Target" }).pattern
        Near = @($rows | Where-Object { $_.role -eq "Near" }).Count
        Far = @($rows | Where-Object { $_.role -eq "Far" }).Count
    }
}

Write-Output "Created all Target-relative ranked card sets and verified each set."
$summary | Format-Table -AutoSize | Out-String | Write-Output
Write-Output "Unassigned or excluded Target-Candidate relationships: $($unassigned.Count)"
Write-Output $outputFullDirectory
