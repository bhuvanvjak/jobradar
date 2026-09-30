<#
  Copy to run.ps1 and fill in your keys. run.ps1 is gitignored - it is
  the one file in this project allowed to hold real secrets.

  Usage:
    .\run.ps1 scan
    .\run.ps1 apply --count 5
    .\run.ps1 apply --count 5 --dry-run
    .\run.ps1 review        # apply module's review queue  - localhost:5055
    .\run.ps1 webui         # jobradar's own scoring dashboard - localhost:8765
    .\run.ps1 run           # jobradar's own scan + weekly digest
#>
Set-Location $PSScriptRoot

# ---- pick ONE scoring provider (config.yaml llm.provider) ----
$env:GROQ_API_KEY = "your-groq-key-here"          # free, console.groq.com/home
# $env:XKIRO_API_KEY = "your-xkiro-key-here"
# $env:OPENROUTER_API_KEY = "your-openrouter-key-here"

# ---- only needed if apply.tailor_llm.provider is "anthropic" ----
# $env:ANTHROPIC_API_KEY = "your-anthropic-key-here"

# ---- cold email + weekly digest ----
$env:JOBRADAR_SMTP_PASSWORD = "your-gmail-app-password"

# ---- application tracking (apply.notion.enabled) ----
$env:NOTION_TOKEN = "your-notion-integration-token"
$env:NOTION_DATABASE_ID = "your-notion-database-id"

# @(...) around the whole if-statement matters: without it, PowerShell
# silently unwraps a single-element array result (e.g. just "scan") into
# a bare string, and splatting a string below then passes each of its
# CHARACTERS as a separate argument instead of the one word you meant.
$cliArgs = @( if ($args.Count -gt 0) { $args } else { "run" } )

if ($cliArgs[0] -eq "review") {
    # Long-running local server you run interactively - never scheduled,
    # so it prints straight to the console rather than through a log tee.
    & ".\.venv\Scripts\python.exe" -m jobradar.main @cliArgs
} elseif ($cliArgs[0] -eq "webui") {
    # jobradar's own dashboard is an ASGI app (jobradar/web/server.py),
    # served through uvicorn rather than `python -m jobradar.main`.
    & ".\.venv\Scripts\uvicorn.exe" jobradar.web.server:app --host 127.0.0.1 --port 8765
} else {
    # Scheduled runs (scan/apply/run/...) get appended to jobradar.log so a
    # Task Scheduler run is debuggable after the fact, while still echoing
    # to the console when you run this by hand.
    & ".\.venv\Scripts\python.exe" -m jobradar.main @cliArgs 2>&1 |
        Tee-Object -FilePath (Join-Path $PSScriptRoot "jobradar.log") -Append
}
