param(
    [string]$TaskName = "Richping Daily"
)

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    [pscustomobject]@{
        TaskName = $TaskName
        Registration = "NOT_FOUND"
        ExpectedCommand = "powershell.exe -NoProfile -File C:\richping\scripts\daily.ps1"
        ExpectedSchedule = "Daily 08:00 Asia/Seoul"
    }
    exit 1
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State
    Principal = $task.Principal.UserId
    Action = (($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join "; ")
    Trigger = (($task.Triggers | ForEach-Object { $_.StartBoundary }) -join "; ")
    WakeToRun = $task.Settings.WakeToRun
    LastRunTime = $info.LastRunTime
    LastTaskResult = $info.LastTaskResult
    NextRunTime = $info.NextRunTime
}
