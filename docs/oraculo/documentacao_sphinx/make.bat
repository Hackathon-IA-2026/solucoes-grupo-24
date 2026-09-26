@ECHO OFF
REM Construcao da documentacao do O.R.A.C.U.L.O. em Windows.
pushd %~dp0
set SOURCEDIR=source
set BUILDDIR=build
set ORACULO_OFFLINE=1
if "%1" == "" goto html
if "%1" == "html" goto html
if "%1" == "clean" goto clean
if "%1" == "strict" goto strict
goto html

:html
python -m sphinx -b html -d "%BUILDDIR%\doctrees" "%SOURCEDIR%" "%BUILDDIR%\html"
echo Pronto: %BUILDDIR%\html\index.html
goto end

:strict
python -m sphinx -b html -W --keep-going -d "%BUILDDIR%\doctrees" "%SOURCEDIR%" "%BUILDDIR%\html"
goto end

:clean
if exist "%BUILDDIR%" rmdir /s /q "%BUILDDIR%"
echo build removido
goto end

:end
popd
