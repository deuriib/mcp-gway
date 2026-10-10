import type { Static } from "@earendil-works/pi-ai";
import { Type } from "@earendil-works/pi-ai";
import type {
  BeforeAgentStartEvent,
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * mcp-gateway — Pi extension.
 *
 * Parity with `plugins/antigravity/scripts/reinject.mjs`: keep the Gateway Protocol card in
 * the system prompt of every run, so it survives context compaction.
 *
 * MCP registration is declarative, not imperative: repo-root `mcp.json`
 * declares `gateway` over stdio (`uvx mcp-gway serve`) — loopback by
 * construction, no TCP surface. A same-named server in a user's project
 * `mcp.json` still takes precedence. The extension never calls
 * `pi.registerMcpServer`.
 * Re-injection happens on `before_agent_start` rather than on a `compaction` hook:
 * Pi re-enters the agent loop after compaction (threshold, overflow
 * recovery, retries), so re-applying the card at the start of every run
 * makes compaction survival a property of the design instead of something
 * we re-establish after the fact. The section is keyed and deduped, so
 * repeated firing within a run cannot duplicate it.
 *
 * The card text is read from `rules/mcp-gway.md` — the single source of truth
 * shared with the Antigravity plugin — so the harnesses cannot drift apart.
 *
 * Meta-tools as tools: the 4 CLI meta-tools (`mcp-gway tools
 * list|read|docs|exec`, same CodeMode operations as the `gateway_*` MCP tools)
 * plus the 2 top-level registry tools (`mcp-gway add|remove`) are exposed as
 * model-callable tools (`gw_list`, `gw_read`, `gw_docs`, `gw_exec`,
 * `gw_add`, `gw_remove`) via `pi.registerTool`, shelling out with `pi.exec`.
 *
 * Session inventory: on `session_start` the extension first probes `uvx
 * --version` (missing `uv` notifies once with the install URL and skips
 * inventory), then runs `mcp-gway tools list` once and publishes the server list as a hidden context message
 * (`display: false`), so the agent knows which servers are available from the
 * first turn without TUI noise. Every failure path degrades to a warning —
 * a missing CLI must never break session start.
 */

const MARKER = "MCP-GWAY v4.6.2";
const RULES_HEADING = "MCP Rules — Gateway Protocol";
const SECTION_KEY = "mcp-gateway";
const MAX_RULES_BYTES = 256 * 1024;

/** `mcp-gway` starts fast (console script, no gateway boot); still bounded. */
const LIST_TIMEOUT_MS = 15_000;
const CMD_TIMEOUT_MS = 60_000;
/** Probe timeout for the `uvx --version` guard at session start. */
const UV_CHECK_TIMEOUT_MS = 5_000;
/** Cap for a single result: a big server stub must not flood context. */
const MAX_OUTPUT_CHARS = 12_000;

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
    const raw = readFileSync(
      resolve(here, "..", "..", "rules", "mcp-gway.md"),
      "utf8",
    );
    if (raw.length === 0 || raw.length > MAX_RULES_BYTES) {
      warn(
        "rules/mcp-gway.md is empty or implausibly large; using the embedded fallback card.",
      );
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

interface ToolsOutcome {
  ok: boolean;
  text: string;
}

interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
  details: Record<string, string>;
}

/** Subset of ExtensionAPI used below (structural, so tests can stub it). */
interface Runner {
  exec(
    command: string,
    args: string[],
    options?: { timeout?: number },
  ): Promise<{ stdout: string; stderr: string; code: number }>;
  sendMessage(message: {
    customType: string;
    content: string;
    display: boolean;
  }): void;
}

/** Run `mcp-gway tools ...`; never throws — failures come back as `{ ok: false }`. */
async function runTools(
  runner: Runner,
  args: string[],
  timeoutMs: number,
): Promise<ToolsOutcome> {
  try {
    const { stdout, stderr, code } = await runner.exec(
      "uvx",
      ["mcp-gway", "tools", ...args],
      {
        timeout: timeoutMs,
      },
    );
    const out: string = (stdout ?? "").trim();
    if (code !== 0) {
      const err: string = (stderr ?? "").trim() || `exit code ${code}`;
      return {
        ok: false,
        text: `mcp-gway tools ${args[0] ?? ""} failed: ${err}`.trim(),
      };
    }
    return { ok: true, text: out === "" ? "(no output)" : out };
  } catch (error) {
    return {
      ok: false,
      text: `mcp-gway is not available: ${(error as Error)?.message ?? error}`,
    };
  }
}

/** Run `mcp-gway <top-level> ...`; never throws — failures come back as `{ ok: false }`. */
async function runRoot(
  runner: Runner,
  args: string[],
  timeoutMs: number,
): Promise<ToolsOutcome> {
  try {
    const { stdout, stderr, code } = await runner.exec(
      "uvx",
      ["mcp-gway", ...args],
      {
        timeout: timeoutMs,
      },
    );
    const out: string = (stdout ?? "").trim();
    if (code !== 0) {
      const err: string = (stderr ?? "").trim() || `exit code ${code}`;
      return {
        ok: false,
        text: `mcp-gway ${args[0] ?? ""} failed: ${err}`.trim(),
      };
    }
    return { ok: true, text: out === "" ? "(no output)" : out };
  } catch (error) {
    return {
      ok: false,
      text: `mcp-gway is not available: ${(error as Error)?.message ?? error}`,
    };
  }
}

function toResult(outcome: ToolsOutcome): ToolResult {
  const text: string =
    outcome.text.length <= MAX_OUTPUT_CHARS
      ? outcome.text
      : `${outcome.text.slice(0, MAX_OUTPUT_CHARS)}\n… [truncated ${outcome.text.length - MAX_OUTPUT_CHARS} chars]`;
  return {
    content: [{ type: "text", text: outcome.ok ? text : `Error: ${text}` }],
    details: {},
  };
}

const ListParams = Type.Object({
  binding: Type.Optional(
    Type.String({ description: "Stub binding level: server or tool" }),
  ),
});
type ListParams = Static<typeof ListParams>;

const ReadParams = Type.Object({
  server: Type.String({ description: "Server owning the stub" }),
  tool: Type.Optional(
    Type.String({ description: "Tool name for a single-tool stub" }),
  ),
  startLine: Type.Optional(
    Type.Number({ description: "First line (1-based)" }),
  ),
  endLine: Type.Optional(Type.Number({ description: "Last line (inclusive)" })),
});
type ReadParams = Static<typeof ReadParams>;

const DocsParams = Type.Object({
  server: Type.String({ description: "Server owning the tool" }),
  tool: Type.String({ description: "Tool to document" }),
});
type DocsParams = Static<typeof DocsParams>;

const ExecParams = Type.Object({
  code: Type.Optional(
    Type.String({ description: "Starlark snippet (assign `result`)" }),
  ),
  file: Type.Optional(
    Type.String({ description: "Path to a .star file to execute" }),
  ),
  timeout: Type.Optional(
    Type.Number({ description: "Execution timeout in seconds" }),
  ),
});
type ExecParams = Static<typeof ExecParams>;

async function runList(
  runner: Runner,
  params: ListParams,
): Promise<ToolResult> {
  const cliArgs: string[] = ["list"];
  if (params.binding !== undefined) cliArgs.push("--binding", params.binding);
  return toResult(await runTools(runner, cliArgs, LIST_TIMEOUT_MS));
}

async function runRead(
  runner: Runner,
  params: ReadParams,
): Promise<ToolResult> {
  const cliArgs: string[] = ["read", "--server", params.server];
  if (params.tool !== undefined) cliArgs.push("--tool", params.tool);
  if (params.startLine !== undefined)
    cliArgs.push("--start-line", String(params.startLine));
  if (params.endLine !== undefined)
    cliArgs.push("--end-line", String(params.endLine));
  return toResult(await runTools(runner, cliArgs, CMD_TIMEOUT_MS));
}

async function runDocs(
  runner: Runner,
  params: DocsParams,
): Promise<ToolResult> {
  return toResult(
    await runTools(
      runner,
      ["docs", "--server", params.server, "--tool", params.tool],
      CMD_TIMEOUT_MS,
    ),
  );
}

async function runExec(
  runner: Runner,
  params: ExecParams,
): Promise<ToolResult> {
  const hasCode: boolean = params.code !== undefined;
  const hasFile: boolean = params.file !== undefined;
  if (hasCode === hasFile) {
    return toResult({
      ok: false,
      text: "Pass exactly one of `code` or `file`.",
    });
  }
  const cliArgs: string[] = ["exec"];
  if (params.code !== undefined) cliArgs.push("--code", params.code);
  else cliArgs.push("--file", params.file as string);
  if (params.timeout !== undefined)
    cliArgs.push("--timeout", String(params.timeout));
  return toResult(await runTools(runner, cliArgs, CMD_TIMEOUT_MS));
}

const AddParams = Type.Object({
  name: Type.String({ description: "Server name to add" }),
  type: Type.Union([Type.Literal("local"), Type.Literal("remote")], {
    description: "Connection type: local or remote",
  }),
  command: Type.Optional(
    Type.String({ description: "Command for local servers" }),
  ),
  url: Type.Optional(Type.String({ description: "URL for remote servers" })),
  tools: Type.Optional(
    Type.String({ description: "Comma-separated tool names (default: all)" }),
  ),
  env: Type.Optional(
    Type.Array(Type.String(), {
      description: "Environment entries as KEY=VALUE (repeatable)",
    }),
  ),
  headers: Type.Optional(
    Type.Array(Type.String(), {
      description: "Header entries as KEY=VALUE for remote (repeatable)",
    }),
  ),
  cwd: Type.Optional(
    Type.String({ description: "Working directory for local servers" }),
  ),
  enabled: Type.Optional(
    Type.Boolean({ description: "Enable the server (default true)" }),
  ),
  timeout: Type.Optional(
    Type.Number({ description: "Timeout in milliseconds" }),
  ),
});
type AddParams = Static<typeof AddParams>;

const RemoveParams = Type.Object({
  name: Type.String({ description: "Server name to remove" }),
});
type RemoveParams = Static<typeof RemoveParams>;

async function runAdd(runner: Runner, params: AddParams): Promise<ToolResult> {
  if (params.type === "local" && params.command === undefined) {
    return toResult({
      ok: false,
      text: "gw_add: local servers need `command`, remote servers need `url`.",
    });
  }
  if (params.type === "remote" && params.url === undefined) {
    return toResult({
      ok: false,
      text: "gw_add: local servers need `command`, remote servers need `url`.",
    });
  }
  const cliArgs: string[] = ["add", params.name, "--type", params.type];
  if (params.type === "local" && params.command !== undefined)
    cliArgs.push("--command", params.command);
  if (params.type === "remote" && params.url !== undefined)
    cliArgs.push("--url", params.url);
  if (params.tools !== undefined) cliArgs.push("--tools", params.tools);
  for (const e of params.env ?? []) cliArgs.push("--env", e);
  for (const h of params.headers ?? []) cliArgs.push("--header", h);
  if (params.cwd !== undefined) cliArgs.push("--cwd", params.cwd);
  if (params.enabled === false) cliArgs.push("--no-enabled");
  if (params.timeout !== undefined)
    cliArgs.push("--timeout", String(params.timeout));
  return toResult(await runRoot(runner, cliArgs, CMD_TIMEOUT_MS));
}

async function runRemove(
  runner: Runner,
  params: RemoveParams,
): Promise<ToolResult> {
  return toResult(
    await runRoot(runner, ["remove", params.name], CMD_TIMEOUT_MS),
  );
}

export default function (pi: ExtensionAPI) {
  const card: string = loadCard();
  const runner = pi as unknown as Runner;

  pi.registerTool({
    name: "gw_list",
    label: "Gateway list",
    description: "List gateway servers (mcp-gway tools list)",
    promptSnippet:
      "gw_list: list available gateway servers before guessing a server name.",
    promptGuidelines: [
      "Use gw_list when the user asks which servers or tools are available.",
    ],
    parameters: ListParams,
    async execute(
      _toolCallId: string,
      params: ListParams,
    ): Promise<ToolResult> {
      return runList(runner, params);
    },
  });

  pi.registerTool({
    name: "gw_read",
    label: "Gateway read",
    description: "Read a gateway server stub (mcp-gway tools read)",
    promptSnippet:
      "gw_read: read a server stub for exact tool names and params.",
    promptGuidelines: [
      "Use gw_read with a server name before calling gw_exec.",
    ],
    parameters: ReadParams,
    async execute(
      _toolCallId: string,
      params: ReadParams,
    ): Promise<ToolResult> {
      return runRead(runner, params);
    },
  });

  pi.registerTool({
    name: "gw_docs",
    label: "Gateway docs",
    description: "Show gateway tool docs (mcp-gway tools docs)",
    promptSnippet:
      "gw_docs: full docs for one gateway tool when the stub is truncated.",
    promptGuidelines: [
      "Use gw_docs with server and tool when the stub omits details.",
    ],
    parameters: DocsParams,
    async execute(
      _toolCallId: string,
      params: DocsParams,
    ): Promise<ToolResult> {
      return runDocs(runner, params);
    },
  });

  pi.registerTool({
    name: "gw_exec",
    label: "Gateway exec",
    description: "Execute Starlark via gateway tools (mcp-gway tools exec)",
    promptSnippet:
      "gw_exec: run Starlark code that assigns `result` via Server.tool calls.",
    promptGuidelines: [
      "Use gw_exec with code or file, never both, to run gateway tools.",
    ],
    parameters: ExecParams,
    async execute(
      _toolCallId: string,
      params: ExecParams,
    ): Promise<ToolResult> {
      return runExec(runner, params);
    },
  });

  pi.registerTool({
    name: "gw_add",
    label: "Gateway add",
    description: "Add a gateway server (mcp-gway add)",
    promptSnippet:
      "gw_add: add a local (command) or remote (url) server to the gateway.",
    promptGuidelines: [
      "Use gw_add with name and type before gw_list when a server is missing.",
    ],
    parameters: AddParams,
    async execute(_toolCallId: string, params: AddParams): Promise<ToolResult> {
      return runAdd(runner, params);
    },
  });

  pi.registerTool({
    name: "gw_remove",
    label: "Gateway remove",
    description: "Remove a gateway server (mcp-gway remove)",
    promptSnippet: "gw_remove: remove a gateway server by name.",
    promptGuidelines: [
      "Use gw_remove with a server name to drop a stale registration.",
    ],
    parameters: RemoveParams,
    async execute(
      _toolCallId: string,
      params: RemoveParams,
    ): Promise<ToolResult> {
      return runRemove(runner, params);
    },
  });

  // Server inventory at session start: the agent knows what is available
  // from the first turn. Hidden from the TUI (display: false) — it is
  // context, not conversation.
  pi.on("session_start", async (_event, ctx: ExtensionContext) => {
    try {
      try {
        const uv = await runner.exec("uvx", ["--version"], {
          timeout: UV_CHECK_TIMEOUT_MS,
        });
        if (uv.code !== 0) throw new Error(`exit code ${uv.code}`);
      } catch (error) {
        warn(
          `session inventory skipped: uvx not available (${(error as Error)?.message ?? error})`,
        );
        if (ctx && ctx.hasUI) {
          try {
            ctx.ui.notify(
              "mcp-gateway: 'uv' (uvx) was not found on PATH. Install uv from https://docs.astral.sh/uv/, then reload (/reload) or reopen Pi.",
              "error",
            );
          } catch {
            // UI is optional (print/rpc modes).
          }
        }
        return;
      }
      const outcome: ToolsOutcome = await runTools(
        runner,
        ["list"],
        LIST_TIMEOUT_MS,
      );
      if (!outcome.ok) {
        warn(`session inventory skipped: ${outcome.text}`);
        return;
      }
      runner.sendMessage({
        customType: "mcp-gateway-servers",
        content: `Available MCP servers (mcp-gway tools list):\n${outcome.text}`,
        display: false,
      });
    } catch (error) {
      warn(`session inventory skipped: ${(error as Error)?.message ?? error}`);
    }
  });

  pi.on(
    "before_agent_start",
    (event: BeforeAgentStartEvent, ctx: ExtensionContext) => {
      try {
        // `systemPromptOptions.sections` is the supported way to contribute a
        // prompt section: Pi wraps it in a tag and records a transcript delta,
        // instead of replacing the whole prompt for this turn.
        if (alreadyPresent(event.systemPrompt)) return;
        const sections = event.systemPromptOptions?.sections;
        if (sections) {
          if (sections[SECTION_KEY] === card) return;
          sections[SECTION_KEY] = card;
          return;
        }
        // omp (oh-my-pi) emits `before_agent_start` without
        // `systemPromptOptions`; request an explicit full-prompt replacement so
        // the card still lands and the handler returns without throwing.
        const systemPrompt =
          typeof event.systemPrompt === "string" ? event.systemPrompt : "";
        return {
          systemPrompt: alreadyPresent(systemPrompt)
            ? systemPrompt
            : `${systemPrompt}${systemPrompt.endsWith("\n") || systemPrompt === "" ? "" : "\n\n"}${card}\n`,
        };
      } catch (error) {
        // Never let a card injection failure abort the turn.
        warn(`card injection skipped: ${(error as Error)?.message ?? error}`);
        if (ctx?.ui) {
          try {
            ctx.ui.notify(
              `mcp-gateway: Gateway Protocol card not injected`,
              "warning",
            );
          } catch {
            // UI is optional (print/rpc modes).
          }
        }
      }
    },
  );
}
