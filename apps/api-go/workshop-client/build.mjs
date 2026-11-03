// Build-only tooling; never imported by the Workshop or production Go runtime.
import { build, version as esbuildVersion } from 'esbuild';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, writeFile, mkdir, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// Official Apache-2.0 text is embedded so builds never fetch license material.
// Source bytes are pinned and independently checked by the served-asset Go test.
const apacheLicense = {
  id: 'Apache-2.0',
  source: 'https://www.apache.org/licenses/LICENSE-2.0.txt',
  sha256: 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30',
  bytes: 11358,
};
const apacheLicenseText = String.raw`
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
`;

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
  if (Buffer.byteLength(apacheLicenseText) !== apacheLicense.bytes || digest(apacheLicenseText) !== apacheLicense.sha256) throw new Error('Pinned Apache-2.0 text integrity mismatch');
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
  legal += `\n\n===== Apache-2.0 full license =====\n${apacheLicenseText}===== End Apache-2.0 full license =====\n`;
  for (const [name, pkg] of [...packages].sort(([a], [b]) => a.localeCompare(b, 'en'))) {
    for (const notice of pkg.notices) legal += `\n\n===== ${name}@${pkg.version} ${notice.file} =====\n${notice.text.trimEnd()}\n`;
  }
  await writeFile(join(scratch, names[1]), legal);
  const dependencies = Object.fromEntries([...packages].sort(([a], [b]) => a.localeCompare(b, 'en')).map(([name, pkg]) => [name, pkg.version]));
  const inputs = await Promise.all(['build.mjs', 'firebase-entry.mjs', 'package-lock.json', 'package.json'].map(name => describe(join(client, name))));
  const outputs = await Promise.all(names.slice(0, 2).map(async name => ({ ...await describe(join(scratch, name)), path: `apps/api-go/workshop/${name}` })));
  const provenance = { schema: 'autodata.firebase-web.provenance', version: 1, sdk: { name: 'firebase', version: '12.19.0' }, dependencies, build: { tool: 'esbuild', version: esbuildVersion, options }, inputs, outputs, exports: expectedExports, licenses: [apacheLicense] };
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
