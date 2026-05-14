# Timeline Package

Maps legacy raw agent runtime events to semantic product projections.

ACP events are now the canonical interaction log for the center timeline.
Semantic timeline events are retained for DocAgent cards, workspace
invalidation, reporting, and compatibility endpoints.

Examples:

- file read in `examples/` -> analyze examples
- write `style_notes.md` -> extract style notes
- run `checkpoint.py` -> create draft version
- run `export_docx.py` -> export DOCX

## Legacy Mapper

`docagent_timeline.map_raw_event(...)` converts simple runtime signals into `SemanticTimelineEvent` objects.

The mapper is intentionally path- and command-based. New runtime integrations
should emit ACP updates first and attach projection metadata when a DocAgent card
or invalidation needs it. Runtime-specific payload handling belongs in the
runtime adapter or ACP shim, not in this package as a primary event protocol.

