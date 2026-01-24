# Sublime Text 4 Plugin Development Guide

This document captures lessons learned while developing SublimeJJ. It serves as a reference for future plugin development.

## Python Version Compatibility

**Critical**: Although Sublime Text 4 officially supports Python 3.8, some installations (particularly on macOS) may load plugins with Python 3.3. To be safe, always use Python 3.3 compatible syntax:

```python
# DO NOT USE - Python 3.6+ only
f"Hello {name}"
my_list: list[str] = []
@dataclass
class Foo:
    pass

# USE INSTEAD - Python 3.3 compatible
"Hello {0}".format(name)
my_list = []  # No type hints
class Foo(object):
    def __init__(self):
        pass
```

Key restrictions:
- No f-strings (use `.format()`)
- No type hints
- No dataclasses
- Use `object` as explicit base class
- No `subprocess.run()` (use `subprocess.Popen()`)
- No `concurrent.futures` (implement simple thread pool)

## Plugin Structure

```
PluginName/
├── PluginName.py              # Entry point - imports all commands
├── PluginName.sublime-settings # Default settings
├── Default.sublime-commands    # Command palette entries
├── Default.sublime-keymap      # Keyboard shortcuts
│
├── commands/
│   ├── __init__.py
│   ├── base.py                # Base command classes
│   └── my_commands.py         # Command implementations
│
├── core/
│   ├── __init__.py
│   └── logic.py               # Core business logic
│
├── views/
│   ├── __init__.py
│   └── panels.py              # UI components
│
└── listeners/
    ├── __init__.py
    └── events.py              # Event listeners
```

## Command Registration

### Command Class Naming Convention

Sublime Text converts CamelCase class names to snake_case command names:

```python
class MyCommandName(sublime_plugin.WindowCommand):
    pass
# Becomes: my_command_name
```

**Critical pitfall with double capitals**:

```python
class JJShowGraph(sublime_plugin.WindowCommand):
    pass
# Becomes: j_j_show_graph  (NOT jj_show_graph!)

# Solution: Use single capital
class JjShowGraph(sublime_plugin.WindowCommand):
    pass
# Becomes: jj_show_graph
```

### Explicit Imports Required

Commands must be explicitly imported in the main plugin file for Sublime to register them:

```python
# PluginName.py

# This DOES NOT work - commands won't be registered:
from .commands import my_commands  # noqa: F401

# This DOES work - commands are registered:
from .commands.my_commands import (  # noqa: F401
    MyFirstCommand,
    MySecondCommand,
)
```

## Command Types

### WindowCommand

For commands that operate on the window (most common):

```python
class JjNewCommand(sublime_plugin.WindowCommand):
    def run(self):
        # self.window is available
        view = self.window.active_view()

    def is_enabled(self):
        # Return False to grey out in menu/palette
        return True
```

### TextCommand

For commands that operate on text/view content:

```python
class JjToggleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        # self.view is available
        # edit is required for text modifications
        self.view.insert(edit, 0, "Hello")
```

### ApplicationCommand

For commands that don't need a window:

```python
class MyAppCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        pass
```

## Event Listeners

```python
class MyEventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        """Called when a view gains focus."""
        pass

    def on_post_save(self, view):
        """Called after a view is saved."""
        pass

    def on_load(self, view):
        """Called when a file is finished loading."""
        pass

    def on_close(self, view):
        """Called when a view is closed."""
        pass
```

## Async Execution

**Never block the main thread**. Use threading for long operations:

```python
import threading
import sublime

def run_async(callback):
    def execute():
        # Do slow work here
        result = expensive_operation()

        # Post result back to main thread
        sublime.set_timeout(lambda: callback(result), 0)

    thread = threading.Thread(target=execute)
    thread.daemon = True
    thread.start()
```

## Settings

### Default Settings File (PluginName.sublime-settings)

```json
{
    "my_option": true,
    "my_path": null,
    "my_number": 50
}
```

### Reading Settings

```python
settings = sublime.load_settings("PluginName.sublime-settings")
value = settings.get("my_option", default_value)
```

## Command Palette (Default.sublime-commands)

```json
[
    {
        "caption": "My Plugin: Do Something",
        "command": "my_do_something"
    },
    {
        "caption": "My Plugin: Other Thing",
        "command": "my_other_thing"
    }
]
```

## Keyboard Shortcuts (Default.sublime-keymap)

```json
[
    {
        "keys": ["ctrl+shift+g"],
        "command": "my_command",
        "context": [
            { "key": "selector", "operator": "equal", "operand": "source.python" }
        ]
    }
]
```

## UI Components

### Status Bar

```python
# Set status
view.set_status("my_key", "Status message here")

# Clear status
view.erase_status("my_key")
```

### Output Panel

```python
panel = window.create_output_panel("my_panel")
panel.run_command("append", {"characters": "Hello\n"})
window.run_command("show_panel", {"panel": "output.my_panel"})
```

### New Tab/View

```python
view = window.new_file()
view.set_name("My Tab Title")
view.set_scratch(True)  # No "unsaved" warning
view.run_command("append", {"characters": content})
view.assign_syntax("Packages/Diff/Diff.sublime-syntax")
view.set_read_only(True)
```

### Phantoms (Inline HTML)

```python
phantom_set = sublime.PhantomSet(view, "my_phantoms")
phantom = sublime.Phantom(
    sublime.Region(point, point),
    "<body><div>HTML content</div></body>",
    sublime.LAYOUT_BLOCK,  # or LAYOUT_INLINE
)
phantom_set.update([phantom])

# Store reference to prevent garbage collection
_phantom_sets[view.id()] = phantom_set
```

### Input Panel

```python
def on_done(text):
    print("User entered:", text)

def on_change(text):
    pass  # Optional: called on each keystroke

def on_cancel():
    pass  # Optional: called if user presses Escape

window.show_input_panel(
    "Prompt:",           # Caption
    "initial value",     # Initial text
    on_done,
    on_change,
    on_cancel
)
```

### Quick Panel

```python
items = [
    ["First Item", "Description of first"],
    ["Second Item", "Description of second"],
]

def on_select(index):
    if index < 0:
        return  # User cancelled
    print("Selected:", items[index])

window.show_quick_panel(items, on_select)
```

## minihtml (Sublime's HTML Subset)

Sublime uses a limited HTML/CSS engine called minihtml. Key limitations:

### Supported CSS

```css
/* SUPPORTED */
body { font-size: 12px; padding: 8px; }
.class { background-color: #2d4a2d; color: #90c090; }
div { margin: 4px 0; padding: 4px 8px; }
span { font-weight: bold; font-style: italic; }
a { text-decoration: none; }

/* NOT SUPPORTED */
var(--custom-property)
color(var(--something) alpha(0.5))
display: flex
position: absolute
/* Most modern CSS features */
```

### Clickable Links (subl: protocol)

```python
# For commands with no arguments:
'<a href="subl:my_command">Click me</a>'

# For commands with arguments - use single quotes for href:
'<a href=\'subl:my_command {{"arg": "{0}"}}\'>Click</a>'.format(value)

# DO NOT use escaped double quotes - causes parse errors:
# '<a href="subl:cmd {\"arg\": \"val\"}">X</a>'  # BROKEN
```

### HTML Escaping

```python
def escape_html(text):
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
```

## Regions and Gutter Icons

```python
# Add regions with gutter icons
view.add_regions(
    "my_regions",                    # Key (for later removal)
    [region1, region2],              # List of sublime.Region
    "markup.inserted.diff",          # Scope for colouring
    "dot",                           # Icon: "dot", "circle", "bookmark", or custom
    sublime.HIDDEN,                  # Flags
)

# Remove regions
view.erase_regions("my_regions")
```

Built-in icons: `dot`, `circle`, `bookmark`, `cross`

Custom icons: Path relative to Packages, e.g., `Packages/MyPlugin/icons/my_icon.png`

## Debugging

### Console Output

View > Show Console (or Ctrl+`)

```python
print("Debug message")  # Appears in console
```

### Error Messages

```python
sublime.error_message("Something went wrong")
sublime.status_message("Brief status update")  # Shows in status bar
```

## Plugin Lifecycle

```python
def plugin_loaded():
    """Called once when plugin is fully loaded."""
    pass

def plugin_unloaded():
    """Called when plugin is about to be unloaded."""
    # Clean up resources, stop threads, etc.
    pass
```

## Common Patterns

### Get Repository/Project Root

```python
def get_project_root(view):
    file_path = view.file_name()
    if file_path:
        # Walk up looking for marker file/directory
        current = os.path.dirname(file_path)
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, ".git")):
                return current
            current = os.path.dirname(current)

    # Fall back to window folders
    window = view.window()
    if window:
        folders = window.folders()
        if folders:
            return folders[0]
    return None
```

### Debouncing

```python
_pending_updates = {}

def debounced_update(view, delay=0.5):
    view_id = view.id()

    # Cancel any pending update
    if view_id in _pending_updates:
        _pending_updates[view_id].cancel()

    def do_update():
        if view_id in _pending_updates:
            del _pending_updates[view_id]
        actual_update(view)

    timer = threading.Timer(delay, lambda: sublime.set_timeout(do_update, 0))
    _pending_updates[view_id] = timer
    timer.start()
```

### Subprocess Execution (Python 3.3 compatible)

```python
import subprocess
import os

def run_command(cmd, cwd=None):
    env = os.environ.copy()
    env["NO_COLOR"] = "1"  # Disable colour codes

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        stdout, stderr = process.communicate(timeout=30)
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    except subprocess.TimeoutExpired:
        process.kill()
        return {"success": False, "stdout": "", "stderr": "Timeout"}
    except OSError as e:
        return {"success": False, "stdout": "", "stderr": str(e)}
```

## Testing

There's no built-in test framework. Options:

1. **Manual testing**: Reload plugin with Ctrl+Shift+P > "Package Development: Reload Plugin"
2. **Console debugging**: Use print statements, check View > Show Console
3. **UnitTesting package**: Third-party package for automated tests

## Distribution

### Package Control

1. Create a repository with proper structure
2. Add to Package Control's channel
3. Users install via Ctrl+Shift+P > "Package Control: Install Package"

### Manual Installation

Copy plugin folder to:
- **macOS**: `~/Library/Application Support/Sublime Text/Packages/`
- **Windows**: `%APPDATA%\Sublime Text\Packages\`
- **Linux**: `~/.config/sublime-text/Packages/`

Note: On some macOS installations, the path may be `Sublime Text 3` even for ST4.
