"""Owned temporary-file and local worker tests; no host observations."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from unittest.mock import patch
from test_policy import load

a=load('real_admission'); f=load('file_transport')


def identity(st):
    return a.FileIdentity(st.st_dev,st.st_ino,st.st_uid,st.st_gid,st.st_mode,st.st_size,
                          st.st_mtime_ns,st.st_ctime_ns,st.st_nlink)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.leaf=self.root/'input';self.leaf.write_bytes(b'owned input');self.leaf.chmod(0o600)
        self.rootfd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        self.anchor=a.Anchor('root',self.rootfd,identity(os.fstat(self.rootfd)))
        self.recipe=a.FileRecipe('input','root',('input',),'regular',identity(self.leaf.stat()),
            (self.anchor.identity,),hashlib.sha256(b'owned input').hexdigest(),None)
        self.cancel=threading.Event();self.workers=[]

    def tearDown(self):
        for w in self.workers:w.close()
        os.close(self.rootfd);self.tmp.cleanup()

    def worker(self,recipes=None):
        self.cancel=threading.Event()  # Each worker is a separate owned test attempt.
        w=f.FileWorker((self.anchor,),tuple(recipes or (self.recipe,)), 'root',
                       time.monotonic_ns()+10*10**9,self.cancel)
        self.workers.append(w);return w

    def test_hash_regular_and_retire(self):
        w=self.worker();r=w.observe('input')
        self.assertEqual(r['sha256'],self.recipe.sha256);self.assertTrue(r['complete'])
        self.assertEqual(w.close(),'reaped');self.assertTrue(w.ipc_closed)
        self.assertEqual(w.close(),'reaped')

    def test_symlink_special_leaf_and_wrong_identity(self):
        for kind in ('symlink','fifo','socket','identity','nlink','mode'):
            with self.subTest(kind=kind):
                if self.leaf.exists() or self.leaf.is_symlink():self.leaf.unlink()
                owned_socket=None
                if kind=='symlink': self.leaf.symlink_to('/not-read')
                elif kind=='fifo':os.mkfifo(self.leaf,0o600)
                elif kind=='socket':
                    owned_socket=socket.socket(socket.AF_UNIX);owned_socket.bind(str(self.leaf))
                else:
                    self.leaf.write_bytes(b'owned input');self.leaf.chmod(0o600)
                    if kind=='nlink':os.link(self.leaf,self.root/'hardlink')
                    if kind=='mode':self.leaf.chmod(0o666)
                anchor=replace(self.anchor,identity=identity(os.fstat(self.rootfd)))
                with patch.object(self,'anchor',anchor):
                    w=self.worker();self.assertRaises(f.TransportFault,w.observe,'input');self.assertEqual(w.close(),'reaped')
                if owned_socket:owned_socket.close()
                if (self.root/'hardlink').exists():(self.root/'hardlink').unlink()

    def test_absence_only_enoent_then_creation_is_integrity_fault(self):
        recipe=a.FileRecipe('absent','root',('absent',),'absence',None,(self.anchor.identity,),None,None)
        w=self.worker((recipe,));self.assertEqual(w.observe('absent'),{'absent':True})
        (self.root/'absent').write_bytes(b'collision')
        self.assertRaises(f.TransportFault,w.observe,'absent')

    def test_exclusive_output_has_real_metadata_and_complete_hash(self):
        w=self.worker();raw=b'output'*20000
        result=w.create_output('REPORT.md',raw)
        self.assertEqual((self.root/'REPORT.md').read_bytes(),raw)
        self.assertEqual((self.root/'REPORT.md').stat().st_mode&0o777,0o600)
        self.assertEqual(result['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(w.verify_output('REPORT.md'),result)
        self.assertRaises(f.TransportFault,w.create_output,'REPORT.md',b'replace')
        self.assertEqual((self.root/'REPORT.md').read_bytes(),raw)

    def test_forbidden_names_owner_inputs_and_reviewer_are_never_created(self):
        for name in ('../escape','extra.json','owner-contract.json','dispatch.json','independent-review.md'):
            w=self.worker();self.assertRaises(f.TransportFault,w.create_output,name,b'private')
            self.assertEqual(w.close(),'reaped')
        self.assertFalse((self.root/'extra.json').exists())

    def test_output_symlink_collision_no_overwrite(self):
        (self.root/'REPORT.md').symlink_to(self.leaf)
        self.anchor=replace(self.anchor,identity=identity(os.fstat(self.rootfd)))
        w=self.worker();self.assertRaises(f.TransportFault,w.create_output,'REPORT.md',b'bad')
        self.assertEqual(self.leaf.read_bytes(),b'owned input')

    def test_output_inventory_detects_unexpected_file(self):
        w=self.worker();self.assertRaises(f.TransportFault,w.inventory_outputs,())

    def test_cancel_and_expiry_latch_no_further_operation(self):
        w=self.worker();self.cancel.set();self.assertRaises(f.TransportFault,w.observe,'input')
        self.cancel.clear();self.assertRaises(f.TransportFault,w.observe,'input')
        self.assertEqual(w.close(),'reaped')

    def test_stalled_worker_is_bounded_and_reaped(self):
        def stalled(*args): time.sleep(20)
        start=time.monotonic()
        with patch.object(f,'_observe',stalled):
            w=self.worker();self.assertRaises(f.TransportFault,w.observe,'input')
        self.assertLess(time.monotonic()-start,10)
        self.assertEqual(w.close(),'reaped')

    def test_unconfirmed_cleanup_is_explicit_and_quarantines(self):
        w=self.worker()
        with patch.object(f.os,'waitid',side_effect=OSError()):
            self.assertEqual(w.close(),'unconfirmed')
        self.assertTrue(w.quarantine_required)
        # Test owns this child and repairs its own injected observation failure.
        os.waitpid(w._pid,0)

    def test_ordinary_sigchld_and_single_thread_requirement(self):
        with patch.object(f.signal,'getsignal',return_value=signal.SIG_IGN):
            self.assertRaises(f.TransportFault,self.worker)
        with patch.object(f.threading,'active_count',return_value=2):
            self.assertRaises(f.TransportFault,self.worker)

    def test_partial_write_and_eintr_resume_one_descriptor(self):
        original=os.write;calls=[0]
        def partial(fd,data):
            calls[0]+=1
            if calls[0]==1:raise InterruptedError()
            return original(fd,data[:7])
        with patch.object(f.os,'write',side_effect=partial):
            w=self.worker();result=w.create_output('REPORT.md',b'partial data'*100)
        self.assertTrue(result['complete']);self.assertEqual((self.root/'REPORT.md').read_bytes(),b'partial data'*100)

    def test_fsync_and_enospc_failures_latch_without_rewrite(self):
        import errno
        for operation,code in (('fsync',errno.EIO),('write',errno.ENOSPC)):
            with self.subTest(operation=operation):
                if (self.root/'REPORT.md').exists():(self.root/'REPORT.md').unlink()
                self.anchor=replace(self.anchor,identity=identity(os.fstat(self.rootfd)))
                with patch.object(f.os,operation,side_effect=OSError(code,'private sentinel')):
                    w=self.worker();self.assertRaises(f.TransportFault,w.create_output,'REPORT.md',b'owned')
                self.assertRaises(f.TransportFault,w.create_output,'classification.json',b'new')
                self.assertFalse((self.root/'classification.json').exists())
                self.assertNotIn('private sentinel',str(w._fault))

    def test_same_inode_change_and_output_substitution(self):
        w=self.worker();w.create_output('REPORT.md',b'first')
        (self.root/'REPORT.md').write_bytes(b'other')
        self.assertRaises(f.TransportFault,w.verify_output,'REPORT.md')

    def test_input_hash_and_size_change_after_admission(self):
        self.leaf.write_bytes(b'different')
        self.anchor=replace(self.anchor,identity=identity(os.fstat(self.rootfd)))
        w=self.worker();self.assertRaises(f.TransportFault,w.observe,'input')

    def test_symlink_parent_never_traversed(self):
        directory=self.root/'nested';directory.mkdir(mode=0o700)
        leaf=directory/'data';leaf.write_bytes(b'owned');leaf.chmod(0o600)
        self.anchor=replace(self.anchor,identity=identity(os.fstat(self.rootfd)))
        recipe=a.FileRecipe('nested','root',('nested','data'),'regular',identity(leaf.stat()),
             (self.anchor.identity,identity(directory.stat())),hashlib.sha256(b'owned').hexdigest(),None)
        w=self.worker((recipe,));leaf.unlink();directory.rmdir();directory.symlink_to('/not-traversed')
        self.assertRaises(f.TransportFault,w.observe,'nested')

    def test_protocol_rejects_length_sequence_and_truncation(self):
        for header,body in ((f._HEADER.pack(1,2,1,65537),b''),
                            (f._HEADER.pack(1,2,2,2),b'{}'),
                            (f._HEADER.pack(1,2,1,5),b'{}')):
            left,right=socket.socketpair();left.setblocking(False)
            try:
                right.sendall(header+body);right.close()
                self.assertRaises(f.TransportFault,f._receive,left,2,1,time.monotonic_ns()+10**9,threading.Event())
            finally:left.close();right.close()
