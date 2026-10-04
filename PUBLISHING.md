# Publishing Things for macOS

The GitHub repository provides a marketplace at `.agents/plugins/marketplace.json`. The installable plugin is in `plugins/things/`. The public OpenAI plugin directory is a separate submission and review process; a GitHub release does not create a directory listing.

## Build a release

Update `plugins/things/plugin.json` with the next version and release notes, then run:

```sh
python3 scripts/package_plugin.py --sync --check
python3 -m unittest discover -s tests -v
node --test tests/test_bridge.cjs
python3 scripts/package_plugin.py --output-dir dist
```

The output is `dist/things-macos-VERSION.zip`, with `plugin.json` at the archive root. It contains the two skills, runtime scripts, icon, license, privacy notes, and plugin README. No MCP server, app mapping, or lifecycle hooks are needed for this plugin.

Commit the source and generated skill copies together, push, and wait for GitHub Actions. Create a tag matching the manifest version and attach the ZIP to its GitHub release. The marketplace currently follows the repository version selected at installation; users can pin a tag:

```sh
codex plugin marketplace add anri-asaturov/things-skill --ref v0.1.0
codex plugin add things-macos@things-skill
```

Before broad distribution, test installation on another Mac with Things installed, including Python-missing and Automation-denied recovery. Local and CI tests use synthetic data and cannot stand in for a second Mac's permissions and runtime setup.

## Submit to the public directory

Use the [official submission process](https://developers.openai.com/plugins/deploy/submission):

1. Sign in to [OpenAI Platform Plugins](https://platform.openai.com/plugins) under the intended organization and project. The publisher needs a verified developer identity and the required submission permission.
2. Upload the release ZIP. The portable manifest already includes listing text, publisher information, an icon, starter prompts, and the onboarding skill.
3. Review the metadata and skill findings. Correct source files, bump the version when appropriate, rebuild, and upload the corrected package.
4. Submit the draft for review after resolving required findings and reviewing any policy attestations.
5. Publish the approved version when ready. Update the repository's installation instructions with the actual directory link once it exists.

This is a skills-only package. It does not need MCP connection setup, MCP review test cases, or an MCP demo recording. Current platform rules do not support adding an MCP server later to an existing skills-only plugin; revisit the distribution plan if that architecture changes.

Keep the listing explicit about macOS, Things 3, Python, and Automation permission. Installation in a cloud-only environment does not provide access to a user's local Things library. Do not claim directory approval or compatibility that has not been verified.

References: [plugin packaging](https://developers.openai.com/plugins/build/plugins), [submission metadata](https://developers.openai.com/plugins/deploy/submission#automatically-provide-submission-and-review-information).
