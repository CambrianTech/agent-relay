"""airc_core — shared Python truth-layer for airc.

Both the bash entrypoint (airc) and the PowerShell entrypoint (airc.ps1)
invoke functions in this package instead of duplicating logic across
shell heredocs. Goals:

1. **One source of truth for business logic.** Config CRUD, gist envelope
   parse/build, pair handshake JSON, monitor formatting, etc. live here.
   The shell scripts become thin dispatch + arg parsers.

2. **No bash → python heredoc fragility.** Every fix today (silent
   SyntaxErrors when bash variable substitution drifted into the python
   source, function-export leaks across $() subshells, etc.) was a
   symptom of mixing the two. Python files are parsed once, tested
   once, and behave identically across shells.

3. **Cross-port consistency.** Bash on macOS/Linux/Git-Bash and
   PowerShell on Windows can call the SAME Python module. Drift
   between airc bash and airc.ps1 (which today is ~20 PRs behind)
   becomes mechanical to detect — same input → same output.

This package is sourced by setting PYTHONPATH to include the parent
'lib' directory. The airc bash script does this at startup.
"""

__version__ = "0.1.0"
