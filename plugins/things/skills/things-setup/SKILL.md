---
name: things-setup
description: Set up the Things for macOS plugin, check prerequisites, verify its connection, and troubleshoot Python or macOS Automation access. Use for first-time setup or connection problems, not ordinary task reviews or edits.
---

# Set up Things for macOS

Follow the user's explicit instructions over these defaults. Setup checks must not create, read, or change tasks. The connection test returns only the Things version and list count.

1. Resolve `../things/scripts/check_setup.sh` relative to this skill folder to an absolute path. Run `sh /absolute/path/check_setup.sh --no-connect` to check macOS and Python without opening Things or requesting Automation permission.
2. If the execution host is not macOS, explain that the plugin needs a local Mac (or a connected Mac host) with Things 3 installed. Do not claim a cloud-only installation can reach the user's Mac.
3. If Python is missing or too old, first check whether the host offers a documented bundled Python runtime. If it does, use its absolute executable path with `THINGS_PYTHON='/absolute/path/to/python3' sh /absolute/path/check_setup.sh --no-connect`. Keep using that interpreter for Things commands in this chat. If no suitable runtime is available, direct the user to the official [Python macOS installer](https://www.python.org/downloads/macos/), or use an existing package manager when the user authorizes installing Python. Do not install software merely to perform a prerequisite check.
4. Once prerequisites pass, briefly explain that macOS may ask the host app to control Things. Run the same setup command without `--no-connect`. The script invokes only `things.py status`. Preserve `THINGS_PYTHON` if an explicit interpreter was selected. If Things is not installed, direct the user to [Things for Mac](https://culturedcode.com/things/mac/).
5. For denied Automation access (`-1743`), explain how to enable Things under the application running the command in **System Settings → Privacy & Security → Automation**. Do not reset privacy permissions, switch identities, or request Full Disk Access. For a shell sandbox/XPC connection failure, use the host's normal approved escalation for the same command. A sandbox can also report “Application can't be found” even when Things is installed: check the Things app bundle before advising installation, and use the same approved escalation if the app is present. See the sibling Things skill's recovery guidance.
6. Report a working connection only when the status JSON contains both `ok: true` and `connected: true`. Include the detected Things version. If the check fails, report the exact failed prerequisite or connection step and its next action. Never present `--no-connect` success as a verified connection.

If you need information or a choice from the user, ask in an ordinary chat reply, end the turn, and wait for their explicit response. Do not retry while waiting.

After a successful connection, offer a starter prompt such as “Review my Things Today list and help me plan my day.” Do not read the user's tasks until they request a task workflow. The sibling `things` skill supplies all task-management commands and write protections.
