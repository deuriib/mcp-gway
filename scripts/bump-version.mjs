// bump-version.mjs — the repo's single version tool.
//
// Two modes, one file:
//
//   node scripts/bump-version.mjs [major|minor|patch] [--dry-run]
//       Increment the version (manual fallback; the auto path is
//       `semantic-release version`). Source of truth is pyproject.toml,
//       package.json moves in lockstep. Everything else is left to
//       --write, which semantic-release runs as its build_command.
//
//   node scripts/bump-version.mjs --write [--version X.Y.Z]
//       Propagate the current (or given) version to every owned surface
//       so CI can verify with --check. Invoked automatically by
//       python-semantic-release via the build_command in pyproject.toml;
//       this replaces the retired scripts/sync_version.py.
//
// Owned sync surfaces (closed list — add here, never inline):
//   package.json                      "version": "X.Y.Z"  (2-space JSON)
//   src/mcp_gway/__init__.py          __version__ = "X.Y.Z"
//   plugin.json                       "version": "X.Y.Z"
//   uv.lock                           root package version (lockstep)
//   plugins/opencode/mcp-gateway.ts   const MARKER = "MCP-GWAY vX.Y.Z"
//   plugins/opencode/INSTALL.md       MCP-GWAY vX.Y.Z tokens
//   rules/mcp-gway.md                 <!-- MCP-GWAY vX.Y.Z -->
//   plugins/antigravity/scripts/reinject.mjs  MARKER + card comment
//   .pi/extensions/mcp-gateway.ts     MARKER const
//   plugins/*/INSTALL.md              MCP-GWAY vX.Y.Z tokens
//
// Deliberately NOT owned: CHANGELOG.md (written by semantic-release
// changelog in update mode, never touched here), docs history
// (v3.1.0 mentions stay as history), archived specs.
//
// Exit codes: 0 clean/wrote, 1 usage or version error, 2 drift found (--check).
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url))); // scripts/ -> repo root
const TYPES = ["major", "minor", "patch"];
const VERSION_RE = /^\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z-.]+)?$/;
const MARKER_RE = /MCP-GWAY v\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z-.]+)?/g;
const TS_MARKER_RE = /const MARKER = "MCP-GWAY v\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z-.]+)?";/g;
const LOCK_ROOT_RE = /(\[\[package\]\]\s+name = "mcp-gway"\s+version = ")[^"]+/;
const INIT_RE = /(__version__\s*=\s*")[^"]+/;
const PKG_VER_RE = /^(\s*"version"\s*:\s*")[^"]+/m;

function usage() {
	console.error(
		[
			"Usage:",
			"  node scripts/bump-version.mjs [major|minor|patch] [--dry-run]",
			"      increment pyproject.toml (+ package.json lockstep)",
			"  node scripts/bump-version.mjs --write [--version X.Y.Z]",
			"      propagate current/given version to all owned surfaces",
			"  node scripts/bump-version.mjs --check [--version X.Y.Z]",
			"      exit 2 with diff when any owned surface drifts",
			"",
			"CHANGELOG.md is always hand-written and never touched here.",
		].join("\n"),
	);
}

function fail(message) {
	console.error(`error: ${message}`);
	process.exit(1);
}

function parseArgs(argv) {
	const args = { type: null, dryRun: false, check: false, write: false, version: null, help: false };
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === "--dry-run" || a === "-n") args.dryRun = true;
		else if (a === "--check") args.check = true;
		else if (a === "--write") args.write = true;
		else if (a === "--help" || a === "-h") args.help = true;
		else if (a === "--version") {
			args.version = argv[++i];
			if (!args.version) fail("--version needs a value");
		} else if (TYPES.includes(a)) args.type = a;
		else {
			console.error(`Unknown argument: ${a}`);
			usage();
			process.exit(1);
		}
	}
	if (args.check && args.write) fail("--check and --write are mutually exclusive");
	if ((args.check || args.write) && args.type) fail("bump type cannot combine with --check/--write");
	if (args.dryRun && !args.type && !args.write) fail("--dry-run needs a bump type or --write");
	return args;
}

function normalize(raw) {
	const cleaned = String(raw).trim().replace(/^[vV]/, "");
	if (!VERSION_RE.test(cleaned)) fail(`invalid version ${JSON.stringify(raw)}: expected semver X.Y.Z`);
	return cleaned;
}

/** Source of truth: pyproject.toml [project] version (read-only). */
function readVersion(root) {
	const text = readFileSync(join(root, "pyproject.toml"), "utf8");
	const match = text.match(/^\[project\][\s\S]*?^version\s*=\s*"([^"]+)"/m);
	if (!match) fail("no [project] version in pyproject.toml");
	return { version: normalize(match[1]), raw: text };
}

function bumpVersion(current, type) {
	const [maj, min, pat] = current.split(".").map(Number);
	if (type === "major") return [maj + 1, 0, 0].join(".");
	if (type === "minor") return [maj, min + 1, 0].join(".");
	return [maj, min, pat + 1].join(".");
}

function setPyprojectVersion(root, raw, next) {
	writeFileSync(
		join(root, "pyproject.toml"),
		raw.replace(/^(\[project\][\s\S]*?^version\s*=\s*")[^"]+(")/m, `$1${next}$2`),
		"utf8",
	);
}

/** 2-space JSON rewrite, package.json repo style. */
function setJsonVersion(root, rel, next) {
	const path = join(root, rel);
	let data;
	try {
		data = JSON.parse(readFileSync(path, "utf8"));
	} catch {
		return { changed: false, reason: "unparseable" };
	}
	if (typeof data !== "object" || data === null) return { changed: false, reason: "not an object" };
	if (data.version === next) return { changed: false, reason: "already synced" };
	data.version = next;
	writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
	return { changed: true };
}

function subAll(text, re, replacement) {
	re.lastIndex = 0;
	const synced = text.replace(re, replacement);
	return { synced, count: (text.match(re) ?? []).length };
}

/** One owned file: read, sync, report (write only when asked). */
function syncFile(root, rel, version) {
	const path = join(root, rel);
	if (!existsSync(path)) return { rel, status: "missing" };
	const original = readFileSync(path, "utf8");
	let synced = original;
	if (rel.endsWith("plugins/opencode/mcp-gateway.ts")) {
		synced = original.replace(TS_MARKER_RE, `const MARKER = "MCP-GWAY v${version}";`);
	} else if (rel === "package.json" || rel === "plugin.json") {
		const data = JSON.parse(original);
		if (data.version === version) return { rel, status: "clean" };
		data.version = version;
		synced = `${JSON.stringify(data, null, 2)}\n`;
	} else if (rel.endsWith("uv.lock")) {
		synced = original.replace(LOCK_ROOT_RE, `$1${version}`);
	} else if (rel.endsWith("src/mcp_gway/__init__.py")) {
		synced = original.replace(INIT_RE, `$1${version}`);
	} else {
		synced = subAll(original, MARKER_RE, `MCP-GWAY v${version}`).synced;
	}
	return synced === original ? { rel, status: "clean" } : { rel, status: "drift", synced };
}

const OWNED = [
	"package.json",
	"src/mcp_gway/__init__.py",
	"plugin.json",
	"uv.lock",
	"plugins/opencode/mcp-gateway.ts",
	"plugins/opencode/INSTALL.md",
	"rules/mcp-gway.md",
	"plugins/antigravity/scripts/reinject.mjs",
	".pi/extensions/mcp-gateway.ts",
	"plugins/antigravity/INSTALL.md",
	"plugins/pi/INSTALL.md",
];

function syncAll(root, version, write) {
	const results = OWNED.map((rel) => syncFile(root, rel, version));
	const drifts = results.filter((r) => r.status === "drift");
	if (write) {
		for (const d of drifts) writeFileSync(join(root, d.rel), d.synced, "utf8");
	}
	return results;
}

function printDiff(rel, beforeRel, after) {
	// Minimal unified diff, no dependency.
	const before = readFileSync(beforeRel, "utf8").split("\n");
	const next = after.split("\n");
	console.log(`--- a/${rel}\n+++ b/${rel}`);
	const n = Math.max(before.length, next.length);
	for (let i = 0; i < n; i++) {
		if (before[i] !== next[i]) {
			if (before[i] !== undefined) console.log(`-${before[i]}`);
			if (next[i] !== undefined) console.log(`+${next[i]}`);
		}
	}
}

async function promptType() {
	const readline = await import("node:readline/promises");
	const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
	try {
		const answer = (await rl.question("Bump type (major|minor|patch): ")).trim().toLowerCase();
		if (!TYPES.includes(answer)) fail(`invalid type "${answer}"`);
		return answer;
	} finally {
		rl.close();
	}
}

async function main() {
	const args = parseArgs(process.argv.slice(2));
	if (args.help) {
		usage();
		process.exit(0);
	}
	if (args.check || args.write) {
		const version = args.version ? normalize(args.version) : readVersion(ROOT).version;
		const results = syncAll(ROOT, version, args.write);
		const drifts = results.filter((r) => r.status === "drift");
		const missing = results.filter((r) => r.status === "missing");
		for (const m of missing) console.error(`warn: owned file missing: ${m.rel}`);
		if (args.write) {
			for (const d of drifts) console.log(`synced ${d.rel} -> ${version}`);
			console.log(drifts.length === 0 ? `version-sync: clean at ${version}` : `version-sync: wrote ${drifts.length} file(s) at ${version}`);
			process.exit(0);
		}
		if (drifts.length > 0) {
			console.log(`version-sync: DRIFT at ${version} (${drifts.length} file(s))`);
			for (const d of drifts) printDiff(d.rel, join(ROOT, d.rel), d.synced);
			console.error("hint: run `node scripts/bump-version.mjs --write` to fix");
			process.exit(2);
		}
		console.log(`version-sync: clean at ${version}`);
		process.exit(0);
	}

	const type = args.type ?? (process.stdin.isTTY ? await promptType() : null);
	if (!type) {
		console.error("No bump type given and stdin is not a TTY.");
		usage();
		process.exit(1);
	}
	const { version: current, raw } = readVersion(ROOT);
	const next = bumpVersion(current, type);
	if (args.dryRun) {
		console.log(`[dry-run] ${current} -> ${next} (${type})`);
		process.exit(0);
	}
	setPyprojectVersion(ROOT, raw, next);
	const pkg = setJsonVersion(ROOT, "package.json", next);
	console.log(`bumped pyproject.toml${pkg.changed ? " + package.json" : ""}: ${current} -> ${next} (${type})`);
	console.log("next: node scripts/bump-version.mjs --write");
}

main().catch((err) => {
	console.error(err?.stack || String(err));
	process.exit(1);
});
