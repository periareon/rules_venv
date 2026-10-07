@ECHO OFF

SETLOCAL ENABLEEXTENSIONS
SETLOCAL ENABLEDELAYEDEXPANSION

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


@REM When started directly from `bazel-bin` rather than via `bazel run` or
@REM `bazel test`, the runfiles tree sits beside this script. Manifest discovery
@REM is handled by `:runfiles_export_envvars` from the appended runfiles library,
@REM which also ensures both RUNFILES_DIR and RUNFILES_MANIFEST_FILE are exported
@REM for child processes.
if {USE_RUNFILES}==1 (
    if not defined RUNFILES_DIR if exist "%~f0.runfiles\" set "RUNFILES_DIR=%~f0.runfiles"

    call :runfiles_export_envvars
    if errorlevel 1 (
        echo>&2 ERROR: cannot find runfiles
        exit /b 1
    )

    call :rlocation "{PY_RUNTIME}" PY_RUNTIME
    if errorlevel 1 exit /b 1
    call :rlocation "{VENV_PROCESS_WRAPPER}" VENV_PROCESS_WRAPPER
    if errorlevel 1 exit /b 1
    call :rlocation "{VENV_CONFIG}" VENV_CONFIG
    if errorlevel 1 exit /b 1
    call :rlocation "{MAIN}" MAIN
    if errorlevel 1 exit /b 1

    if "{VENV_RUNFILES_COLLECTION}" NEQ "" (
        call :rlocation "{VENV_RUNFILES_COLLECTION}" RULES_VENV_RUNFILES_COLLECTION
        if errorlevel 1 exit /b 1
    )
) else (
    call :slocation "{PY_RUNTIME}" PY_RUNTIME
    call :slocation "{VENV_PROCESS_WRAPPER}" VENV_PROCESS_WRAPPER
    call :slocation "{VENV_CONFIG}" VENV_CONFIG
    call :slocation "{MAIN}" MAIN

    if "{VENV_RUNFILES_COLLECTION}" NEQ "" (
        call :slocation "{VENV_RUNFILES_COLLECTION}" RULES_VENV_RUNFILES_COLLECTION
    )
)

"%PY_RUNTIME%" ^
    "%VENV_PROCESS_WRAPPER%" ^
    "%VENV_CONFIG%" ^
    "%MAIN%" ^
    %*

@REM Exit before falling through into the runfiles library appended below.
exit /b %ERRORLEVEL%

@REM {RUNFILES_API}
