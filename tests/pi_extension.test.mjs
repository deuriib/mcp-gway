import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const ext = await import(
	pathToFileURL(resolve(here, "..", ".pi", "extensions", "mcp-gateway.ts")).href
);

let failures = 0;
const check = (name, fn) => {
	try {
		fn();
		console.log(`PASS ${name}`);
	} catch (error) {
		failures += 1;
		console.log(`FAIL ${name}: ${error.message}`);
	}
};

// Pi injects handlers via `pi.on(...)`. The event under test may be named
// "before_agent_start"; if the runtime registers a different name, report which
// one was actually seen instead of failing every check with an opaque error.
function makePi() {
	const handlers = new Map();
	const api = {
		on: (event, handler) => {
			handlers.set(event, handler);
			return () => {};
		},
		// Exposed so assertions can inspect which events were registered.
		handlers,
	};
	return { handlers, api };
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

console.log(failures === 0 ? "\nALL GREEN" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);