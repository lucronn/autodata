/** Build-time inventory only. Its output requires independent owner acceptance. */
import {createHash} from 'node:crypto';
import {lstat,readdir,readFile,writeFile,chmod,unlink} from 'node:fs/promises';
import path from 'node:path';
const require=value=>{if(!value)throw Error('invalid_toolkit_tree');};
const hash=raw=>createHash('sha256').update(raw).digest('hex');
const canonical=value=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':value!==null&&typeof value==='object'?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}':JSON.stringify(value);
try {
 require(process.argv.length===2);
 async function replace(filename,data,mode){try{const st=await lstat(filename);require(st.isFile() && st.nlink===1 && st.uid===process.getuid());await unlink(filename);}catch(e){if(e.code!=='ENOENT')throw e;}await writeFile(filename,data,{mode,flag:'wx'});}
 const root=process.cwd(),lockBytes=await readFile(path.join(root,'package-lock.json'));
 require(lockBytes.length<=1024*1024);
 const lock=JSON.parse(lockBytes),packages=Object.create(null),inventory=[];
 require(lock.packages && typeof lock.packages==='object');
 for(const [name,pkg] of Object.entries(lock.packages)){
  if(!name)continue;
  require(/^node_modules\//.test(name) && !name.split('/').some(p=>!p || p==='.' || p==='..') && !name.includes('\\'));
  require(typeof pkg.version==='string' && /^https:\/\/registry\.npmjs\.org\/[^?#]+$/.test(pkg.resolved) && /^sha512-[A-Za-z0-9+/]+=*$/.test(pkg.integrity) && !pkg.hasInstallScript);
  packages[name]={version:pkg.version,resolved:pkg.resolved,integrity:pkg.integrity};
  const installed=JSON.parse(await readFile(path.join(root,name,'package.json')));
  require(installed.name===(pkg.name??name.split('node_modules/').at(-1)) && installed.version===pkg.version);
  inventory.push({name:installed.name,version:installed.version,license:installed.license??null,lock_path:name});
 }
 // Preserve license values, including absent/unknown licenses, for an independent
 // reviewer. This file never declares vulnerabilities or licenses accepted.
 await replace(path.join(root,'dependency-inventory.json'),canonical({protocol_version:1,packages:inventory.sort((a,b)=>a.lock_path<b.lock_path?-1:1)}),0o600);
 const files=[],dirs=[];let total=0;
 async function walk(rel){
  const at=path.join(root,rel),directory=await lstat(at);require(directory.isDirectory() && !directory.isSymbolicLink() && directory.uid===process.getuid());dirs.push(at);
  for(const name of (await readdir(at)).sort()){
   require(!/[\\\x00-\x20\x7f]/.test(name));const next=rel?rel+'/'+name:name;
   if(next==='installed-tree.json')continue;
   const file=path.join(root,next),st=await lstat(file);
   if(st.isDirectory()){await walk(next);continue;}
   require(st.isFile() && st.nlink===1 && st.uid===process.getuid() && st.size<=64*1024*1024 && !(st.mode&0o7000));
   const raw=await readFile(file);require(raw.length===st.size);total+=raw.length;require(total<=1024*1024*1024 && files.length<50000);
   const mode=(st.mode&0o111)?0o555:0o444;await chmod(file,mode);
   files.push({path:next,bytes:raw.length,sha256:hash(raw),mode});
  }
 }
 await walk('');files.sort((a,b)=>a.path<b.path?-1:1);
 const manifest=canonical({protocol_version:1,toolkit_lock_sha256:hash(lockBytes),packages,files});require(Buffer.byteLength(manifest)<=8*1024*1024);
 const target=path.join(root,'installed-tree.json');
 try{const st=await lstat(target);require(st.isFile() && st.nlink===1 && st.uid===process.getuid());await unlink(target);}catch(e){if(e.code!=='ENOENT')throw e;}
 await writeFile(target,manifest,{mode:0o444,flag:'wx'});
 for(const dir of dirs.reverse())await chmod(dir,0o555);
} catch {process.stderr.write('invalid_toolkit_tree\n');process.exitCode=2;}
