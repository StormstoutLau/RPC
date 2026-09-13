# === O-25 P2 看板生成器：读取 ledger + run.json -> 内联单文件 dashboard.html (file:// 直开)
# 浏览器对 file:// 有同源限制，fetch 本地文件会被 CORS 拦 -> 数据在生成时内联为 JSON 字面量。
# 用法: powershell -File make-dashboard.ps1 [-Limit 50]  # 默认只渲染「已完成」总览
#       powershell -File make-dashboard.ps1 -Live -StationHost <host> -LivePort <port>
#           # -Live 时顺带从目标站 scp 拉运行中 .progress -> 「正在跑」tab（需站点引擎在线）
# 约定: 本文件必须保存为 UTF-8 BOM（Edit 会剥离 BOM，见 project_memory 纪律）。
param(
    [int]$Limit = 50,
    [switch]$Live,
    [string]$StationHost = '',     # --live 目标站 host（如 scott-lau-NEX.local）
    [int]$LivePort = 0             # 引擎端口
)
$ErrorActionPreference = 'Stop'
$ledgerPath = 'd:\RPC\ops\station-bin\agent-runs.log'
$projRoot   = 'D:\Paper'
$agentOut   = Join-Path $projRoot 'agent-out'
$outHtml    = 'd:\RPC\ops\station-bin\dashboard.html'
$WorkspaceRoot = '/home/scott-lau/agent-workspaces'

function Get-IsoTime([int64]$tsN) {
    # ledger ts = 17-digit yyyyMMddHHmmssSSS
    try {
        $s = $tsN.ToString()
        $fmt = $s.Substring(0,4) + '-' + $s.Substring(4,2) + '-' + $s.Substring(6,2) + 'T' + $s.Substring(8,2) + ':' + $s.Substring(10,2) + ':' + $s.Substring(12,2)
        $dt = [datetime]::ParseExact($fmt, 'yyyy-MM-ddTHH:mm:ss', $null)
        return $dt.ToString('yyyy-MM-dd HH:mm:ss')
    } catch { return $tsN.ToString() }
}

# ---- 1) ledger -> completed rows ----
$completed = @()
if (Test-Path $ledgerPath) {
    $rows = Get-Content $ledgerPath | Where-Object { $_ -match '^\d{14,},' }
    foreach ($r in ($rows | Select-Object -Last $Limit)) {
        $c = $r -split ','
        if ($c.Count -lt 5) { continue }
        $completed += [ordered]@{
            ts     = $c[0]
            label  = Get-IsoTime ([int64]$c[0])
            proj   = $c[1]
            model  = $c[2]
            sens   = $c[3]
            code   = [int]$c[4]
            queue_s= if ($c.Count -gt 5) { [int]$c[5] } else { 0 }
            run_s  = if ($c.Count -gt 6) { [int]$c[6] } else { 0 }
        }
    }
}

# ---- 2) run.json detail index (by ts) ----
$detail = @{}
if (Test-Path $agentOut) {
    Get-ChildItem -Path $agentOut -Directory -EA SilentlyContinue | ForEach-Object {
        $rj = Join-Path $_.FullName '.agent-run.json'
        if (-not (Test-Path $rj)) { return }
        try {
            $j = Get-Content $rj -Raw -Encoding UTF8 | ConvertFrom-Json
            $detail[$_.Name] = [ordered]@{
                status = if ($j.status) { [string]$j.status } else { '' }
                exit_code = if ($null -ne $j.exit_code) { [int]$j.exit_code } else { -1 }
                output_bps  = if ($null -ne $j.output_bps)  { [int]$j.output_bps }  else { 0 }
                output_bytes= if ($null -ne $j.output_bytes){ [int]$j.output_bytes } else { 0 }
                slot = if ($j.slot) { [ordered]@{ gated=[bool]$j.slot.gated; total=[int]$j.slot.total; busy=[int]$j.slot.busy; queue=[int]$j.slot.queue; action=[string]$j.slot.action } } else { $null }
                profile = if ($j.profile) { [ordered]@{ name=[string]$j.profile.name; context=[int]$j.profile.context; max_output=[int]$j.profile.max_output; flavor=[string]$j.profile.flavor } } else { $null }
                accept = if ($j.accept -and $null -ne $j.accept.passed) { [bool]$j.accept.passed } else { $null }
            }
        } catch { }
    }
}
foreach ($c in $completed) { if ($detail.ContainsKey($c.ts)) { $c.detail = $detail[$c.ts] } }

# ---- 3) optional live .progress (需站点引擎在线；失败/未指定则 live=null -> HTML 显示 no-live-data) ----
$liveData = $null
if ($Live) {
    if ($StationHost -and $LivePort -gt 0) {
        $via = 'd:\RPC\ops\station-bin\__probe_live.sh'
        @'
#!/bin/bash
# probe running .progress across workspace projects (ASCII only)
set -u
for d in "$HOME/agent-workspaces"/*/out; do
  [ -f "$d/.progress" ] || continue
  proj=$(basename "$(dirname "$d")")
  last=$(grep '^t=' "$d/.progress" | tail -1)
  echo "PROJ=$proj $last"
done
'@ | Set-Content $via -Encoding ASCII
            # O-25 在线实测修复(2026-09-12): PS Set-Content 写 CRLF, bash 解析 `done\r` 报
            # "未预期的文件结束符" -> scp 过去 bash 失败, -Live 链路跳过。显式规范为 LF。
            $raw = [System.IO.File]::ReadAllText($via)
            $raw = ($raw -replace "`r`n", "`n")
            [System.IO.File]::WriteAllText($via, $raw, (New-Object System.Text.UTF8Encoding($false)))
        try {
            scp -q -o ConnectTimeout=8 $via "${StationHost}:/tmp/__probe_live.sh"
            $po = ssh -o ConnectTimeout=8 $StationHost "bash /tmp/__probe_live.sh" 2>$null
            $pr = @()
            foreach ($ln in $po) {
                if ($ln -match 'PROJ=(\S+)\s+t=\S+\s+bytes=(\d+)\s+bytes_s=(\d+)') {
                    $pr += [ordered]@{ proj=$Matches[1]; bytes=[int]$Matches[2]; bytes_s=[int]$Matches[3] }
                }
            }
            if ($pr.Count -gt 0) { $liveData = $pr }
            Write-Host ("LIVE: {0} running task(s)" -f $pr.Count)
        } catch { Write-Host "LIVE: probe skipped ($($_.Exception.Message))" }
    } else {
        Write-Host 'LIVE: -Live 需配 -StationHost 与 -LivePort'
    }
}

# ---- 4) build inline JSON + HTML (单引号 here-string: 不展开 $, 承载 JS) ----
$payload = [ordered]@{
    generated = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    limit = $Limit
    completed = $completed
    live = $liveData
}
$json = $payload | ConvertTo-Json -Depth 6 -Compress
$json = $json.Replace('</', '<\/')   # 避免 </script 提前闭合

$tpl = @'
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>D6 Agent Dashboard</title>
<style>
  body{font-family:Consolas,Menlo,monospace;background:#0f1420;color:#d8e0f0;margin:0;padding:18px;}
  h1{font-size:18px;color:#7fd0ff;margin:0 0 4px 0;}
  .meta{color:#6a7890;font-size:11px;margin-bottom:14px;}
  .tabs button{background:#1a2336;color:#9fb0cf;border:1px solid #24304a;padding:6px 14px;margin-right:6px;cursor:pointer;border-radius:4px;}
  .tabs button.on{background:#24507a;color:#eaf4ff;border-color:#3f7bb0;}
  table{border-collapse:collapse;width:100%;font-size:12px;margin-top:10px;}
  th,td{border:1px solid #24304a;padding:4px 8px;text-align:left;white-space:nowrap;}
  th{background:#1a2336;color:#8fb0d8;}
  tr:nth-child(even){background:#151c2e;}
  .ok{color:#6fe08a;}.tw{color:#f0c060;}.no{color:#ff7a7a;}.na{color:#5a6a88;}
  .panel{display:none;}.panel.on{display:block;}
  .empty{color:#5a6a88;padding:10px 0;}
  details{margin:2px 0;}
  summary{cursor:pointer;color:#7fd0ff;}
</style>
</head>
<body>
<h1>D6 Agent Dashboard</h1>
<div class="meta">generated: <span id="gen"></span> &middot; file:// self-contained &middot; refresh = re-run make-dashboard.ps1</div>
<div class="tabs">
  <button id="tabC" class="on" onclick="switchTab('C')">已完成总览</button>
  <button id="tabL" onclick="switchTab('L')">正在跑 / Live</button>
</div>

<table id="tblC"></table>

<div id="livePanel" class="panel">
  <table id="tblL"></table>
</div>

<script>
var D = __DATA__;
document.getElementById('gen').textContent = D.generated;
var PROJ = {};

function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;'); }
function cls(status){
  if(status=='completed') return 'ok';
  if(status=='timeout') return 'tw';
  if(status=='failed') return 'no';
  return 'na';
}
function codeToStatus(c){
  if(c==0) return 'completed';
  if(c==6) return 'timeout';
  if(c==24) return 'slot-rejected';
  return 'failed';
}

// —— 已完成总览 ——
(function(){
  var h='<tr><th>ts</th><th>proj</th><th>model</th><th>sens</th><th>exit</th><th>status</th><th>run_s</th><th>queue_s</th><th>t/s</th><th>slot</th><th>detail</th></tr>';
  (D.completed||[]).forEach(function(c){
    var d=c.detail||{};
    var st = d.status || codeToStatus(c.code);
    var bps = d.output_bps||0;
    var slot = '';
    if(d.slot && d.slot.gated){ slot = d.slot.action; }
    else { slot = (d.slot&&d.slot.action)||(c.code==24?'reject':'-'); }
    var prof = d.profile? ('profile='+esc(d.profile.name)+' ctx='+esc(d.profile.context)+' max_out='+esc(d.profile.max_output)+' flavor='+esc(d.profile.flavor)) : '-';
    var acc = (d.accept==null) ? '-' : (d.accept?'accept ok':'accept fail');
    var detail='<details><summary>展开</summary><div>'+prof+'<br>accept: '+acc+
      (d.slot&&d.slot.gated?('<br>slot: total='+d.slot.total+' busy='+d.slot.busy+' queue='+d.slot.queue):'')+
      (d.output_bytes?('<br>output bytes: '+d.output_bytes):'')+'</div></details>';
    h+='<tr><td>'+esc(c.label)+'</td><td>'+esc(c.proj)+'</td><td>'+esc(c.model)+'</td><td>'+esc(c.sens)+
      '</td><td>'+esc(c.code)+'</td><td class="'+cls(st)+'">'+esc(st)+'</td><td>'+esc(c.run_s)+'</td><td>'+esc(c.queue_s)+
      '</td><td>'+esc(bps)+'</td><td>'+esc(slot)+'</td><td>'+detail+'</td></tr>';
  });
  document.getElementById('tblC').innerHTML = h;
})();

// —— 正在跑 / Live ——
(function(){
  var h='<tr><th>proj</th><th>bytes</th><th>bytes_s (t/s approx)</th><th>ETA note</th></tr>';
  if(D.live && D.live.length){
    D.live.forEach(function(p){
      h+='<tr><td>'+esc(p.proj)+'</td><td>'+esc(p.bytes)+'</td><td>'+esc(p.bytes_s)+
        '</td><td class="na">need max_output+baseline for t/s ETA</td></tr>';
    });
  } else {
    h='<tr><td colspan="4" class="empty">no-live-data: 站点引擎在线时用 make-dashboard.ps1 -Live -StationHost &lt;host&gt; -LivePort &lt;port&gt; 拉取运行中 .progress</td></tr>';
  }
  document.getElementById('tblL').innerHTML = h;
})();

function switchTab(t){
  document.getElementById('tabC').className = (t=='C')?'on':'';
  document.getElementById('tabL').className = (t=='L')?'on':'';
  document.querySelectorAll('.panel').forEach(function(p){p.className='panel'+(t=='L'?' on':'');});
}
</script>
</body>
</html>
'@

$html = $tpl.Replace('__DATA__', $json)
[System.IO.File]::WriteAllText($outHtml, $html, (New-Object System.Text.UTF8Encoding($true)))
Write-Host ("DASH_WRITTEN: {0} bytes -> {1}" -f $html.Length, $outHtml)
exit 0