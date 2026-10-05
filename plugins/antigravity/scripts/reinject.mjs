#!/usr/bin/env node
/**
 * reinject.mjs — Gateway Protocol reinject for Antigravity PreInvocation hook.
 *
 * Replaces the previous POSIX/sh implementation, whose absolute path
 * (`sh /plugins/antigravity/scripts/reinject.sh`) does not exist on Windows and
 * could not be resolved relative to the workspace.
 *
 * stdin:  JSON hook input (expects a "transcriptPath" field per /docs/hooks).
 * argv:   optional $1 transcript path override (takes precedence over stdin).
 * stdout: JSON hook output — {"injectSteps": []} when the MARKER card is
 *         already present in the transcript, otherwise:
 *         {"injectSteps": [{"ephemeralMessage": ...}]}.
 *
 * Hardening: no eval, no network, no child processes, no file writes — reads the
 * transcript only when a path is supplied, and emits nothing else on stdout. No
 * secrets are read or emitted. Any failure degrades to a no-op injection list so
 * the hook can never block a turn.
 */

import { readFileSync } from "node:fs";

const MARKER = "MCP-GWAY v4.4.0";
const RULES_HEADING = "MCP Rules — Gateway Protocol";
const MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024;

/** Read stdin as UTF-8, tolerating a closed or absent stdin (non-TTY, no pipe). */
function readStdin() {
	if (process.stdin.isTTY) return "";
	try {
		return readFileSync(0, "utf8");
	} catch {
		return "";
	}
}

/** Extract transcriptPath from raw hook JSON without a full parse. */
function extractTranscriptPath(raw) {
	if (typeof raw !== "string" || raw === "") return "";
	const match = raw.match(/"transcriptPath"\s*:\s*"([^"]*)"/);
	return match ? match[1] : "";
}

/** True when the card is already present in the transcript. */
function hasCard(text) {
	return text.includes(MARKER) || text.includes(RULES_HEADING);
}

/**
 * Read the transcript when a path is available.
 * Returns "" on any failure — a missing transcript means "inject", never "crash".
 */
function readTranscript(path) {
	if (!path) return "";
	try {
		const text = readFileSync(path, "utf8");
		return text.length > MAX_TRANSCRIPT_BYTES ? "" : text;
	} catch {
		return "";
	}
}

function buildCard() {
	return `<!-- ${MARKER} -->
## ${RULES_HEADING}

All MCP tools run via \`gateway_*\` helpers. **Mandatory order:**

1. \`gateway_listToolFiles\` — discover servers
2. \`gateway_readToolFile\` — read \`servers/<Name>.pyi\` stub for exact tool names + params
3. \`gateway_getToolDocs\` (optional) — full docs when stub is truncated
4. \`gateway_executeToolCode\` — run Starlark: \`Server.tool(param=value)\`

> **Parallel:** Step 1 first. Steps 2-4 can run concurrently across servers/tools.

### Calling Convention (Starlark)

\`\`\`python
result = Server.tool(param=value, params....)
value = result["key"]  # brackets, not dot
\`\`\`

- Sync only, keyword args, no \`try/except\`, no classes, no imports.
- Each \`executeToolCode\` scope is fresh — re-fetch or persist via MCP.

### Anti-Patterns

| Anti-Pattern                            | Fix                                       |
| :-------------------------------------- | :---------------------------------------- |
| Guessing tool names                     | Stub from \`readToolFile\` is authoritative |
| Skipping \`listToolFiles\`                | Always discover first when unsure         |
| \`executeToolCode\` before \`readToolFile\` | Confirm signature first                   |
| Assuming cross-call state               | Every call is isolated                    |

## MCP RULES

- For mcps not listed in your context, use gateway mcp instead, to list and execute mcp tools, this is no negotiable.
`;
}

function main() {
	const argvPath = typeof process.argv[2] === "string" ? process.argv[2].trim() : "";
	const transcriptPath = argvPath !== "" ? argvPath : extractTranscriptPath(readStdin());

	const alreadyInjected = transcriptPath !== "" && hasCard(readTranscript(transcriptPath));
	const injectSteps = alreadyInjected
		? []
		: [{ ephemeralMessage: buildCard() }];

	process.stdout.write(`${JSON.stringify({ injectSteps })}\n`);
}

try {
	main();
} catch {
	// A hook must never break the turn it precedes.
	process.stdout.write(`${JSON.stringify({ injectSteps: [] })}\n`);
}