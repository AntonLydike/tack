set __tack_var_commands add list migrate read-md remove pdf help

set __tack_var_commands_info "Add a new paper" "List all imported papers" "Migrate the database" "Import changes made in markdown" "Remove a paper from the database" "Add pdf" "Print help"

function __tack_completions_list_commands
    for i in (seq (count $__tack_var_commands))
        printf "%s\t%s\n" $__tack_var_commands[$i] $__tack_var_commands_info[$i]
    end
end

function __fish_is_nth_argument
    test (count (commandline -opc)) -eq (math $argv[1] + 1)
end

function __fish_last_arg_is_from
    contains (commandline -opc)[-1] $argv
end

function __tack_completions_list_papers
    tack-completions list jsonl | jq -r '"\(.doi)\t\(.conference | .[:20]) - \(.title | .[:60])"'
end

function __fish_arguments_match
    set -l cmdline (commandline -opc)
    for arg in $argv
        if test (count $cmdline) -eq 0
            return 1
        end
        if test "$arg" = '?' -o "$arg" = "$cmdline[1]"
            set cmdline $cmdline[2..]
            continue
        end
        return 1
    end
    test (count $cmdline) -eq 0
end

# remove files from completion
complete -c tack -f

# add base commands to completion
complete -c tack -n "__fish_arguments_match tack" -a "(__tack_completions_list_commands)"

## autocomplete papers for read-md, remove and pdf commands
## but only for the first arg
complete -c tack -n "__fish_last_arg_is_from read-md remove pdf" -a "(__tack_completions_list_papers)"
#
## if pdf was an argument, but not the last argument, complete files
## (basically complete `tack pdf * <file>``)
complete -c tack -n "__fish_arguments_match tack pdf '?'" -F

complete -c tack -n "__fish_arguments_match tack grep"` -C "rg"
complete -c tack -n "__fish_arguments_match tack git"` -C "git"
