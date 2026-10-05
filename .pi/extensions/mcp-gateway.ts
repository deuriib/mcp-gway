import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type { ExtensionAPI, BeforeAgentStartEvent } from "@earendil-works/pi-coding-agent";

/**
 * mcp-gateway — Pi extension.
 *
 * Parity with `plugins/opencode/mcp-gateway.ts` and
 * `plugins/antigravity/scripts/reinject.mjs`: keep the Gateway Protocol card in
 * the system prompt of every run, so it survives context compaction.
 *
 * Two deliberate differences from the OpenCode plugin:
 *
 * 1. MCP registration is declarative, not code. `.mcp.json` at the repo root is
 *    discovered by pi-mcp-adapter on its own. We deliberately do NOT call
 *    `registerMcpServer()` from pi-mcp-adapter: it forces `directTools: false`
 *    (proxy-only) and throws when the server name already exists — which would
 *    both downgrade and break a pre-existing `gateway` registration.
 *
 * 2. Re-injection happens on `before_agent_start` rather than on a `compaction`
 *    hook. Pi re-enters the agent loop after compaction (threshold, overflow
 *    recovery, retries), so re-applying the card at the start of every run makes
 *    compaction survival a property of the design instead of something we
 *    re-establish after the fact. The section is keyed and deduped, so repeated
 *    firing within a run cannot duplicate it.
 *
 * The card text is read from `rules/mcp-gway.md` — the single source of truth
 * shared with the Antigravity plugin — so the harnesses cannot drift apart.
 */

const MARKER = "MCP-GWAY v4.3.1";
const RULES_HEADING = "MCP Rules — Gateway Protocol";
const SECTION_KEY = "mcp-gateway";
const MAX_RULES_BYTES = 256 * 1024;

/**
 * Minimal fallback, used only when `rules/mcp-gway.md` cannot be read (broken
 * checkout, extension copied out of the repo). Keeps the mandatory call order
 * available rather than silently dropping the protocol.
 */
const FALLBACK_CARD = `<!-- ${MARKER} -->
## ${RULES_HEADING}

All MCP tools run via \`gateway_*\` helpers. **Mandatory order:**

1. \`gateway_listToolFiles\` — discover servers
2. \`gateway_readToolFile\` — read \`servers/<Name>.pyi\` stub for exact tool names + params
3. \`gateway_getToolDocs\` (optional) — full docs when stub is truncated
4. \`gateway_executeToolCode\` — run Starlark: \`Server.tool(param=value)\`
`;

function warn(message: string): void {
	try {
		console.error(`[mcp-gateway] ${message}`);
	} catch {
		// Logging must never break a run.
	}
}

/**
 * Load the card from the repo's canonical rules file.
 * Resolved relative to this file, so it works from any cwd.
 */
function loadCard(): string {
	try {
		const here = dirname(fileURLToPath(import.meta.url));
		const raw = readFileSync(resolve(here, "..", "..", "rules", "mcp-gway.md"), "utf8");
		if (raw.length === 0 || raw.length > MAX_RULES_BYTES) {
			warn("rules/mcp-gway.md is empty or implausibly large; using the embedded fallback card.");
			return FALLBACK_CARD;
		}
		return raw;
	} catch (error) {
		warn(
			`could not read rules/mcp-gway.md (${(error as Error)?.message ?? error}); using the embedded fallback card.`,
		);
		return FALLBACK_CARD;
	}
}

/** True when the rendered system prompt already carries the card. */
function alreadyPresent(systemPrompt: string): boolean {
	return systemPrompt.includes(MARKER) || systemPrompt.includes(RULES_HEADING);
}

export default function (pi: ExtensionAPI) {
	const card = loadCard();

	pi.on("before_agent_start", (event: BeforeAgentStartEvent, ctx) => {
		try {
			// `systemPromptOptions.sections` is the supported way to contribute a
			// prompt section: Pi wraps it in a tag and records a transcript delta,
			// instead of replacing the whole prompt for this turn.
			if (alreadyPresent(event.systemPrompt)) return;
			const { sections } = event.systemPromptOptions;
			if (sections[SECTION_KEY] === card) return;
			sections[SECTION_KEY] = card;
		} catch (error) {
			// Never let a card injection failure abort the turn.
			warn(`card injection skipped: ${(error as Error)?.message ?? error}`);
			if (ctx?.ui) {
				try {
					ctx.ui.notify(`mcp-gateway: Gateway Protocol card not injected`, "warning");
				} catch {
					// UI is optional (print/rpc modes).
				}
			}
		}
	});
}