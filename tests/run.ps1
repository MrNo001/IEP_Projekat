# tests/run.ps1
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File .\tests\run.ps1
# Or:
#   cd tests; .\run.ps1

Set-Location $PSScriptRoot

# Equivalent to the active command in run.sh
python .\main.py `
  --type all `
  --with-authentication `
  --authentication-url http://127.0.0.1:5000 `
  --owner-url http://127.0.0.1:5001 `
  --customer-url http://127.0.0.1:5002 `
  --courier-url http://127.0.0.1:5003 `
  --with-blockchain `
  --provider-url http://127.0.0.1:8545 `
  --owner-private-key 0xb64be88dd6b89facf295f4fd0dda082efcbe95a2bb4478f5ee582b7efe88cf60 `
  --jwt-secret JWT_SECRET_DEV_KEY `
  --roles-field roles `
  --owner-role owner `
  --customer-role customer `
  --courier-role courier