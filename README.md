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
| **JJ: Operation Log (Restore)...** | Browse the operation log and restore the repository to an earlier operation (safe multi-step undo) |
| **JJ: Refresh Status** | Refresh status bar |

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
| `b` | Set a bookmark on it |
| `r` | Refresh the view |
| `?` | Show this key reference |
| `escape` | Close the view |

The view refreshes automatically after each operation. Entries are syntax highlighted: change ids, bookmarks, conflict and empty markers, and author lines each pick up theme colours.

### Bookmark Management

| Command | Description |
|---------|-------------|
| **JJ: Bookmark Set** | Create or update a bookmark on a revision |
| **JJ: Bookmark Move** | Move an existing bookmark to a different revision |
| **JJ: Bookmark Delete** | Delete one or more bookmarks (multi-select supported) |
| **JJ: Bookmark Rename** | Rename a bookmark |
| **JJ: Bookmark List** | List all bookmarks; selecting one navigates to that revision |

### Git Integration

| Command | Description |
|---------|-------------|
| **JJ: Git Push (Create Bookmark)** | Push a change by creating a bookmark (`jj git push -c`), with optional GitHub PR URL detection |
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
