#!/usr/bin/env bash

if [[ "{USE_RUNFILES}" == "1" ]]; then

    if [[ -z "${RUNFILES_DIR:-}" && -z "${RUNFILES_MANIFEST_FILE:-}" ]]; then
        if [[ -d "$0.runfiles" ]]; then
            export RUNFILES_DIR="$0.runfiles"
        elif [[ -d "$0.exe.runfiles" ]]; then
            export RUNFILES_DIR="$0.exe.runfiles"
        elif [[ -f "$0.runfiles_manifest" ]]; then
            export RUNFILES_MANIFEST_FILE="$0.runfiles_manifest"
        elif [[ -f "$0.exe.runfiles_manifest" ]]; then
            export RUNFILES_MANIFEST_FILE="$0.exe.runfiles_manifest"
        else
            echo >&2 "ERROR: cannot find runfiles"
            exit 1
        fi
    fi

    # {RUNFILES_API}

    runfiles_export_envvars

    if [[ -n "{VENV_RUNFILES_COLLECTION}" ]]; then
        export VENV_RUNFILES_COLLECTION="$(rlocation "{VENV_RUNFILES_COLLECTION}")"
    fi

    exec \
        "$(rlocation "{PY_RUNTIME}")" \
        "$(rlocation "{VENV_PROCESS_WRAPPER}")" \
        "$(rlocation "{VENV_CONFIG}")" \
        "$(rlocation "{MAIN}")" \
        "$@"

else

    if [[ -n "{VENV_RUNFILES_COLLECTION}" ]]; then
        export VENV_RUNFILES_COLLECTION="{VENV_RUNFILES_COLLECTION}"
    fi

    exec \
        "{PY_RUNTIME}" \
        "{VENV_PROCESS_WRAPPER}" \
        "{VENV_CONFIG}" \
        "{MAIN}" \
        "$@"
fi
