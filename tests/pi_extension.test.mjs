import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

// Extension shells out via `uvx mcp-gway tools ...` through `pi.exec`.
// Keep command/arg/timeout assertions on the uvx contract exact.
const CLI = "uvx";
const CLI_PREFIX = ["mcp-gway", "tools"];
const CLI_ROOT = ["mcp-gway"];
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
// MCP registration is declarative (repo-root mcp.json) — the extension never
// calls pi.registerMcpServer; stubs stay only to prove zero calls.
function makePi(execImpl) {
	const handlers = new Map();
	const tools = new Map();
	const sent = [];
	const execCalls = [];
	const mcpCalls = [];
	const notified = [];
	const api = {
		on: (event, handler) => {
			handlers.set(event, handler);
			return () => {};
		},
		registerTool: (tool) => {
			tools.set(tool.name, tool);
		},
		registerMcpServer: (name, config) => {
			mcpCalls.push({ name, config });
		},
		unregisterMcpServer: (name) => {
			const idx = mcpCalls.findIndex((c) => c.name === name);
			if (idx >= 0) mcpCalls.splice(idx, 1);
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
		mcpCalls,
		notified,
	};
	return { handlers, tools, sent, execCalls, mcpCalls, notified, api };
}

function notifyCtx(api) {
	return {
		hasUI: true,
		ui: {
			notify: (message, type) => {
				api.notified.push({ message, type });
			},
		},
	};
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
check("returns a systemPrompt replacement when options are missing (omp)", () => {
	const { api } = makePi();
	ext.default(api);
	const event = { systemPrompt: "", systemPromptOptions: undefined };
	const result = handlerFor(api)(event, {});
	assert.ok(result?.systemPrompt?.includes("MCP Rules — Gateway Protocol"));
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

check("registers the 6 meta-tools", () => {
	const { api } = makePi();
	ext.default(api);
	for (const name of ["gw_list", "gw_read", "gw_docs", "gw_exec", "gw_add", "gw_remove"]) {
		assert.ok(api.tools.has(name), `missing tool ${name}`);
	}
});

check("never calls pi.registerMcpServer (declarative mcp.json owns registration)", () => {
	const { api, mcpCalls } = makePi();
	ext.default(api);
	assert.equal(mcpCalls.length, 0);
});

check("declares gateway in repo-root mcp.json (uvx mcp-gway serve)", () => {
	const raw = readFileSync(resolve(here, "..", "mcp.json"), "utf8");
	const config = JSON.parse(raw);
	assert.equal(config.mcpServers.gateway.command, "uvx");
	assert.deepEqual(config.mcpServers.gateway.args, ["mcp-gway", "serve"]);
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

check("session_start probes uvx then publishes a hidden server inventory", async () => {
	const { api, execCalls, sent } = makePi();
	ext.default(api);
	await api.handlers.get("session_start")({ type: "session_start", reason: "startup" }, {});
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, ["--version"]);
	assert.equal(execCalls[1].command, CLI);
	assert.deepEqual(execCalls[1].args, [...CLI_PREFIX, "list"]);
	assert.equal(execCalls[1].options.timeout, LIST_TIMEOUT_MS);
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

check("session_start without uv notifies with install URL and skips inventory", async () => {
	const { api, execCalls, sent, notified } = makePi(async (command, args) => {
		if (args[0] === "--version") throw new Error("spawn uvx ENOENT");
		return { stdout: "servers/Omniroute.pyi", stderr: "", code: 0 };
	});
	ext.default(api);
	await api.handlers.get("session_start")({ type: "session_start", reason: "startup" }, notifyCtx(api));
	assert.equal(execCalls.length, 1);
	assert.deepEqual(execCalls[0].args, ["--version"]);
	assert.equal(sent.length, 0);
	assert.equal(notified.length, 1);
	assert.ok(notified[0].message.includes("'uv' (uvx) was not found on PATH"));
	assert.ok(notified[0].message.includes("https://docs.astral.sh/uv/"));
	assert.ok(notified[0].message.includes("/reload"));
});

check("gw_add local shells out to uvx mcp-gway add with --command", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_add").execute("id", { name: "MyServer", type: "local", command: "npx -y x" });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_ROOT, "add", "MyServer", "--type", "local", "--command", "npx -y x"]);
	assert.equal(execCalls[0].options.timeout, CMD_TIMEOUT_MS);
	assert.ok(!res.content[0].text.startsWith("Error:"));
});

check("gw_add local forwards env, cwd, timeout and --no-enabled", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_add").execute("id", {
		name: "MyServer",
		type: "local",
		command: "npx -y x",
		tools: "a,b",
		env: ["KEY=VALUE"],
		headers: ["H=V"],
		cwd: "/tmp",
		enabled: false,
		timeout: 9000,
	});
	assert.deepEqual(execCalls[0].args, [
		...CLI_ROOT, "add", "MyServer", "--type", "local",
		"--command", "npx -y x", "--tools", "a,b",
		"--env", "KEY=VALUE", "--header", "H=V",
		"--cwd", "/tmp", "--no-enabled", "--timeout", "9000",
	]);
});

check("gw_add remote shells out with --url", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_add").execute("id", { name: "Remote", type: "remote", url: "https://example.com/mcp" });
	assert.deepEqual(execCalls[0].args, [...CLI_ROOT, "add", "Remote", "--type", "remote", "--url", "https://example.com/mcp"]);
});

check("gw_add local without command returns usage error with zero exec calls", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_add").execute("id", { name: "Foo", type: "local" });
	assert.equal(execCalls.length, 0);
	assert.ok(res.content[0].text.includes("local servers need `command`"));
});

check("gw_add remote without url returns usage error with zero exec calls", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	const res = await api.tools.get("gw_add").execute("id", { name: "Foo", type: "remote" });
	assert.equal(execCalls.length, 0);
	assert.ok(res.content[0].text.includes("remote servers need `url`"));
});

check("gw_remove shells out to uvx mcp-gway remove", async () => {
	const { api, execCalls } = makePi();
	ext.default(api);
	await api.tools.get("gw_remove").execute("id", { name: "Foo" });
	assert.equal(execCalls[0].command, CLI);
	assert.deepEqual(execCalls[0].args, [...CLI_ROOT, "remove", "Foo"]);
	assert.equal(execCalls[0].options.timeout, CMD_TIMEOUT_MS);
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
