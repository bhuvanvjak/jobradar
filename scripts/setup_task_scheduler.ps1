<#
  Registers two Windows Task Scheduler tasks that run a full
  scan-then-apply cycle at 9:00 AM and 9:00 PM every day: fetch fresh
  postings, score them, then tailor a resume and apply to the best
  5 unapplied jobs.

  Review this script before running it. Run it yourself once run.ps1
  exists and you've tested manually (.\run.ps1 apply --count 5 --dry-run):

      cd "C:\Randomchetta\Hook or Crook\jobradar"
      .\scripts\setup_task_scheduler.ps1
#>

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$RunScript = "$ProjectRoot\run.ps1"

if (-not (Test-Path $RunScript)) {
    Write-Error "run.ps1 not found. Copy run.example.ps1 to run.ps1 and fill in your keys first."
    exit 1
}

function Register-ScanApplyTask {
    param([string]$TaskName, [string]$Time)

    # A task can chain multiple actions; this one runs a scan, then applies
    # to the best 5 unapplied jobs that scan turned up.
    $scanAction = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`" scan" `
        -WorkingDirectory $ProjectRoot
    $applyAction = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`" apply --count 5" `
        -WorkingDirectory $ProjectRoot

    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
    Register-ScheduledTask -TaskName $TaskName -Action $scanAction, $applyAction `
        -Trigger $trigger -Settings $settings `
        -Description "jobradar - scan + apply to 5 jobs ($TaskName)" -Force
    Write-Host "Registered task '$TaskName' at $Time"
}

Register-ScanApplyTask -TaskName "JobRadar_Morning" -Time "09:00"
Register-ScanApplyTask -TaskName "JobRadar_Evening" -Time "21:00"

Write-Host ""
Write-Host "Done. View/edit these tasks anytime in Task Scheduler (taskschd.msc)."
Write-Host "Your PC must be on (not asleep) at 9 AM / 9 PM for these to fire."
Write-Host "Each run's output is appended to jobradar.log in this folder."
