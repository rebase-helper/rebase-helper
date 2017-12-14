#!/bin/sh

if [ -z "${REPOSITORY}" ]; then
    if [ -n "${PACKAGE}" ]; then
        REPOSITORY="https://src.fedoraproject.org/rpms/${PACKAGE%#*}.git"

        if [ "${PACKAGE#*#}" != "${PACKAGE}" ]; then
            REPOSITORY="${REPOSITORY}#${PACKAGE#*#}"
        fi
    else
        echo "PACKAGE or REPOSITORY must be specified!"
        exit 1
    fi
fi

git clone "${REPOSITORY%#*}" dist-git
cd dist-git

ref="${REPOSITORY#*#}"

if [ "${ref}" != "${REPOSITORY}" ]; then
    case "${ref%%=*}" in
        commit|tag)
            ref="${ref##*=}"
            ;;

        branch)
            ref="origin/${ref##*=}"
            ;;

        *)
            ref=
            ;;
    esac

    if [ -n "${ref}" ]; then
        git checkout --force --no-track -B rebase "${ref}"
    fi
fi

exec rebase-helper --results-dir .. --buildtool rpmbuild $@
