# Bash completition for rebase-helper tool
# Author: Tomas Hozza <thozza@redhat.com>

# fill LOCAL_ARCHIVES variable with supported archive names
_local_archives()
{
    # supported archive extensions
    extensions=".tar .tar.gz .tgz .tar.xz .tar.bz2 .zip"
    LOCAL_ARCHIVES=()
    for ext in $extensions; do
        LOCAL_ARCHIVES=("${LOCAL_ARCHIVES[@]}" $( ls | grep $ext\$ ))
    done
}

# fill --*tool arguments into ARGUMENTS variable
_complete_tool_arguments()
{
    patchtools="patch git"
    buildtools="mock rpmbuild"
    difftools="meld"
    pkgcomparetools="pkgdiff"
    outputtools="text"
    
    if [ $# != 1 ]; then
        ARGUMENTS=()
    else
        cmd="$( echo $1 | sed -E s'/--(.*)/\1/'g )s"
        ARGUMENTS=${!cmd}
    fi
}

_rebase-helper()
{
    local cur prev opts

    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # basic commands
    opts="-h --help \
          -v --verbose \
          -p --patch-only \
          -b --build-only \
          --patchtool \
          --buildtool \
          --difftool \
          --pkgcomparetool \
          --outputtool \
          -w --keep-workspace \
          --not-download-sources \
          -c --continue"

    # complete arguments of some commands
    case "${prev}" in
        --*tool)
            _complete_tool_arguments ${prev}
            COMPREPLY=( $(compgen -W "${ARGUMENTS}" -- ${cur}) )
            return 0
            ;;
        *)
            ;;
    esac

    _local_archives
    # complete options as well supported archives in current directory
    COMPLETE="${LOCAL_ARCHIVES[@]} ${opts[@]}"
    COMPREPLY=( $(compgen -W "${COMPLETE}" -- ${cur}) )
    return 0
}

complete -F _rebase-helper rebase-helper
