# Things for macOS

[![Tests](https://github.com/anri-asaturov/things-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/anri-asaturov/things-skill/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An agent skill for reading and managing **Things 3 on macOS**. Use it with Codex to review your inbox, plan your day, organize projects, and make task changes you request.

Available as an installable plugin or a standalone skill. The plugin adds guided setup and connection checks. [Download the plugin ZIP](https://github.com/anri-asaturov/things-skill/releases/latest) or install from the GitHub marketplace below. Public directory submission is pending; the GitHub marketplace is the current distribution source.

The included JSON command-line helper uses Things' public scripting interface through macOS JavaScript for Automation (JXA). It needs Python's standard library and the macOS automation tools; there is no package installation, background server, or Things Cloud login.

## What it can do

- Read lists, tasks, projects, areas, and tags, with pagination and optional notes.
- Search task and project titles, including within a project or area.
- Create tasks and projects; update titles, notes, existing tags, start dates, and deadlines.
- Move tasks between projects or areas; complete, cancel, and reopen items.
- Preview writes, check for concurrent edits, and read back changed fields to verify results.

## Requirements

- A Mac with Things 3 installed.
- Python 3.10 or later, either on your PATH or supplied by your agent's local runtime.
- A local agent that can run shell commands, such as Codex, or a terminal for direct CLI use.
- macOS Automation permission for the application running the helper to control Things.

The helper runs on the Mac where Things is installed. A remote Linux or cloud environment cannot access your Mac's Things app.

## Install the plugin

Paste this into Codex on your Mac:

```text
Install the Things for macOS plugin from https://github.com/anri-asaturov/things-skill using its repository marketplace. Preserve any existing Things skill, then run the setup workflow and verify the connection.
```

With a current Codex CLI, the equivalent commands are:

```sh
codex plugin marketplace add anri-asaturov/things-skill
codex plugin add things-macos@things-skill
```

If your CLI does not have `plugin add`, add the marketplace with the first command, then open the desktop app's Plugins directory, choose the **Things skill** source, and install **Things for macOS**. Restart the app if the new source does not appear. See the [official marketplace guide](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli) for supported clients.

Start a new chat and ask:

```text
Set up Things on this Mac and verify the connection.
```

Setup checks macOS and Python, then asks Things for its version and list count. It does not read tasks. macOS may ask whether the app running the command can control Things; allow that access to connect. If access was previously denied, enable Things under that app in **System Settings → Privacy & Security → Automation**. Setup is complete only when the connection check returns `ok: true` and `connected: true`.

If Python is missing, setup can use a compatible runtime supplied by your agent. Otherwise install Python 3.10+ from the [official macOS downloads](https://www.python.org/downloads/macos/) and rerun setup. No pip packages are needed.

If you already installed the standalone Things skill, choose one installation to keep enabled so the agent does not see duplicate `things` skills. The plugin adds a separate `things-setup` skill for onboarding.

### Standalone skill alternative

For a direct skill installation, you also need Git. Clone into your personal skills directory:

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/anri-asaturov/things-skill.git "$HOME/.agents/skills/things"
```

If you already have a `things` skill, compare it with this repository before replacing it. Avoid installing duplicate copies with the same skill name. For a project-specific installation, clone into `.agents/skills/things` in that project instead.

Codex discovers local skills automatically. If it does not appear, restart Codex. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills#where-to-save-skills) for discovery locations and installation details.

Check the connection from your agent, or run this in Terminal (Terminal has its own Automation permission):

```sh
sh "$HOME/.agents/skills/things/scripts/check_setup.sh"
```

### Use Things

After setup, try a prompt such as:

```text
Use $things to review my Today list and help me plan my day.
```

Other examples:

```text
Use $things to show my inbox and suggest which items belong in projects.
Use $things to add a task called "Book a dentist appointment" for tomorrow.
Use $things to find my "Renew passport" task and set its deadline to 2027-01-15.
```

The skill treats a request to review or plan as a read. It applies changes when the user's request authorizes them and asks for clarification when the target or requested change is unclear.

## Use the CLI directly

From the repository directory:

```sh
python3 scripts/things.py status
python3 scripts/things.py lists
python3 scripts/things.py today --limit 30
python3 scripts/things.py inbox --limit 30
python3 scripts/things.py projects
python3 scripts/things.py search --query 'travel'
python3 scripts/things.py get --id 'ID_FROM_READ'
```

`status` checks access without returning task contents. On first use, macOS may ask for Automation permission. For denied access (`-1743`), enable Things under the responsible app in **System Settings → Privacy & Security → Automation**.

To diagnose prerequisites without contacting Things, use `sh scripts/check_setup.sh --no-connect`. To select a specific Python executable, set `THINGS_PYTHON` when running setup; use that same executable instead of `python3` for other CLI commands.

`today` and `inbox` use English list names. Run `lists` to discover localized names, then use `list --list 'EXACT_NAME'`. The `anytime` and `someday` write shortcuts also require English list names.

### Filtered reads

Use JSON for filters beyond the convenience flags:

```sh
python3 scripts/things.py request <<'JSON'
{"op":"list","project_id":"ID_FROM_READ","status":"open","limit":50,"offset":0}
JSON
```

List results omit notes by default. Use `get` for an item's notes or add `include_notes: true` to a JSON read. Follow `next_offset` until it is `null` to read every page. Search matches titles and includes closed items unless you specify `status: "open"`.

### Preview and apply writes

Writes use JSON and **preview by default**:

```sh
python3 scripts/things.py request <<'JSON'
{"op":"create","title":"Book a dentist appointment","when":"tomorrow"}
JSON
```

Add `--apply` to execute the request:

```sh
python3 scripts/things.py request --apply <<'JSON'
{"op":"create","title":"Book a dentist appointment","when":"tomorrow"}
JSON
```

A preview connects to Things to read the current item and validate destinations. To validate the request without connecting to Things, add `--validate-only`. This works on other platforms too:

```sh
python3 scripts/things.py request --validate-only <<'JSON'
{"op":"create","title":"Example task","when":"tomorrow"}
JSON
```

You can also supply JSON with `request --file /absolute/path/request.json`.

| Operation | Required fields | Optional fields |
| --- | --- | --- |
| `create` | `title` | `notes`, `tags`, `when`, `deadline`, `project_id` or `area_id` |
| `create-project` | `title` | `notes`, `tags`, `when`, `deadline`, `area_id` |
| `update` | `id`, at least one field to change | Same editable fields as `create`; `expected_modified` |
| `complete`, `cancel`, `reopen` | `id` | `expected_modified` |

Use IDs from read results. For edits, copy the exact `modified` value from a recent read into `expected_modified` to reject stale changes. Projects cannot be nested inside other projects.

- `when`: `YYYY-MM-DD`, `today`, `tomorrow`, `anytime`, or `someday`. Relative dates use the Mac's local calendar.
- `deadline`: `YYYY-MM-DD` or `null` to clear it. Changing the start date preserves the deadline unless it is also specified.
- `tags`: replaces the entire set; names must already exist in Things. To add a tag, include existing tags as well.
- Omitted fields stay unchanged. Each request changes one item.

An applied write succeeds only when `ok` and `verified` are both `true`. Inspect `mismatches` if verification fails. If `write_may_have_applied` is true or a request times out, read the item before retrying; creating it again can make a duplicate. Writes are not transactional: an error can occur after some changes have applied. The CLI exits with status `0` for successful results and `1` for reported failures; argument-usage errors use argparse's status `2`.

See [SKILL.md](SKILL.md) for the full agent workflow and read filters.

## Privacy and scope

The helper makes no network requests and does not persist task contents or credentials. It prints requested data as JSON; when an AI agent runs it, that output can enter the agent's context and conversation history. Notes are omitted from list reads by default to limit unnecessary disclosure.

See [PRIVACY.md](PRIVACY.md) for the complete data flow.

It uses the public scripting dictionary rather than accessing the Things database or Things Cloud. Cultured Code lists AppleScript as a supported integration method in its [AI integration guidance](https://culturedcode.com/things/support/articles/5510170/), and documents the [scripting commands](https://culturedcode.com/things/support/articles/4562654/).

Headings, checklists, reminders, repeating rules, deletion, and creation of tags or areas are not implemented in this helper. Task and project text is treated as data, never executable instructions. The helper does not need Full Disk Access.

## Development

The standalone skill stays at the repository root. The plugin bundles a generated copy so both installation methods use the same helper:

```text
SKILL.md               Agent instructions and skill metadata
agents/openai.yaml     Codex display metadata
scripts/things.py      JSON validation and CLI
scripts/things.js      JXA bridge to Things
scripts/check_setup.sh Prerequisite and connection checks
scripts/package_plugin.py  Sync, validate, and build the plugin
plugins/things/        Installable plugin and onboarding skill
.agents/plugins/       GitHub marketplace catalog
tests/                 Tests with synthetic data
```

Run the test suites with Python 3.10+ and Node.js 22+ (Node is only needed for development):

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_bridge.cjs
python3 scripts/package_plugin.py --check --output-dir dist
```

Tests check input validation, safe argument transport, preview behavior, stale-edit rejection, failure reporting, setup failures, and an extracted plugin archive using synthetic data. They do not access or modify a real Things library. GitHub Actions runs them on Linux with Python 3.10 and 3.14. Real automation behavior must be checked separately on macOS; see [CONTRIBUTING.md](CONTRIBUTING.md). For releases and public directory submission, see [PUBLISHING.md](PUBLISHING.md).

## License

[MIT](LICENSE). Copyright © 2026 Anri Asaturov.

This is an independent project, not affiliated with or endorsed by Cultured Code or OpenAI. Things is a product of Cultured Code.
