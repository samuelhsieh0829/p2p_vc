@echo off
set /p version="Enter the version number: "
pyinstaller --noconfirm --onedir --console --icon "..\assets\icon\p2p.ico" ".\client.py" -n=client_%version% --distpath=./output/client_%version%
cd output/client_%version%
WinRAR a client_%version%.zip client_%version% -r
PAUSE