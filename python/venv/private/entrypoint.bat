@ECHO OFF

SETLOCAL ENABLEEXTENSIONS
SETLOCAL ENABLEDELAYEDEXPANSION

@REM {RUNFILES_API}

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
    if not defined RUNFILES_DIR if not defined RUNFILES_MANIFEST_FILE (
        if exist "%~f0.runfiles" (
            set "RUNFILES_DIR=%~f0.runfiles"
        ) else if exist "%~f0.runfiles_manifest" (
            set "RUNFILES_MANIFEST_FILE=%~f0.runfiles_manifest"
        ) else if exist "%~f0.exe.runfiles_manifest" (
            set "RUNFILES_MANIFEST_FILE=%~f0.exe.runfiles_manifest"
        ) else (
            echo>&2 ERROR: cannot find runfiles
            exit /b 1
        )
    )

    call :runfiles_export_envvars

    call :rlocation "{PY_RUNTIME}" PY_RUNTIME
    call :rlocation "{VENV_PROCESS_WRAPPER}" VENV_PROCESS_WRAPPER
    call :rlocation "{VENV_CONFIG}" VENV_CONFIG
    call :rlocation "{MAIN}" MAIN

    if "{VENV_RUNFILES_COLLECTION}" NEQ "" (
        call :rlocation "{VENV_RUNFILES_COLLECTION}" RULES_VENV_RUNFILES_COLLECTION
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

%PY_RUNTIME% ^
    %VENV_PROCESS_WRAPPER% ^
    %VENV_CONFIG% ^
    %MAIN% ^
    %*
