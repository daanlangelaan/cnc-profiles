# run.ps1
# Ga naar projectmap, activeer venv, zet src op PYTHONPATH en run de CLI

Set-Location "C:\software builds\cnc app"
. .\.venv\Scripts\Activate.ps1

# Belangrijk: laat Python in 'src' zoeken
$env:PYTHONPATH = "src"

# Geef alle meegegeven args door aan de CLI
python .\src\cncapp\cli.py @args
