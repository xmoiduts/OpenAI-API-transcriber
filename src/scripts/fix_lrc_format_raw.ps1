# 此为原料脚本，需二次加工成成熟工具。
# 读取云译工坊（https://t.cdgz.top/）复制出来的歌词，去除其换行，修改时间戳格式为 [mm:ss:cs(centi-second)]
$files = Get-ChildItem -Path "lyrics" -Filter "*.lrc"
foreach ($file in $files) {
    Write-Host "Processing $($file.Name)..."
    $lines = Get-Content -Path $file.FullName -Encoding UTF8
    $newLines = @()
    $pendingTimestamp = $null
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ($trimmed -match "^\[\d{2}:\d{2}[:\.]\d{2,3}\]$") {
            if ($pendingTimestamp -ne $null) {
                $newLines += $pendingTimestamp
            }
            $pendingTimestamp = $trimmed -replace '(:)(\d{2,3})\]$', '.$2]'
        } else {
            if ($pendingTimestamp -ne $null) {
                $newLines += "$pendingTimestamp$line"
                $pendingTimestamp = $null
            } else {
                $newLines += $line
            }
        }
    }
    if ($pendingTimestamp -ne $null) {
        $newLines += $pendingTimestamp
    }
    $newLines | Set-Content -Path $file.FullName -Encoding UTF8
}

