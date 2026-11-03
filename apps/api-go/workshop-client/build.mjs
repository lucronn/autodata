// Build-only tooling; never imported by the Workshop or production Go runtime.
import { build, version as esbuildVersion } from 'esbuild';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, writeFile, mkdir, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const client = dirname(fileURLToPath(import.meta.url));
const repo = resolve(client, '../../..');
const assets = resolve(client, '../workshop');
const names = ['firebase-web.mjs', 'firebase-web.mjs.LEGAL.txt', 'firebase-web.provenance.json'];
const expectedExports = ['GoogleAuthProvider', 'browserPopupRedirectResolver', 'getIdTokenResult', 'inMemoryPersistence', 'initializeApp', 'initializeAuth', 'reauthenticateWithPopup', 'setPersistence', 'signInWithPopup', 'signOut'];
const options = { bundle: true, format: 'esm', platform: 'browser', target: 'es2022', minify: true, legalComments: 'external', sourcemap: false };
const canonical = path => relative(repo, path).split(sep).join('/');
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const json = async path => JSON.parse(await readFile(path, 'utf8'));
const describe = async path => {
  const bytes = await readFile(path);
  return { path: canonical(path), sha256: digest(bytes), bytes: bytes.length };
};

async function generate(scratch) {
  if (Number(process.versions.node.split('.')[0]) < 20) throw new Error('Node >=20 is required');
  const manifest = await json(join(client, 'package.json'));
  const lock = await json(join(client, 'package-lock.json'));
  if (manifest.dependencies.firebase !== '12.19.0' || manifest.devDependencies.esbuild !== '0.28.2' || esbuildVersion !== '0.28.2') throw new Error('Pinned Firebase/esbuild versions are required');
  const pins = {
    firebase: ['12.19.0', 'sha512-kwXCLcI0ly2lkwygkbuRx6SsX3DSO96355YrWh9SWZ5ncsxK/y5cirn3sY6nZVSiBVE++2nL6Hchzu1EB8uohQ=='],
    '@firebase/auth': ['1.13.6', 'sha512-MKRLvF72HJ/irNn2fJR0Gv5FOZNtqv1IBeJHRwK8l8pZ/wi9vuUw8ecyCMvQDDNxfS6uW0MWACL5KC4Y8Pp+fA=='],
    '@firebase/app': ['0.16.2'],
    esbuild: ['0.28.2'],
  };
  for (const [name, [version, integrity]] of Object.entries(pins)) {
    const locked = lock.packages[`node_modules/${name}`];
    const installed = await json(join(client, 'node_modules', name, 'package.json'));
    if (locked?.version !== version || installed.version !== version || (integrity && locked.integrity !== integrity)) throw new Error(`Pinned dependency mismatch: ${name}; run npm ci --ignore-scripts`);
  }
  for (const [path, entry] of Object.entries(lock.packages)) {
    if (path && (!entry.integrity?.startsWith('sha512-') || !entry.resolved?.startsWith('https://registry.npmjs.org/'))) throw new Error(`Incomplete registry lock: ${path}`);
  }
  const outfile = join(scratch, names[0]);
  const result = await build({ ...options, absWorkingDir: client, entryPoints: ['firebase-entry.mjs'], outfile, metafile: true, write: true, logLevel: 'silent' });
  const emitted = Object.entries(result.metafile.outputs);
  const module = emitted.find(([path]) => path.endsWith('/firebase-web.mjs'))?.[1];
  if (!module || JSON.stringify([...module.exports].sort()) !== JSON.stringify(expectedExports)) throw new Error('Unexpected emitted ESM exports');
  if (Object.values(result.metafile.inputs).some(input => input.imports.some(item => item.external)) || emitted.some(([path, output]) => path.endsWith('.map') || output.imports.length)) throw new Error('External imports or source maps are forbidden');
  if (emitted.length !== 2 || !emitted.some(([path]) => path.endsWith('/firebase-web.mjs.LEGAL.txt'))) throw new Error('Unexpected emitted artifacts');

  // Keep extracted source notices and full licenses for every included package.
  const packages = new Map();
  for (const input of Object.keys(result.metafile.inputs).sort()) {
    if (!input.startsWith('node_modules/')) continue;
    const parts = input.split('/');
    const name = parts[1].startsWith('@') ? parts.slice(1, 3).join('/') : parts[1];
    if (packages.has(name)) continue;
    const packageRoot = join(client, 'node_modules', name);
    const pkg = await json(join(packageRoot, 'package.json'));
    if (lock.packages[`node_modules/${name}`]?.version !== pkg.version) throw new Error(`Installed package differs from lock: ${name}`);
    const noticeFiles = (await readdir(packageRoot, { withFileTypes: true })).filter(entry => entry.isFile() && /^(license|copyright|notice)/i.test(entry.name)).map(entry => entry.name).sort();
    const notices = await Promise.all(noticeFiles.map(async file => ({ file, text: await readFile(join(packageRoot, file), 'utf8') })));
    packages.set(name, { version: pkg.version, notices });
  }
  let legal = await readFile(join(scratch, names[1]), 'utf8');
  for (const [name, pkg] of [...packages].sort(([a], [b]) => a.localeCompare(b, 'en'))) {
    for (const notice of pkg.notices) legal += `\n\n===== ${name}@${pkg.version} ${notice.file} =====\n${notice.text.trimEnd()}\n`;
  }
  await writeFile(join(scratch, names[1]), legal);
  const dependencies = Object.fromEntries([...packages].sort(([a], [b]) => a.localeCompare(b, 'en')).map(([name, pkg]) => [name, pkg.version]));
  const inputs = await Promise.all(['build.mjs', 'firebase-entry.mjs', 'package-lock.json', 'package.json'].map(name => describe(join(client, name))));
  const outputs = await Promise.all(names.slice(0, 2).map(async name => ({ ...await describe(join(scratch, name)), path: `apps/api-go/workshop/${name}` })));
  const provenance = { schema: 'autodata.firebase-web.provenance', version: 1, sdk: { name: 'firebase', version: '12.19.0' }, dependencies, build: { tool: 'esbuild', version: esbuildVersion, options }, inputs, outputs, exports: expectedExports };
  await writeFile(join(scratch, names[2]), JSON.stringify(provenance, null, 2) + '\n');
}

const args = process.argv.slice(2);
if (args.length > 1 || (args.length === 1 && args[0] !== '--check')) throw new Error('Usage: node build.mjs [--check]');
const check = args[0] === '--check';
const scratch = await mkdtemp(join(tmpdir(), 'autodata-firebase-build-'));
try {
  await generate(scratch);
  if (!check) await mkdir(assets, { recursive: true });
  for (const name of names) {
    const generated = await readFile(join(scratch, name));
    if (check) {
      let committed;
      try { committed = await readFile(join(assets, name)); } catch { throw new Error(`Missing artifact: ${name}`); }
      if (!generated.equals(committed)) throw new Error(`Stale or altered artifact/input: ${name}`);
    } else await writeFile(join(assets, name), generated);
  }
  console.log(check ? 'Firebase artifacts match (3 files; checkout unchanged).' : 'Generated Firebase artifacts (3 files).');
} finally {
  await rm(scratch, { recursive: true, force: true });
}
