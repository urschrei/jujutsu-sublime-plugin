# SublimeJJ

[Jujutsu](https://www.jj-vcs.dev/latest/) (`jj`) integration for Sublime Text.

SublimeJJ provides status bar information and jj commands accessible via the command palette. It is designed for **colocated repositories** (where both `.jj` and `.git` exist), letting Sublime's built-in git integration handle diff gutters and other git-specific features while SublimeJJ adds jj workflow commands.

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
3. Search for "SublimeJJ" and install

### Manual Installation

1. Clone or download this repository
2. Copy the `SublimeJJ` folder to your Sublime Text Packages directory:
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
| **JJ: Abandon Change** | Abandon the current change (with confirmation) |
| **JJ: Undo Last Operation** | Undo the last jj operation |
| **JJ: Refresh Status** | Refresh status bar |

### Squash Operations

| Command | Description |
|---------|-------------|
| **JJ: Squash...** | Interactive squash with multi-select sources and destination picker |
| **JJ: Quick Squash** | Instantly squash current change into parent (no interaction, ideal for keybinding) |
| **JJ: Absorb** | Automatically move changes into ancestor commits where those lines were last modified |

### Navigation and History

| Command | Description |
|---------|-------------|
| **JJ: Edit Change...** | Switch to editing a different change |
| **JJ: Log (Custom Revset)** | Query changes using any revset expression (e.g. `trunk()..@`, `author(me)`) |
| **JJ: Rebase...** | Rebase with full control over source mode (-r/-s/-b) and destination mode (-d/-A/-B) |

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

Configure SublimeJJ via `Preferences > Package Settings > SublimeJJ > Settings` or by editing `SublimeJJ.sublime-settings`:

```json
{
    // Path to jj executable. Set to null to auto-detect from PATH.
    "jj_path": null,

    // Enable status bar with current change ID and description.
    "status_bar_enabled": true,

    // Debounce delay in seconds for updates after save.
    "debounce_delay": 0.5,

    // In colocated repositories (both .jj and .git), prefer jj.
    // Set to false to let Sublime's built-in git take precedence.
    "prefer_jj_in_colocated": true,

    // Enable debug logging.
    "debug": false
}
```

## Key Bindings

SublimeJJ does not define default key bindings. To add your own, go to `Preferences > Key Bindings` and add entries like:

```json
[
    { "keys": ["ctrl+shift+s"], "command": "jj_quick_squash" },
    { "keys": ["ctrl+shift+n"], "command": "jj_new" },
    { "keys": ["ctrl+shift+d"], "command": "jj_describe" }
]
```

### Available Command Names

- `jj_new`
- `jj_describe`
- `jj_commit`
- `jj_squash`
- `jj_quick_squash`
- `jj_absorb`
- `jj_abandon`
- `jj_undo`
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

## TODO

- [ ] Split change command (interactive hunk selection across multiple files)

## Licence

Blue Oak Model Licence 1.0.0 - See [LICENCE](LICENCE) for details.
