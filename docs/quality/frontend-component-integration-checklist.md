# Frontend Component Integration Checklist

Use this checklist when adding or changing third-party React components in `apps/web`.

## Runtime Adapters

- Verify every callback required by the library runtime is either wired or intentionally documented as unsupported.
- Add a contract test for callbacks that can be triggered outside the visible UI, such as cancel, reload, retry, or submit.
- Keep async refs scoped by workspace, task, session, or tab when data can outlive the current render.

## Data Fetching

- Do not use `keepPreviousData` across task, session, workspace, or document boundaries unless the UI labels the data as stale and blocks writes.
- Key query invalidation by the same entity boundary used in the query key.
- Add a regression test for task switches when stale data could be shown or saved.

## DOM And Accessibility

- Do not nest interactive elements inside buttons, tabs, links, menu items, or tree rows.
- Verify keyboard dismissal for overlays, command menus, dialogs, and popovers.
- Add role-based Testing Library assertions for tabs, dialogs, menus, and forms.

## Persisted Layout State

- Clamp and normalize values loaded from localStorage before passing them to component defaults.
- Add tests for corrupted, missing, and extreme persisted values.
- Keep persisted state migrations local to the state helper that reads the values.

## Editor And Long-Lived Inputs

- Memoize CodeMirror extensions and listeners that are passed as arrays or objects.
- Protect dirty local edits from late async fetches.
- Prefer explicit dirty refs over inferring dirty state from text equality.

## Documentation Check

- When a new third-party component is introduced, link the relevant local type or documentation evidence in the review or plan.
- Record intentional deviations in `docs/decisions/` when they affect product behavior.
