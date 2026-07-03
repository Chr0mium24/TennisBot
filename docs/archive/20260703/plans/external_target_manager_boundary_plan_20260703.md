# External Target Manager Boundary Plan

Date: 2026-07-03

## Goal

Make `tennis_robot_ws` the owner of `target_manager` and keep this repository
focused on the headless vision runtime.

Target ownership:

```text
tennis_robot_ws
  target_msgs
  target_manager

TennisBot
  tennisbot_headless_vision
  scripts/headless.ts
```

## Scope

1. Remove the duplicate `src/interface/target_manager` package from TennisBot.
2. Remove the stale `src/interface/README.md` interface-layer document.
3. Update current docs so TennisBot build commands only build
   `tennisbot_headless_vision`.
4. Keep `scripts/headless.ts` able to launch external `target_manager` after
   the operator sources `~/tennis_robot_ws/install/setup.bash`.

## Verification

- Search current docs and source for local `src/interface/target_manager`
  assumptions.
- Run Python compile/tests that do not require the external control workspace.
- Run `scripts/headless.ts` dry-run to confirm it still launches external
  `target_manager`.
- Save results in Markdown.
