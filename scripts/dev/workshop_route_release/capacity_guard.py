"""Bounded complete allocation reads and owned-child failure handling."""
import pathlib,re,subprocess,time,os,signal
class AllocationReadError(RuntimeError):pass

def require_floor(free_bytes,free_inodes,floor):
    if free_bytes<=floor:raise RuntimeError('home_capacity_floor')
    if free_inodes<=1000:raise RuntimeError('home_inode_floor')

def allocated(path,*,runner=subprocess.run,sleeper=time.sleep,attempts=3):
    path=pathlib.Path(path)
    if not path.exists():return 0
    for attempt in range(attempts):
        result=runner(['/usr/bin/du','-sx','-B1',str(path)],capture_output=True,text=True,
                      timeout=10,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        if result.returncode==0:
            match=re.fullmatch(r'([0-9]+)\s+'+re.escape(str(path))+r'\n?',result.stdout)
            if not match or result.stderr:raise AllocationReadError('du_invalid_complete_result')
            return int(match[1])
        lines=result.stderr.splitlines()
        transient=result.returncode==1 and bool(lines)
        for line in lines:
            match=re.fullmatch(r"(?:/usr/bin/)?du: cannot access '([^']+)': No such file or directory",line)
            if not match:transient=False;break
            missing=pathlib.Path(match[1])
            if missing==path or not missing.is_relative_to(path) or missing.exists():transient=False;break
        # Partial stdout is NEVER accepted, even when its number looks in range.
        if not transient or attempt+1==attempts:raise AllocationReadError('du_incomplete_or_persistent_failure')
        sleeper(.025)
    raise AllocationReadError('du_retry_exhausted')

def wait_guarded(proc,guard,*,timeout,interval=.75):
    deadline=time.monotonic()+timeout
    try:
        while proc.poll() is None:
            guard()
            if time.monotonic()>=deadline:raise RuntimeError('child_deadline')
            time.sleep(min(interval,max(0,deadline-time.monotonic())))
        guard() # final floors/caps must also pass; child success alone is insufficient.
        if proc.returncode:raise RuntimeError('child_failed')
    except BaseException:
        if proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait(timeout=5)
        raise
