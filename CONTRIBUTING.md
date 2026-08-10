# Contributing to Jujutsu

## Before You Start

Please open a discussion before opening a pull request. This helps ensure your contribution aligns with the project's direction and avoids wasted effort.

## LLM-Assisted Contributions

LLM-assisted contributions are welcome, but contributors MUST review these themselves and ensure that they are of good quality. Do not submit unreviewed LLM output.

## Code Style

- Follow existing patterns in the codebase
- Use UK English spelling in comments and documentation
- No emoji in code comments or documentation
- Run `ruff format` and `ruff check --fix` on Python files before committing

## Development Gotcha: jj run and Duplicate Palette Entries

If you develop with this repository symlinked into Sublime's Packages
directory, avoid leaving a `jj run` working-copy cache in the repo.
`jj run` caches its private checkouts under `.jj/run/`, and each checkout
contains a full copy of the repository, including Default.sublime-commands
and the other resource files. Sublime scans the whole package tree for
resources, so the cached copies produce duplicate command palette entries.

The cache location is not configurable. After using `jj run` (or the
plugin's "JJ: Run Command on Revset" command) inside this repository,
remove the cache with:

    rm -rf .jj/run

This is safe: the cache is recreated on demand.
