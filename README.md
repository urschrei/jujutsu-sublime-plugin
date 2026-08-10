# Jujutsu

[Jujutsu](https://www.jj-vcs.dev/latest/) (`jj`) integration for Sublime Text.

Jujutsu provides status bar information and jj commands accessible via the command palette. It is designed for **colocated repositories** (where both `.jj` and `.git` exist), letting Sublime's built-in git integration handle diff gutters and other git-specific features while Jujutsu adds jj workflow commands.

## Features

- **Status bar**: Shows current change ID, description, and bookmark information
- **Command palette integration**: Common jj operations available via quick commands

## Requirements

- Sublime Text 4
- [Jujutsu](https://github.com/martinvonz/jj) installed and available in PATH (or configured via settings)

## Installation

### Package Control

1. Open the command palette (Ctrl+Shift+P / Cmd+Shift+P)
2. Run "Package Control: Install Package"
3. Search for "Jujutsu" and install

### Manual Installation

1. Clone or download this repository
2. Copy the `Jujutsu` folder to your Sublime Text Packages directory:
   - macOS: `~/Library/Application Support/Sublime Text/Packages/`
   - Linux: `~/.config/sublime-text/Packages/`
   - Windows: `%APPDATA%\Sublime Text\Packages\`
3. Restart Sublime Text

## Commands

All commands are available via the command palette (Ctrl+Shift+P / Cmd+Shift+P) with the "JJ:" prefix.

### Basic Operations

| Command | Description |
|---------|-------------|
| **JJ: New Change** | Create a new change (optionally with a message) |
| **JJ: Describe** | Set or update the description of the current change |
| **JJ: Commit** | Commit current change (describe + new) |
| **JJ: Split Change** | Interactively split the current change (select hunks/lines for first commit) |
| **JJ: Abandon Change** | Abandon the current change (with confirmation) |
| **JJ: Undo Last Operation** | Undo the last jj operation |
| **JJ: Fix (Run Formatters)** | Run configured formatters (`fix.tools`) over the mutable stack; only modified lines are formatted |
| **JJ: Duplicate Change** | Duplicate the current change in place |
| **JJ: Revert Change...** | Select a change; a new change undoing it is created on top of @ |
| **JJ: Parallelize Changes...** | Select two or more changes in a chain and make them siblings |
| **JJ: Operation Log (Restore)...** | Browse the operation log and restore the repository to an earlier operation (safe multi-step undo) |
| **JJ: Refresh Status** | Refresh status bar |

### Running Commands Across a Stack

"JJ: Run Command on Revset..." runs a shell command once per change in a revset (default configurable via `run_default_revset`). Each change is checked out into a private working copy by `jj run --ignore-changes`, so neither the commits nor your working copy are modified. Results appear in an output panel: a PASS/FAIL line per change, captured output for failures, and a final summary. The per-change timeout is configurable via `run_command_timeout` (default 600 seconds). Requires jj 0.43 or later.

### Restoring and Discarding Changes

| Command | Description |
|---------|-------------|
| **JJ: Restore File (Discard File Changes)** | Restore the current file to its parent-revision state (with confirmation) |
| **JJ: Discard Changes (Select Hunks)...** | Select specific hunks/lines to discard (same UI as split); everything else is kept |

Both operations are recorded in the operation log, so they can be undone with "JJ: Undo Last Operation" or "JJ: Operation Log (Restore)...".

### Squash Operations

| Command | Description |
|---------|-------------|
| **JJ: Squash...** | Interactive squash with multi-select sources and destination picker |
| **JJ: Squash Interactive...** | Select destination, then choose specific hunks/lines to squash (same UI as split) |
| **JJ: Quick Squash** | Instantly squash current change into parent (no interaction, ideal for keybinding) |
| **JJ: Absorb** | Automatically move changes into ancestor commits where those lines were last modified |
| **JJ: Absorb Interactive...** | Choose specific hunks/lines to absorb (same UI as split); requires jj 0.44 or later |

### Navigation and History

| Command | Description |
|---------|-------------|
| **JJ: Edit Change...** | Switch to editing a different change |
| **JJ: Log (Custom Revset)** | Query changes using any revset expression (e.g. `trunk()..@`, `author(me)`) |
| **JJ: Log View** | Open a read-only log graph view with keybindings on the change under the cursor (see below) |
| **JJ: File History...** | List the changes that touched the current file; selecting one shows its diff for that file |
| **JJ: Annotate File** | Show the current file with per-line change annotations (`jj file annotate`) |
| **JJ: Evolog (Change Evolution)...** | Browse past versions of the current change; selecting one shows its diff |
| **JJ: File Search...** | Search file contents with a regex (`jj file search`); selecting a match jumps to it |
| **JJ: Rebase...** | Rebase with full control over source mode (-r/-s/-b) and destination mode (-d/-A/-B) |

### Conflicts

| Command | Description |
|---------|-------------|
| **JJ: Conflicts...** | List all mutable changes containing conflicts; selecting one edits it and shows its conflicted files |
| **JJ: Conflicted Files** | List conflicted files in the working copy; selecting one opens it at the first conflict marker |

The status bar also flags conflicts: the current change gets a `(conflict)` marker, and a count of other conflicted mutable changes is appended when present.

### Log View

"JJ: Log View" opens a persistent, read-only tab showing the `jj log` graph. The view uses jj's configured default revset unless `log_view_revset` is set. The following keys act on the change under the cursor:

| Key | Action |
|-----|--------|
| `enter` | Edit (check out) the change |
| `o` | Show its diff in a scratch view |
| `n` | Create a new change on top of it |
| `d` | Set its description |
| `a` | Abandon it (with confirmation) |
| `s` | Squash it into its parent (with confirmation) |
| `alt+up` / `alt+down` | Swap it with its child / parent (linear reordering) |
| `b` | Set a bookmark on it |
| `r` | Refresh the view |
| `?` | Show this key reference |
| `escape` | Close the view |

The view refreshes automatically after each operation. Entries are syntax highlighted: change ids, bookmarks, conflict and empty markers, and author lines each pick up theme colours.

Further chrome:

- Hovering an entry shows a detail card with the full description, author, timestamps, a diff stat, and clickable edit/diff/squash/abandon actions.
- Right-aligned annotations show each entry's relative age, bookmarks, and working-copy or conflict markers.
- The entry under the cursor is outlined, making the target of key presses unambiguous.
- The gutter marks the working copy (circle) and conflicted entries (dot).

### Workspaces

Workspaces are additional working copies attached to the same repository, each with its own working-copy commit.

| Command | Description |
|---------|-------------|
| **JJ: Workspace List** | List workspaces; selecting one shows its working-copy diff |
| **JJ: Workspace Add...** | Create a workspace (shares the current change's parents) and open it in a new window |
| **JJ: Workspace Forget...** | Stop tracking one or more workspaces (multi-select) |
| **JJ: Workspace Rename** | Rename the current workspace |
| **JJ: Workspace Update Stale** | Update this working copy after another workspace has rewritten it |

jj does not record workspace directory paths, so the list command cannot open existing workspaces' folders; only newly created workspaces are opened automatically.

### Bookmark Management

| Command | Description |
|---------|-------------|
| **JJ: Bookmark Set** | Create or update a bookmark on a revision |
| **JJ: Bookmark Move** | Move an existing bookmark to a different revision |
| **JJ: Bookmark Delete** | Delete one or more bookmarks (multi-select supported) |
| **JJ: Bookmark Rename** | Rename a bookmark |
| **JJ: Bookmark List** | List all bookmarks; selecting one navigates to that revision |

### Tag Management

Requires jj 0.44 or later (tags are tracked like bookmarks).

| Command | Description |
|---------|-------------|
| **JJ: Tag List** | List all tags; selecting one navigates to that revision |
| **JJ: Tag Set** | Create or update a tag on a revision |
| **JJ: Tag Delete** | Delete one or more tags (multi-select supported) |

### Git Integration

| Command | Description |
|---------|-------------|
| **JJ: Git Push (Create Bookmark)** | Push a change by creating a bookmark (`jj git push -c`), with optional GitHub PR URL detection |
| **JJ: Git Push (Tracked Bookmarks)** | Plain `jj git push`: push all tracked bookmarks pointing to ancestors of @ |
| **JJ: Git Fetch** | Fetch from the default remote |
| **JJ: Pull and Retrunk** | Fetch from default remote and rebase current stack onto trunk (requires revset aliases, see below) |

#### Pull and Retrunk

The "Pull and Retrunk" command runs `jj git fetch` followed by `jj rebase -d trunk() -s roots(trunk()..stack(@))`. This requires the following revset aliases in your jj config:

```toml
[revset-aliases]
'trunk()' = 'latest((present(main) | present(master)) & remote_bookmarks())'
'stack()' = 'stack(@)'
```

## Settings

Configure Jujutsu via `Preferences > Package Settings > Jujutsu > Settings` or by editing `Jujutsu.sublime-settings`:

```json
{
    // Path to jj executable. Set to null to auto-detect from PATH.
    "jj_path": null,

    // Enable status bar with current change ID and description.
    "status_bar_enabled": true,

    // Debounce delay in seconds for updates after save.
    "debounce_delay": 0.5,

    // Enable debug logging.
    "debug": false
}
```

## Key Bindings

Jujutsu does not define default key bindings to avoid conflicts with other packages. To add your own, go to `Preferences > Key Bindings` and add entries from the suggestions below.

### Suggested Shortcuts

These are convenient bindings for the most common operations. Copy whichever you find useful into your user key bindings:

```json
[
    { "keys": ["ctrl+shift+n"], "command": "jj_new" },
    { "keys": ["ctrl+shift+c"], "command": "jj_commit" },
    { "keys": ["ctrl+shift+d"], "command": "jj_describe" },
    { "keys": ["ctrl+shift+z"], "command": "jj_undo" },
    { "keys": ["ctrl+shift+s"], "command": "jj_quick_squash" },
    { "keys": ["ctrl+shift+l"], "command": "jj_squash" },
    { "keys": ["ctrl+shift+r"], "command": "jj_rebase" }
]
```

### All Available Command Names

- `jj_new`
- `jj_describe`
- `jj_commit`
- `jj_split`
- `jj_squash`
- `jj_squash_interactive`
- `jj_quick_squash`
- `jj_absorb`
- `jj_absorb_interactive`
- `jj_abandon`
- `jj_undo`
- `jj_op_log`
- `jj_conflicts`
- `jj_conflicted_files`
- `jj_restore_file`
- `jj_discard_interactive`
- `jj_log_view`
- `jj_file_history`
- `jj_annotate_file`
- `jj_evolog`
- `jj_git_push`
- `jj_git_fetch`
- `jj_duplicate`
- `jj_revert`
- `jj_tag_list`
- `jj_tag_set`
- `jj_tag_delete`
- `jj_fix`
- `jj_file_search`
- `jj_parallelize`
- `jj_run`
- `jj_workspace_list`
- `jj_workspace_add`
- `jj_workspace_forget`
- `jj_workspace_rename`
- `jj_workspace_update_stale`
- `jj_pull_retrunk`
- `jj_edit`
- `jj_log`
- `jj_rebase`
- `jj_refresh`
- `jj_bookmark_set`
- `jj_bookmark_move`
- `jj_bookmark_delete`
- `jj_bookmark_rename`
- `jj_bookmark_list`
- `jj_git_push_change`

## Jujutsu Documentation

- [Command Reference](https://docs.jj-vcs.dev/latest/cli-reference/)
- [Revset Language](https://docs.jj-vcs.dev/latest/revsets/)
- [Fileset Language](https://docs.jj-vcs.dev/latest/filesets/)

## Licence

Blue Oak Model Licence 1.0.0 - See [LICENCE](LICENCE) for details.
