$taskName = "Antigravity_X_Growth_Engine"
$batPath = "d:\AI 프로젝트\MCP_notion-antigravity\run_x_growth.bat"

$action = New-ScheduledTaskAction -Execute $batPath

$times = @("05:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00")
$triggers = @()

foreach ($t in $times) {
    # 시간 형식을 엄격하게 맞추기 위해 DateTime 객체 사용
    $triggers += New-ScheduledTaskTrigger -Daily -At $t
}

# 기존 작업이 있다면 덮어쓰기 (-Force)
Register-ScheduledTask -TaskName $taskName -Trigger $triggers -Action $action -Description "Antigravity X Growth Engine - Daily Automation (5,8,10,12,14,16,18,20,22)" -Force

Write-Host "Task '$taskName' has been successfully registered with 9 daily triggers!"
