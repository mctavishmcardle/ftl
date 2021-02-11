# Tools for recording and restoring web browser state

These tools aim to make it easy to take a Firefox window containing a
particular set of tabs, each displaying a certain address, record it in a simple,
plain text data structure (JSON), and enable that browser window to be
recreated.

## Creating tab lists

Tab lists are JSON objects mapping workspace IDs to lists of maps from window
IDs to lists of the URLs of the tabs open in those windows in those workspaces.

### `ftl`

`ftl` is responsible for creating tab lists initially.

    Usage: ftl [OPTIONS]

      Write Firefox tab URLs out in JSON format.

    Options:
      --workspace TEXT                A workspace whose windows' tabs' URLs should
                                      be written

      --window TEXT                   A specific window whose tabs' URLs should be
                                      written

      --session-dir DIRECTORY         A Firefox session directory to get URL
                                      information from

      --find-session-dir / --dont-find-session-dir
                                      Should this script attempt to automatically
                                      determine the session directory?  [default:
                                      True]

      --firefox-dir TEXT              The directory that should searched to find
                                      the session directory  [default:
                                      $HOME/.mozilla/firefox]

      --target FILENAME               The location to write the URL information to
      --help                          Show this message and exit.

It can be used either to write tab lists to a particular file, by passing a
file name into the `--target` option, or to write to standard output:

    $ ftl --find-session-dir --workspace 1 --window 0 --target -
    {
        "1": {
            "0": [
                "<some_url>",
                "<other_url>"
            ]
        }
    }

### `ftl-get-workspace`

This script provides the ID of the current workspace, according to `X`:

    $ ftl-get-workspace
    1

It can be used together with `ftl` to write the tabs open in any windows in the
current workspace:

    ftl --find-session-dir --workspace $(ftl-get-workspace) --target tabs.json


## Restoring tab lists


### `ftr`

This script opens up new Firefox windows whose tab structure matches the input
tab list. It can take input tab list files as filename arguments, or read a tab
list from standard input:

    cat tabs.json | ftr

### `jq`

Tab lists are human-readable, plain text data structures, and they can be edited
by hand to include or remove particular URLs or rearrange the windows that tabs
are assigned to.

Examining the implementation of `ftr` reveals that it makes use of `jq` to
manipulate the structure of the input tab list JSON object on the fly. Since
`ftr` can take input either from a file argument or standard input, `jq` can be
used to filter or rearrange a tab list before restoring it (though the
map-to-map-to-list structure of the tab list must be preserved).

For example, restoring a tab list, but where each window in each workspace only
contains the tabs in the list whose URLs match a particular search string:

    cat tabs.json \
    | jq 'map_values(map_values(map(select((. | contains("<search string>"))))))' \
    | ftr
