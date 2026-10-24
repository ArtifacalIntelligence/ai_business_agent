Remove-Item Env:WEBHOOK_URL -ErrorAction SilentlyContinue
$env:N8N_EDITOR_BASE_URL = "http://localhost:5678"
$env:WEBHOOK_URL = "http://localhost:5678/"
Set-Location $HOME
n8n start