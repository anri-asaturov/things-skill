# Contributing

Issues and pull requests are welcome. Keep changes focused and include a synthetic request that reproduces a bug. Remove task titles, notes, IDs, local paths, and other personal information from any shared logs.

## Local checks

No third-party packages are needed. Use Python 3.10+ and Node.js 22+:

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_bridge.cjs
```

The Python suite checks validation and the command-line boundary. The JavaScript suite evaluates the JXA bridge against a fake Things application, checking behavior without Automation permission or a Things installation. Both run in CI.

On macOS, check JXA syntax without executing the script:

```sh
osacompile -l JavaScript -o /tmp/things-skill-check.scpt scripts/things.js
```

For changes to automation behavior, also test against a real Things installation using tasks and projects created specifically for testing. A useful sequence is: read an item, preview an edit, apply it, read it back, then attempt a stale edit. Include the macOS and Things versions and the operations checked in your pull request. Mock tests cannot establish how Things handles every scripting command.

## Design constraints

- Use documented macOS automation interfaces. Do not add direct database access or Things Cloud credentials.
- Keep task text in JSON arguments, separate from executable source. Do not use a shell to transport it.
- Keep writes opt-in through `--apply`, with read-only previews by default.
- Resolve destinations and existing tags before changing an item. Preserve fields omitted from a request.
- Verify writes by reading back changed fields. Report uncertainty when a write may have partially applied; never retry a create automatically.
- Preserve pagination, opt-in notes on list reads, and the distinction between start dates and deadlines.
- Keep runtime dependencies to Python's standard library and the built-in macOS automation tools.

Update the README and SKILL.md when you change behavior. Add focused regression coverage when fixing a bug in validation, write handling, or the bridge contract.
