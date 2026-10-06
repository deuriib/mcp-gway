import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

// Extension shells out via `uvx mcp-gway tools ...` through `pi.exec`.
// Keep command/arg/timeout assertions on the uvx contract exact.
const CLI = "uvx";
const CLI_PREFIX = ["mcp-gway", "tools"];
const LIST_TIMEOUT_MS = 15_000;
const CMD_TIMEOUT_MS = 60_000;
const MAX_OUTPUT_CHARS = 12_000;

const ext = await import(
	pathToFileURL(resolve(here, "..", ".pi", "extensions", "mcp-gateway.ts")).href
);

let failures = 0;
let pending = [];
const check = (name, fn) => {
	pending.push(
		Promise.resolve()
			.then(fn)
			.then(() => console.log(`PASS ${name}`))
			.catch((error) => {
				failures += 1;
				console.log(`FAIL ${name}: ${error.message}`);
			}),
	);
};

// Full ExtensionAPI stub: card injection + gw_* tools + session inventory.
// MCP registration is declarative (.mcp.json) — the extension registers no servers.
function makePi(execImpl) {
	const handlers = new Map();
	const tools = new Map();
	const sent = [];
	const execCalls = [];
	const api = {
		on: (event, handler) => {
			handlers.set(event, handler);
			return () => {};
		},
		registerTool: (tool) => {
			tools.set(tool.name, tool);
		},
		exec: async (command, args, options) => {
			execCalls.push({ command, args, options });
			if (execImpl) return execImpl(command, args, options);
			return { stdout: "servers/Omniroute.pyi", stderr: "", code: 0 };
		},
		sendMessage: (message) => {
			sent.push(message);
		},
		// Exposed so assertions can inspect what was registered.
		handlers,
		tools,
		sent,
		execCalls,
	};
	return { handlers, tools, sent, execCalls, api };
}

const card = readFileSync(resolve(here, "..", "rules", "mcp-gway.md"), "utf8");

function handlerFor(api) {
	const names = [...api.handlers.keys()];
	const direct = api.handlers.get("before_agent_start");
	if (direct) return direct;
	if (names.length === 0) {
		throw new Error(`extension registered no handlers (saw: ${JSON.stringify(names)})`);
	}
	throw new Error(
		`no "before_agent_start" handler; registered: ${JSON.stringify(names)}`,
	);
}

check("loads card from canonical rules file (no fallback)", () => {
	const { api } = makePi();
	ext.default(api);
	const event = { systemPrompt: "", systemPromptOptions: { sections: {} } };
	handlerFor(api)(event, {});
	assert.ok(event.systemPromptOptions.sections["mcp-gateway"], "card not injected");
	assert.equal(
		event.systemPromptOptions.sections["mcp-gateway"].trim(),
		card.trim(),
		"injected card differs from rules/mcp-gway.md",
	);
});

check("injects card when system prompt is empty", () => {
	const { api } = makePi();
	ext.default(api);
	const event = { systemPrompt: "", systemPromptOptions: { sections: {} } };
	handlerFor(api)(event, {});
	assert.ok(event.systemPromptOptions.sections["mcp-gateway"]);
});

check("does not duplicate when MARKER already in system prompt", () => {
	const { api } = makePi();
	ext.default(api);
	const event = {
		systemPrompt: `... ${card}`,
		systemPromptOptions: { sections: {} },
	};
	handlerFor(api)(event, {});
	assert.equal(
		Object.keys(event.systemPromptOptions.sections).length,
		0,
		"re-injected a card already present",
	);
});

check("does not duplicate when MARKER already in sections", () => {
	const { api } = makePi();
	ext.default(api);
	const event = {
		systemPrompt: "",
		systemPromptOptions: { sections: { "mcp-gateway": card } },
	};
	handlerFor(api)(event, {});
	assert.equal(Object.keys(event.systemPromptOptions.sections).length, 1);
});

check("skips injection when only the heading is present in system prompt", () => {
	const { api } = makePi();
	ext.default(api);
	const event = {
		systemPrompt: "## MCP Rules — Gateway Protocol",
		systemPromptOptions: { sections: {} },
	};
	handlerFor(api)(event, {});
	assert.equal(Object.keys(event.systemPromptOptions.sections).length, 0);
});

check("degrades without throwing on a malformed event", () => {
	const { api } = makePi();
	ext.default(api);
	assert.doesNotThrow(() => handlerFor(api)({}, {}));
});

check("card carries the mandatory 4-step order", () => {
	const { api } = makePi();
	ext.default(api);
	const event = { systemPrompt: "", systemPromptOptions: { sections: {} } };
	handlerFor(api)(event, {});
	const injected = event.systemPromptOptions.sections["mcp-gateway"];
	for (const step of [
		"gateway_listToolFiles",
		"gateway_readToolFile",
		"gateway_getToolDocs",
		"gateway_executeToolCode",
	]) {
		assert.ok(injected.includes(step), `missing ${step}`);
	}
});

check("registers the 4 meta-tools", () => {
	const { api } = makePi();
	ext.default(api);
	for (const name of ["gw_list", "gw_read", "gw_docs", "gw_exec"]) {
		assert.ok(api.tools.has(name), `missing tool ${name}`);
	}
});

check("declares gateway over stdio in .mcp.json (uvx mcp-gway serve)", () => {
	const raw = readFileSync(resolve(here, "..", ".mcp.json"), "utf8");
	const data = JSON.parse(raw);
	assert.deepEqual(data.mcpServers.gateway, { command: "uvx", args: ["mcp-gway", "serve"] });
});

check("gw_list shells out to uvx mcp-gway tools list", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_list").execute("id", {});
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "list"]);
	assert.equal(execCalls[0].options.timeout, LIST_TIMEOUT_MS);
	assert.ok(res.content[0].text.includes("servers/Omniroute.pyi"));
	assert.ok(!res.content[0].text.startsWith("Error:"));
});

check("gw_list forwards binding", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_list").execute("id", { binding: "tool" });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "list", "--binding", "tool"]);
	assert.equal(execCalls[0].options.timeout, LIST_TIMEOUT_MS);
});

check("gw_read forwards server and tool", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_read").execute("id", { server: "Omniroute", tool: "web_search" });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "read", "--server", "Omniroute", "--tool", "web_search"]);
	assert.equal(execCalls[0].options.timeout, CMD_TIMEOUT_MS);
});

check("gw_read forwards line range", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_read").execute("id", { server: "Omniroute", startLine: 1, endLine: 40 });
	assert.deepEqual(execCalls[0].args, [
		...CLI_PREFIX,
		"read",
		"--server",
		"Omniroute",
		"--start-line",
		"1",
		"--end-line",
		"40",
	]);
});

check("gw_docs forwards server and tool", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_docs").execute("id", { server: "Omniroute", tool: "web_search" });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "docs", "--server", "Omniroute", "--tool", "web_search"]);
	assert.equal(execCalls[0].options.timeout, CMD_TIMEOUT_MS);
});

check("gw_exec with neither code nor file returns a usage error", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_exec").execute("id", {});
	assert.equal(execCalls.length, 0);
	assert.ok(res.content[0].text.includes("exactly one"));
});

check("gw_exec with both code and file returns a usage error", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_exec").execute("id", { code: "x", file: "y.star" });
	assert.equal(execCalls.length, 0);
	assert.ok(res.content[0].text.includes("exactly one"));
});

check("gw_exec forwards code", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_exec").execute("id", { code: 'result = Omniroute.web_search(query="x")' });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "exec", "--code", 'result = Omniroute.web_search(query="x")']);
	assert.equal(execCalls[0].options.timeout, CMD_TIMEOUT_MS);
	assert.ok(!res.content[0].text.startsWith("Error:"));
});

check("gw_exec forwards file and timeout", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_exec").execute("id", { file: "snippet.star", timeout: 30 });
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "exec", "--file", "snippet.star", "--timeout", "30"]);
});

check("tool failure surfaces an error result, never throws", async () => {
	const { api } = makePi(async () => ({ stdout: "", stderr: "boom", code: 1 }));
	ext.default(api);
	const res = await api.tools.get("gw_list").execute("id", {});
	assert.ok(res.content[0].text.startsWith("Error:"));
	assert.ok(res.content[0].text.includes("boom"));
});

check("missing CLI degrades to an error result, never throws", async () => {
	const { api } = makePi(async () => {
		throw new Error("spawn uvx ENOENT");
	});
	ext.default(api);
	const res = await api.tools.get("gw_list").execute("id", {});
	assert.ok(res.content[0].text.startsWith("Error:"));
	assert.ok(res.content[0].text.includes("mcp-gway is not available"));
});

check("long output truncates with a remainder note", async () => {
	const big = "x".repeat(MAX_OUTPUT_CHARS + 100);
	const { api } = makePi(async () => ({ stdout: big, stderr: "", code: 0 }));
	ext.default(api);
	const res = await api.tools.get("gw_list").execute("id", {});
	assert.ok(res.content[0].text.includes("[truncated 100 chars]"));
});

check("empty CLI output reports (no output)", async () => {
	const { api } = makePi(async () => ({ stdout: "   \n", stderr: "", code: 0 }));
	ext.default(api);
	const res = await api.tools.get("gw_list").execute("id", {});
	assert.ok(res.content[0].text.includes("(no output)"));
});

check("session_start publishes a hidden server inventory", async () => {
	const { api, execCalls, sent } = makePi();
	ext.default(api);
	await api.handlers.get("session_start")({ type: "session_start", reason: "startup" }, {});
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "list"]);
	assert.equal(execCalls[0].options.timeout, LIST_TIMEOUT_MS);
	assert.equal(sent.length, 1);
	assert.equal(sent[0].customType, "mcp-gateway-servers");
	assert.equal(sent[0].display, false);
	assert.ok(sent[0].content.includes("servers/Omniroute.pyi"));
});

check("session_start degrades silently when the CLI is missing", async () => {
	const { api, sent } = makePi(async () => {
		throw new Error("spawn uvx ENOENT");
	});
	ext.default(api);
	await api.handlers.get("session_start")({ type: "session_start", reason: "startup" }, {});
	assert.equal(sent.length, 0);
});

check("gw_read without tool omits --tool flag", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_read").execute("id", { server: "Omniroute" });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_PREFIX, "read", "--server", "Omniroute"]);
	assert.equal(execCalls[0].options.timeout, CMD_TIMEOUT_MS);
});

check("tool failure without stderr reports exit code", async () => {
	const { api } = makePi(async () => ({ stdout: "", stderr: "  ", code: 2 }));
	ext.default(api);
	const res = await api.tools.get("gw_read").execute("id", { server: "Omniroute" });
	assert.ok(res.content[0].text.startsWith("Error:"));
	assert.ok(res.content[0].text.includes("exit code 2"));
});

await Promise.all(pending);
console.log(failures === 0 ? "\nALL GREEN" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
