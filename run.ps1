# run.ps1
# Activeer venv, ga naar projectmap en run CLI

# Ga naar projectmap
Set-Location "C:\software builds\cnc app"

# Activeer venv
. .\.venv\Scripts\Activate.ps1

# Run de CLI met meegegeven parameters
python .\src\cncapp\cli.py @args
