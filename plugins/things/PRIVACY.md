# Privacy

The Things helper runs on your Mac and communicates with Things 3 through its public scripting interface. The helper makes no network requests, runs no hosted service, and includes no analytics or telemetry. It does not ask for Things Cloud credentials or open the Things database directly.

The setup connection check returns the Things version and the number of lists. It does not return task titles or notes. Task-management commands return requested data as JSON. List reads omit notes unless requested; item reads and write previews can include notes.

When an AI assistant runs the helper, its outputs can become part of that assistant's context, conversation history, and logs. The assistant provider's and your workspace's data policies apply to those outputs. Local execution of the helper does not mean that data returned to an AI assistant stays only on your Mac.

The plugin author does not receive your Things data through the helper. If you open a GitHub issue or share diagnostic output, that information is shared with GitHub and the people who can view it. Remove task titles, notes, item IDs, and personal paths before posting.

Plugin downloads, directory use, and repository visits are handled by their hosting services under those services' own policies. This project is independent of Cultured Code and OpenAI.
