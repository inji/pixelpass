# pixelpass: Crewline context

[Crewline](https://github.com/mosip/mosip-labs/tree/develop/crewline) is a gated, evidence-first AI engineering workflow. Its
agents read this folder before they change this repository. The repository's own READMEs (`README.md`, `js/Readme.md`,
`kotlin/Readme.md`) win wherever they are more specific.

| Folder | Role | Files |
|---|---|---|
| `development/` | developer | `local-context.md` (layout, build, unit tests, coverage, CI, consumers, default change scope), `discovery.json` (machine facts) |
| `qa/` | SDET | `module-context.md` (where the tests are, what a change must re-run), `known-issues.md` |

pixelpass is a library (JavaScript and Kotlin Multiplatform), not a service: there is no `api-test/`, no UI test project, no
DB and no deployment. Other roles (`product/`, `ui-ux/`, `devops/`, `security/`) are added when the module has something to say.

## Using it

Cloning this repository and opening it in Claude Code offers the Crewline plugin (`.claude/settings.json`). In Cursor,
`.cursor/` does the same job: `.cursor/rules/crewline.mdc` is the rule, and `.cursor/hooks.json` runs `.cursor/crewline.py`, which
keeps a cached copy of Crewline under `~/.crewline/`. Then ask for the work as usual. Agents follow the workflow, and your
approval is needed before every commit, push, PR or bug.

Prerequisites for the Cursor hooks: a `python` command (Python 3.11+), PyYAML and git. Without `python` the hooks cannot start, and
without PyYAML Cursor asks for confirmation on every read, write and shell command.

What the hooks do: they download Crewline from `mosip/mosip-labs` branch `develop`, refresh it at most once a day, and run it on
your machine. Once active, an agent cannot commit or push without a Crewline task. This applies to agent actions only; your own
terminal commands and git are not affected.

| Want | Do |
|---|---|
| Off for you in this clone (Claude Code) | `.claude/settings.local.json`: `{"enabledPlugins": {"crewline@mosip-labs": false}}` |
| Off for you in this clone (Cursor) | `.cursor/crewline.local.json`: `{"enabled": false}`. The always-on Cursor rule still tells the agent to run Crewline |
| Off for one session | start the tool with `CREWLINE=off` |
| Work files | `.crewline-work/` in your clone (task records, worktrees) |

Add `.crewline-work/` and your local settings files above to `.git/info/exclude`; never commit them.

## Freshness

Verified at `c9e2258d9b` (`develop`, 2026-11-02) with `crewline discover` and one run of each test command listed in
`development/local-context.md`. `crewline discover` 0.6.0 does not read Gradle builds, so `development/discovery.json` lists only
the Node projects; the Kotlin rows were added by hand from the build files and the test run. Rows marked *Inferred* are still to
be confirmed by a run. Refresh with the Crewline `module-onboarding` task when the build or test layout changes.
