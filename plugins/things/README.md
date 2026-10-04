# Things for macOS

An independent community plugin for reading and managing Things 3 through its public macOS scripting interface. Requires a Mac with Things 3, Python 3.10+, and macOS Automation permission.

After installation, start with:

> Set up Things on this Mac and verify the connection.

The `things-setup` skill checks prerequisites and tests access without returning task contents. After it confirms the connection, try:

> Review my Things Today list and help me plan my day.

The `things` skill supports task and project reads, search, creation, edits, scheduling, and status changes. Writes preview by default and require `--apply`; applied changes are read back for verification. Headings, checklists, reminders, repeating rules, and tag/area creation are not implemented.

This plugin runs on the execution host. A cloud-only host cannot reach Things on your Mac. The helper has no hosted service or telemetry, but requested task data returned to an AI assistant may enter its context and conversation history.

- [Source, installation, and CLI documentation](https://github.com/anri-asaturov/things-skill)
- [Support](https://github.com/anri-asaturov/things-skill/issues)
- [Privacy](https://github.com/anri-asaturov/things-skill/blob/main/PRIVACY.md)

MIT licensed. Not affiliated with or endorsed by Cultured Code or OpenAI.
