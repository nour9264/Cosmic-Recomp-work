#pragma once

inline constexpr const wchar_t* cinematic_clips[] = {
    L"l_chin/chin_a", L"l_chin/chin_b", L"l_mili/mili_a", L"l_mili/mili_b",
    L"l_pari/pari_a", L"l_pari/pari_b", L"l_pari/pari_c", L"l_pari/pari_d",
    L"l_romd/romd_a", L"l_romd/romd_c", L"l_romn/romn_a", L"l_romn/romn_b",
    L"l_rush/rush_a", L"l_rush/rush_b", L"l_tokd/tokd_a", L"l_tokd/tokd_b",
    L"l_tokd/tokd_c", L"l_tokn/tokn_a", L"l_tokn/tokn_b",
};

// Windows' ZIP reader streams entries directly to a private staging folder.
inline constexpr wchar_t cinematic_zip_script[] = LR"PS(
$ErrorActionPreference = 'Stop'
$stage = $null
$lock = $null
$zip = $null
$code = 1
$install = [IO.Path]::GetFullPath($install)
function Remove-StagingFolder($path) {
    $full = [IO.Path]::GetFullPath($path)
    if ([IO.Path]::GetDirectoryName($full) -eq $install -and
        [IO.Path]::GetFileName($full) -match '^cinematics-import-[0-9a-f]{32}(-previous)?$') {
        [IO.Directory]::Delete($full, $true)
    }
}
try {
    $lock = [IO.File]::Open((Join-Path $install 'running.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $code = 2
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    $expected = @{}
    foreach ($clip in $clips) {
        $expected.Add($clip + '.wmv', $true)
        $expected.Add($clip + '.subtitles.tsv', $true)
    }
    $entries = @{}
    $legacyIntroSubtitle = $null
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName.Replace('\','/')
        if ($name.StartsWith('cinematics/')) { $name = $name.Substring(11) }
        if ($name -eq '' -or $name -match '^l_[a-z]+/$') { continue }
        # Older packs included a second copy of this subtitle at the pack root.
        if ($name -ceq 'romd_a.subtitles.tsv') {
            if ($legacyIntroSubtitle -or $entry.Length -le 0 -or $entry.Length -gt 128KB) { exit 2 }
            $legacyIntroSubtitle = $entry
            continue
        }
        $key = if ($name.EndsWith('.mp4')) { $name.Substring(0, $name.Length - 4) + '.wmv' } else { $name }
        if (!$expected.ContainsKey($key) -or $entries.ContainsKey($key)) { exit 2 }
        $limit = if ($key.EndsWith('.wmv')) { 768MB } else { 128KB }
        if ($entry.Length -le 0 -or $entry.Length -gt $limit) { exit 2 }
        $entries.Add($key, @{ Name = $name; Entry = $entry })
    }
    if ($entries.Count -ne $expected.Count) { exit 2 }
    if ($legacyIntroSubtitle) {
        $canonical = $entries['l_romd/romd_a.subtitles.tsv'].Entry
        if ($legacyIntroSubtitle.Length -ne $canonical.Length) { exit 2 }
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $duplicateStream = $legacyIntroSubtitle.Open()
            try { $duplicateHash = [Convert]::ToBase64String($sha.ComputeHash($duplicateStream)) }
            finally { $duplicateStream.Dispose() }
            $canonicalStream = $canonical.Open()
            try { $canonicalHash = [Convert]::ToBase64String($sha.ComputeHash($canonicalStream)) }
            finally { $canonicalStream.Dispose() }
            if ($duplicateHash -cne $canonicalHash) { exit 2 }
        } finally { $sha.Dispose() }
    }

    $code = 3
    $stage = Join-Path $install ('cinematics-import-' + [Guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($stage)
    foreach ($key in $expected.Keys) {
        $name = $entries[$key].Name
        $entry = $entries[$key].Entry
        $dest = Join-Path $stage $name
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($dest))
        $inputStream = $entry.Open()
        try {
            $output = [IO.File]::Open($dest, 'CreateNew', 'Write', 'None')
            try {
                $buffer = New-Object byte[] (1MB)
                $written = 0L
                while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $written += $count
                    if ($written -gt $entry.Length) { exit 2 }
                    $output.Write($buffer, 0, $count)
                }
                if ($written -ne $entry.Length) { exit 2 }
            } finally { $output.Dispose() }
        } finally { $inputStream.Dispose() }
        if ($key.EndsWith('.wmv')) {
            $video = [IO.File]::OpenRead($dest)
            try {
                $header = New-Object byte[] 16
                if ($video.Read($header, 0, 16) -ne 16) { exit 2 }
                if ($name.EndsWith('.mp4')) {
                    if ([Text.Encoding]::ASCII.GetString($header, 4, 4) -cne 'ftyp') { exit 2 }
                } elseif ([BitConverter]::ToString($header) -ne '30-26-B2-75-8E-66-CF-11-A6-D9-00-AA-00-62-CE-6C') { exit 2 }
            } finally { $video.Dispose() }
        } else {
            $last = 0L
            $lines = [IO.File]::ReadAllLines($dest, [Text.UTF8Encoding]::new($false, $true))
            if ($lines.Length -lt 1 -or $lines.Length -gt 256) { exit 2 }
            foreach ($line in $lines) {
                if ($line -notmatch '^(\d{1,8})\t(\d{1,8})\t[^\t]+$') { exit 2 }
                $start = [long]$Matches[1]
                $end = [long]$Matches[2]
                if ($start -lt $last -or $end -le $start) { exit 2 }
                $last = $end
            }
        }
    }
    [IO.File]::WriteAllText((Join-Path $stage '.cosmic-cinematics-pack'), 'v1')
    $target = Join-Path $install 'cinematics'
    $backup = $stage + '-previous'
    if ([IO.Directory]::Exists($target)) { [IO.Directory]::Move($target, $backup) }
    try { [IO.Directory]::Move($stage, $target) }
    catch {
        if ([IO.Directory]::Exists($backup)) { [IO.Directory]::Move($backup, $target) }
        throw
    }
    $stage = $null
    if ([IO.File]::Exists((Join-Path $backup '.cosmic-cinematics-pack'))) {
        try { Remove-StagingFolder $backup } catch {}
    }
    exit 0
} catch { exit $code }
finally {
    if ($zip) { $zip.Dispose() }
    if ($lock) { $lock.Dispose() }
    if ($stage -and [IO.Directory]::Exists($stage)) {
        try { Remove-StagingFolder $stage } catch {}
    }
}
)PS";
