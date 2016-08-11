import os
import re
import sys
import glob
import shutil

class Action(object):
   def __init__(self):
      super(Action, self).__init__()
      self.basedir = None
      self.verbose = False
      self.dryRun = False
   
   def setup(self, basedir, dryRun=False, verbose=False, **kwargs):
      self.basedir = basedir
      self.verbose = verbose
      self.dryRun = dryRun
      return True
   
   def execute(self, arg):
      pass
   

class Delete(Action):
   CreatedDirs = set()
   
   def __init__(self):
      super(Delete, self).__init__()
      self.deletedir = None
   
   def setup(self, basedir, dryRun=False, verbose=False, **kwargs):
      super(Delete, self).setup(basedir, dryRun=dryRun, verbose=verbose, **kwargs)
      self.deletedir = basedir + "/_deleted"
      if not os.path.isdir(self.deletedir):
         if verbose:
            if not dryRun or self.deletedir not in self.CreatedDirs:
               print("Create directory '%s'" % self.deletedir)
               self.CreatedDirs.add(self.deletedir)
         if not dryRun:
            try:
               os.makedirs(self.deletedir)
            except Exception, e:
               print("ERROR: %s" % e)
               return False
      return True
   
   def execute(self, arg):
      if self.verbose:
         print("Move '%s' to '%s'" % (arg, self.deletedir))
      if not self.dryRun:
         shutil.move(arg, self.deletedir)
   

class Copy(Action):
   CreatedDirs = set()
   
   def __init__(self, todir, repl=[]):
      super(Copy, self).__init__()
      self.todir = todir
      self.realtodir = None
      self.repl = repl
   
   def setup(self, basedir, dryRun=False, verbose=False, **kwargs):
      super(Copy, self).setup(basedir, dryRun=dryRun, verbose=verbose, **kwargs)
      if not os.path.isabs(self.todir):
         self.realtodir = basedir + "/" + self.todir
      else:
         self.realtodir = self.todir
      if self.repl:
         args = tuple([kwargs[x] for x in self.repl])
         self.realtodir = self.realtodir % args
      if not os.path.isdir(self.realtodir):
         if verbose:
            if not dryRun or self.realtodir not in self.CreatedDirs:
               print("Create directory '%s'" % self.realtodir)
               self.CreatedDirs.add(self.realtodir)
         if not dryRun:
            try:
               os.makedirs(self.realtodir)
            except Exception, e:
               print("ERROR: %s" % e)
               return False
      return True
   
   def execute(self, arg):
      if self.verbose:
         print("Copy '%s' to '%s'" % (arg, self.realtodir))
      if not self.dryRun:
         try:
            if os.path.isdir(arg):
               shutil.copytree(arg, self.realtodir)
            else:
               shutil.copy2(arg, self.realtodir)
         except Exception, e:
            if self.verbose:
               print("FAILED: %s" % e)

MtoA = {"bin": [(re.compile(r"^kick(\.exe)?$"), Delete()),
                (re.compile(r"^(lib)?ai\.(dll|so|dylib)$"), Delete()),
                (re.compile(r"^maketx(\.exe)?$"), Delete())],
        "scripts": [("arnold", Delete()),
                    ("pykick", Delete())],
        "shaders": [("*", Copy("../../../../arnold/MtoAShaders/%s/shaders", ["mtoaver"]))],
        "procedurals": [("*", Copy("../../../../arnold/MtoAShaders/%s/procedurals", ["mtoaver"]))]}

HtoA = {"scripts/bin": [(re.compile(r"^(py)?kick(\.exe)?$"), Delete()),
                        (re.compile(r"^(lib)?ai\.(dll|so|dylib)$"), Delete()),
                        (re.compile(r"^maketx(\.exe)?$"), Delete())],
        "scripts/python": [("arnold", Delete())],
        "arnold": [("plugins/*", Copy("../../../../arnold/HtoAShaders/%s/plugins", ["htoaver"])),
                   ("procedurals/*", Copy("../../../../arnold/HtoAShaders/%s/procedurals", ["htoaver"]))]}

if __name__ == "__main__":
   dryRun = ("-dr" in sys.argv or "--dry-run" in sys.argv)
   verbose = ("-v" in sys.argv or "--verbose" in sys.argv)
   
   thisdir = os.path.abspath(os.path.dirname(__file__))
   
   lst = [("/maya/MtoA/*", "mtoaver", "mayaver", MtoA), 
          ("/houdini/HtoA/*", "htoaver", "houver", HtoA)]
   
   for pattern, key1, key2, aitems in lst:
      d = {}
      for dir1 in glob.glob(thisdir + pattern):
         d[key1] = os.path.basename(dir1)
         for dir2 in glob.glob(dir1 + "/*"):
            d[key2] = os.path.basename(dir2)
            if not re.match(r"[\d.]+", d[key2]):
               continue
            for k, v in aitems.iteritems():
               tgt = dir2 + "/" + k
               if not os.path.isdir(tgt):
                  continue
               contents = glob.glob(tgt + "/*")
               for nameOrExp, action in v:
                  action.setup(dir2, dryRun=dryRun, verbose=verbose, **d)
                  if type(nameOrExp) in (str, unicode):
                     for item in glob.glob(tgt + "/" + nameOrExp):
                        action.execute(item)
                  else:
                     for item in filter(lambda x: nameOrExp.match(os.path.basename(x)), contents):
                        action.execute(item)
