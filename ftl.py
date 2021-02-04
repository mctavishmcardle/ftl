import fnmatch
import io
import itertools
import json
import os
import pathlib
import typing

import click
import lz4.block

# the pattern to match firefox session directories to
SESSION_DIR_PATTERN = "*.default*"

# the data stored for a whole firefox session
Session = typing.NewType("Session", typing.Dict)
# the data stored for a single firefox window, within a session's data
Window = typing.NewType("Window", typing.Dict)


def get_session_data(recovery_file_path: pathlib.Path) -> Session:
    """Extract, read, & load Firefox session data

    Args:
        recovery_file_path: The path to the session data file
    """
    with open(recovery_file_path, "rb") as session_contents:
        # skip past 8 initial bits, which firefox uses as a header
        session_contents.read(8)

        return json.loads(lz4.block.decompress(session_contents.read()).decode("utf-8"))


def get_window_workspace_id(window: Window) -> str:
    """Extract the workspace ID from a window

    Args:
        window: The window whose workspace ID to retrieve
    """
    return window["workspaceID"]


# The urls of each of the tabs in a window
TabUrls = typing.List[str]
# The urls of each of the windows in a workspace
WindowUrls = typing.Dict[str, TabUrls]
# The urls of several workspaces
WorkspaceUrls = typing.Dict[str, WindowUrls]


def get_window_tab_urls(window: Window) -> TabUrls:
    """Get the URLs in a window

    Note:
        The session data preserves history for each tab; the extracted URLs will
        be only the current URL for each tab

    Args:
        window: The window whose URLs to extract
    """
    return [
        # history information is preserved in the tab, so we need to grab the
        # 'current' url
        tab["entries"][int(tab["index"]) - 1]["url"]
        for tab in window["tabs"]
    ]


def get_urls_by_window_by_workspace(
    session: Session,
) -> WorkspaceUrls:
    """Construct a map from workspace ID to its windows' tabs' URLs

    Args:
        session: The session from which to construct the map
    """
    return {
        workspace_id: {
            str(index): get_window_tab_urls(window)
            for index, window in enumerate(windows)
        }
        for workspace_id, windows in itertools.groupby(
            sorted(session["windows"], key=get_window_workspace_id),
            get_window_workspace_id,
        )
    }


def select_urls(
    all_workspace_urls: WorkspaceUrls,
    workspace_ids: typing.Tuple[str],
    window_ids: typing.Tuple[str],
) -> WorkspaceUrls:
    """Filter down to only some URLs

    Args:
        all_workspace_urls: The full set of workspaces, their windows, & their
            tabs
        workspace_ids: The IDs of the workspaces to select. If no IDs are provided,
            all workspaces will be selected.
        window_ids: The IDs of the windows to select. If no IDs are provided, all
            windows will be selected.

    Returns:
        The selected URLs
    """
    return {
        workspace_id: {
            window_id: tab_urls
            for window_id, tab_urls in windows.items()
            if window_id in (window_ids or windows.keys())
        }
        for workspace_id, windows in all_workspace_urls.items()
        if workspace_id in (workspace_ids or windows.keys())
    }


def to_pathlib_callback(
    context, param, path: typing.Optional[str]
) -> typing.Optional[pathlib.Path]:
    """A `click` option callback to cast a path to a `Path`

    Args:
        context: The `click` context; unused
        param: The current param being evaluated; unused
        path: The path; if `None`, will be passed through

    Returns:
        The converted path
    """
    if path is None:
        return None

    return pathlib.Path(path)


def search_for_session_dir(firefox_dir: pathlib.Path) -> pathlib.Path:
    """Searches for the most recently modified Firefox session dir

    Args:
        firefox_dir: The Firefox data dir to search inside - e.g. `~/.mozilla/firefox`

    Returns:
        The path to the session dir
    """
    session_dir_entry = max(
        (
            dir_entry
            for dir_entry in os.scandir(firefox_dir)
            if dir_entry.is_dir()
            and fnmatch.fnmatch(
                dir_entry.name,
                SESSION_DIR_PATTERN,
            )
        ),
        # pick the most recently modified directory - that should correspond
        # to the current session
        key=lambda dir_entry: dir_entry.stat().st_mtime,
    )

    return pathlib.Path(session_dir_entry.path)


@click.command(help="Write Firefox tab URLs out in JSON format")
@click.option(
    "--workspace",
    help="A workspace whose windows' tabs' URLs should be written",
    multiple=True,
)
@click.option(
    "--window",
    help="A specific window whose tabs' URLs should be written",
    multiple=True,
)
@click.option(
    "--session-dir",
    help="A Firefox session directory to get URL information from",
    type=click.Path(
        exists=True,
        file_okay=False,
        readable=True,
    ),
    callback=to_pathlib_callback,
)
@click.option(
    "--find-session-dir/--dont-find-session-dir",
    help="Should this script attempt to automatically determine the session directory?",
    default=False,
    show_default=True,
)
@click.option(
    "--firefox-dir",
    help="The directory that should searched to find the session directory",
    default=str(pathlib.Path(os.environ["HOME"]) / ".mozilla" / "firefox"),
    show_default=True,
    callback=to_pathlib_callback,
)
@click.option(
    "--target",
    help="The location to write the URL information to",
    type=click.File("w"),
    default="-",
)
def cli(
    workspace: typing.Tuple[str],
    window: typing.Tuple[int],
    session_dir: pathlib.Path,
    find_session_dir: bool,
    firefox_dir: pathlib.Path,
    target: io.TextIOBase,
) -> None:
    if find_session_dir:
        # prefer searching
        session_dir = search_for_session_dir(firefox_dir)
    elif session_dir:
        # no need to do anything if the session dir is passed in directly
        pass
    else:
        # noop if nothing is configured
        return

    all_workspace_urls = get_urls_by_window_by_workspace(
        get_session_data(session_dir / "sessionstore-backups" / "recovery.jsonlz4")
    )
    output_object = select_urls(all_workspace_urls, workspace, window)

    target.write(json.dumps(output_object, indent=4))
