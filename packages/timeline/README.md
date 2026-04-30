# Timeline Package

Maps raw agent runtime events to semantic product events.

Examples:

- file read in `examples/` -> analyze examples
- write `style_notes.md` -> extract style notes
- run `checkpoint.py` -> create draft version
- run `export_docx.py` -> export DOCX

## Phase 0 Mapper

`docagent_timeline.map_raw_event(...)` converts simple runtime signals into `SemanticTimelineEvent` objects.

The mapper is intentionally path- and command-based for Phase 0. Runtime-specific payload handling belongs in the future runtime adapter.

