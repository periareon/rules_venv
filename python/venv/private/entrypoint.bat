@ECHO OFF

SETLOCAL ENABLEEXTENSIONS
SETLOCAL ENABLEDELAYEDEXPANSION

@REM Usage of rlocation function:
@REM        call :rlocation <runfile_path> <abs_path>
@REM        The rlocation function maps the given <runfile_path> to its absolute
@REM        path and stores the result in a variable named <abs_path>.
@REM        This function fails if the <runfile_path> doesn't exist in mainifest
@REM        file.
:: Start of rlocation
goto :rlocation_end
:rlocation
if "%~2" equ "" (
    echo>&2 ERROR: Expected two arguments for rlocation function.
    exit 1
)
if "%RUNFILES_MANIFEST_ONLY%" neq "1" (
    set %~2=%~1
    exit /b 0
)
if exist "%RUNFILES_DIR%" (
    set RUNFILES_MANIFEST_FILE=%RUNFILES_DIR%_manifest
)
if "%RUNFILES_MANIFEST_FILE%" equ "" (
    set RUNFILES_MANIFEST_FILE=%~f0.runfiles\MANIFEST
)
if not exist "%RUNFILES_MANIFEST_FILE%" (
    set RUNFILES_MANIFEST_FILE=%~f0.runfiles_manifest
)
set MF=%RUNFILES_MANIFEST_FILE:/=\%
if not exist "%MF%" (
    echo>&2 ERROR: Manifest file %MF% does not exist.
    exit 1
)
set runfile_path=%~1
for /F "tokens=2* usebackq" %%i in (`%SYSTEMROOT%\system32\findstr.exe /l /c:"!runfile_path! " "%MF%"`) do (
    set abs_path=%%i
)
if "!abs_path!" equ "" (
    echo>&2 ERROR: !runfile_path! not found in runfiles manifest
    exit 1
)
set %~2=!abs_path!
exit /b 0
:rlocation_end


@REM Function to replace forward slashes with backslashes.
goto :slocation_end
:slocation
set "input=%~1"
set "varName=%~2"
set "output="

@REM Replace forward slashes with backslashes
set "output=%input:/=\%"

@REM Assign the sanitized path to the specified variable
set "%varName%=%output%"
exit /b 0
:slocation_end


if {USE_RUNFILES}==1 (
    call :rlocation "{PY_RUNTIME}" PY_RUNTIME
    call :rlocation "{VENV_PROCESS_WRAPPER}" VENV_PROCESS_WRAPPER
    call :rlocation "{VENV_CONFIG}" VENV_CONFIG
    call :rlocation "{MAIN}" MAIN

    if "{VENV_RUNFILES_COLLECTION}" NEQ "" (
        call :rlocation "{VENV_RUNFILES_COLLECTION}" VENV_RUNFILES_COLLECTION
    )
) else (
    call :slocation "{PY_RUNTIME}" PY_RUNTIME
    call :slocation "{VENV_PROCESS_WRAPPER}" VENV_PROCESS_WRAPPER
    call :slocation "{VENV_CONFIG}" VENV_CONFIG
    call :slocation "{MAIN}" MAIN

    if "{VENV_RUNFILES_COLLECTION}" NEQ "" (
        call :slocation "{VENV_RUNFILES_COLLECTION}" VENV_RUNFILES_COLLECTION
    )
)

%PY_RUNTIME% ^
    %VENV_PROCESS_WRAPPER% ^
    %VENV_CONFIG% ^
    %MAIN% ^
    %*
