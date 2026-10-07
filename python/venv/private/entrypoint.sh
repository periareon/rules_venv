#!/bin/sh

if [ "{USE_RUNFILES}" = "1" ]; then

    if [ -z "${RUNFILES_DIR:-}" ] && [ -z "${RUNFILES_MANIFEST_FILE:-}" ]; then
        # Runfiles live beside the real script. When invoked through a symlink,
        # such as the extensionless alias Bazel builds next to this script, the
        # resolved path is tried after the invoked one.
        __rules_venv_self="$0"
        while [ -L "${__rules_venv_self}" ]; do
            __rules_venv_link="$(readlink "${__rules_venv_self}")"
            case "${__rules_venv_link}" in
                /*) __rules_venv_self="${__rules_venv_link}" ;;
                *) __rules_venv_self="$(dirname "${__rules_venv_self}")/${__rules_venv_link}" ;;
            esac
        done

        for __rules_venv_candidate in "$0" "${__rules_venv_self}"; do
            if [ -d "${__rules_venv_candidate}.runfiles" ]; then
                export RUNFILES_DIR="${__rules_venv_candidate}.runfiles"
                break
            elif [ -d "${__rules_venv_candidate}.exe.runfiles" ]; then
                export RUNFILES_DIR="${__rules_venv_candidate}.exe.runfiles"
                break
            elif [ -f "${__rules_venv_candidate}.runfiles_manifest" ]; then
                export RUNFILES_MANIFEST_FILE="${__rules_venv_candidate}.runfiles_manifest"
                break
            elif [ -f "${__rules_venv_candidate}.exe.runfiles_manifest" ]; then
                export RUNFILES_MANIFEST_FILE="${__rules_venv_candidate}.exe.runfiles_manifest"
                break
            fi
        done

        if [ -z "${RUNFILES_DIR:-}" ] && [ -z "${RUNFILES_MANIFEST_FILE:-}" ]; then
            echo >&2 "ERROR: cannot find runfiles"
            exit 1
        fi
    fi

    # {RUNFILES_API}

    runfiles_export_envvars

    if [ -n "{VENV_RUNFILES_COLLECTION}" ]; then
        export RULES_VENV_RUNFILES_COLLECTION="$(rlocation "{VENV_RUNFILES_COLLECTION}")"
    fi

    exec \
        "$(rlocation "{PY_RUNTIME}")" \
        "$(rlocation "{VENV_PROCESS_WRAPPER}")" \
        "$(rlocation "{VENV_CONFIG}")" \
        "$(rlocation "{MAIN}")" \
        "$@"

else

    if [ -n "{VENV_RUNFILES_COLLECTION}" ]; then
        export RULES_VENV_RUNFILES_COLLECTION="{VENV_RUNFILES_COLLECTION}"
    fi

    exec \
        "{PY_RUNTIME}" \
        "{VENV_PROCESS_WRAPPER}" \
        "{VENV_CONFIG}" \
        "{MAIN}" \
        "$@"
fi
