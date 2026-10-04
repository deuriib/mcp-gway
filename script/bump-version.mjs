#!/usr/bin/env node
// bump-version.mjs — bump the project version in pyproject.toml (source of
// truth) and package.json (lockstep), then print the remaining sync step.
//
// This script does the mechanical increment only. `scripts/sync_version.py`
// stays the canonical propagator for every other owned surface
// (src/mcp_gway/__init__.py, plugins/*/INSTALL.md + markers, README, AGENTS,
// uv.lock). CHANGELOG.md is maintained by hand and is never touched here.
//
// Usage:
//   node script/bump-version.mjs            # interactive prompt (major|minor|patch)
//   node script/bump-version.mjs minor      # non-interactive
//   node script/bump-version.mjs minor --dry-run
//
// Requires: bump parts to already agree (use --dry-run to check).
// Exit codes: 0 success, 1 error.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url))); // script/ -> repo root
const CONFIG_PATH = join(ROOT, ".bump-version.json");
const TYPES = ["major", "minor", "patch"];

function usage() {
	console.error(
		[
			"Usage: node script/bump-version.mjs [major|minor|patch] [--dry-run]",
			"",
			"  major|minor|patch  Semver increment type (prompted if omitted).",
			"  --dry-run          Print the resulting versions without writing files.",
			"",
			"Then run:  uv run scripts/sync_version.py --write",
		].join("\n"),
	);
}

function parseArgs(argv) {
	const args = { type: null, dryRun: false, help: false };
	for (const a of argv) {
		if (a === "--dry-run" || a === "-n") args.dryRun = true;
		else if (a === "--help" || a === "-h") args.help = true;
		else if (TYPES.includes(a)) args.type = a;
		else {
			console.error(`Unknown argument: ${a}`);
			usage();
			process.exit(1);
		}
	}
	return args;
}

/** Extract `version = "X.Y.Z"` from pyproject.toml's [project] table. */
function readPyprojectVersion(root) {
	const text = readFileSync(join(root, "pyproject.toml"), "utf8");
	const match = text.match(/^\[project\][\s\S]*?^version\s*=\s*"([^"]+)"/m);
	if (!match) {
		console.error("No [project] version found in pyproject.toml");
		process.exit(1);
	}
	return { version: match[1], raw: text };
}

function bump(v, type) {
	const [maj, min, pat] = v.split(".").map((n) => Number(n));
	if ([maj, min, pat].some((n) => Number.isNaN(n))) {
		console.error(`Current version is not semver: "${v}"`);
		process.exit(1);
	}
	if (type === "major") return [maj + 1, 0, 0].join(".");
	if (type === "minor") return [maj, min + 1, 0].join(".");
	return [maj, min, pat + 1].join(".");
}

function writePyprojectVersion(root, raw, next) {
	const updated = raw.replace(
		/^(\[project\][\s\S]*?^version\s*=\s*")[^"]+(")/m,
		`$1${next}$2`,
	);
	writeFileSync(join(root, "pyproject.toml"), updated, "utf8");
}

function writePackageJsonVersion(root, next) {
	const path = join(root, "package.json");
	const data = JSON.parse(readFileSync(path, "utf8"));
	data.version = next;
	writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

async function promptType() {
	const readline = await import("node:readline/promises");
	const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
	try {
		const answer = (await rl.question("Bump type (major|minor|patch): ")).trim().toLowerCase();
		if (!TYPES.includes(answer)) {
			console.error(`Invalid type "${answer}". Expected: ${TYPES.join(" | ")}`);
			process.exit(1);
		}
		return answer;
	} finally {
		rl.close();
	}
}

function checkConfig(root) {
	const path = join(root, ".bump-version.json");
	if (!existsSync(path)) {
		console.error(`Missing config: ${path}`);
		process.exit(1);
	}
	try {
		JSON.parse(readFileSync(path, "utf8"));
	} catch (err) {
		console.error(`Invalid JSON in ${path}: ${err.message}`);
		process.exit(1);
	}
}

async function main() {
	const args = parseArgs(process.argv.slice(2));
	if (args.help) {
		usage();
		process.exit(0);
	}
	checkConfig(ROOT);
	const type = args.type ?? (process.stdin.isTTY ? await promptType() : null);
	if (!type) {
		console.error("No bump type given and stdin is not a TTY.");
		usage();
		process.exit(1);
	}
	const { version: current } = readPyprojectVersion(ROOT);
	const next = bump(current, type);
	if (args.dryRun) {
		console.log(`[dry-run] pyproject.toml: ${current} -> ${next} (${type})`);
		console.log(`[dry-run] package.json: ${current} -> ${next} (${type})`);
		console.log("[dry-run] follow with: uv run scripts/sync_version.py --write");
		process.exit(0);
	}
	writePyprojectVersion(ROOT, readPyprojectVersion(ROOT).raw, next);
	writePackageJsonVersion(ROOT, next);
	console.log(`Bumped pyproject.toml + package.json: ${current} -> ${next} (${type})`);
	console.log("Next: uv run scripts/sync_version.py --write");
}

main().catch((err) => {
	console.error(err?.stack || String(err));
	process.exit(1);
});
