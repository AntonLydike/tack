set -l commands add list migrate read-md remove help

set -l commands_info "Add a new paper" "List all imported papers" "Migrate the database" "Import changes made in markdown" "Remove a paper from the database" "Print help"

function __tack_completions_list_commands
    for i in (seq (count $commands))
        printf "%s\t%s\n" $commands[$i] $commands_info[$i]
    end
end

function __tack_completions_list_papers
    tack list --json | jq -r '"\(.doi)\t\(.conference | .[:20]) - \(.title | .[:60])"'
end

complete -c tack -n "not __fish_seen_subcommand_from $commands" -a "(__tack_completions_list_commands)"
complete -c tack -f

complete -c tack -n "__fish_seen_subcommand_from read-md remove" -a "(__tack_completions_list_papers)"
