@echo off
rem Bliznjica: run <ukaz> [argumenti]
rem   run                 -> pokaze pripravljen predlog narocila in ga po potrditvi (da/ne) izvede
rem   run povzetek        -> povzetek racuna
rem   run pozicije        -> branje (vrednost, gotovina, pozicije, pozicija X)
rem   run kupi ... / prodaj ... / stanje / najdi ... / preklici ...  -> bot
cd /d "%~dp0"
set UKAZ=%1
if "%UKAZ%"=="" goto predlog
for %%u in (povzetek vrednost gotovina pozicije pozicija) do if /i "%UKAZ%"=="%%u" goto beri
python t212_trgovanje.py %*
exit /b %errorlevel%
:predlog
python predlog.py
exit /b %errorlevel%
:beri
python t212_portfolio.py %*
exit /b %errorlevel%
