import os
import re
import sys
import glob
import shutil

class Action(object):
   def __init__(self, condition=None, invertCondition=False):
      super(Action, self).__init__()
      self.basedir = None
      self.verbose = False
      self.dryRun = False
      self.condition = condition
      self.invertCondition = invertCondition
   
   def setup(self, basedir, dryRun=False, verbose=False, **kwargs):
      self.basedir = basedir
      self.verbose = verbose
      self.dryRun = dryRun
      if self.condition:
         #if verbose:
         #   print("Evaluate condition: %s(%s)" % ("not " if self.invertCondition else "", self.condition))
         if self.invertCondition:
            rv = self.condition.isFalse(basedir)
         else:
            rv = self.contition.isTrue(basedir)
         #if verbose:
         #   print("=> %s" % rv)
         return rv
      else:
         return True
   
   def execute(self, arg):
      pass
   

class Condition(object):
   def __init__(self, **kwargs):
      super(Condition, self).__init__()
      self.args = kwargs

   def isTrue(self, basedir):
      return False

   def isFalse(self, basedir):
      return not self.isTrue(basedir)

   def __str__(self):
      return ""


class FileExists(Condition):
   PLAIN = 0
   GLOB_PATTERN = 1
   RE_PATTERN = 2

   def __init__(self, path, mode=0, **kwargs):
      super(FileExists, self).__init__(**kwargs)
      self.path = path
      self.mode = mode
      if self.mode == self.RE_PATTERN:
         self.exp = re.compile(self.path)

   def isTrue(self, basedir):
      d = basedir
      sd = self.args.get("subdir", None)
      if sd:
         d += "/" + sd
      if self.mode == self.PLAIN:
         return os.path.isfile(d + "/" + self.path)
      elif self.mode == self.GLOB_PATTERN:
         return (len(glob.glob(d + "/" + self.path)) > 0)
      elif self.mode == self.RE_PATTERN:
         items = filter(lambda x: self.exp.match(os.path.basename(x)) is not None, glob.glob(d + "/*"))
         return (len(items) > 0)
      else:
         return False

   def __str__(self):
      return "exists(%s)" % self.path


class And(Condition):
   def __init__(self, c0, c1, **kwargs):
      super(Condition, self).__init__(**kwargs)
      self.c0 = c0
      self.c1 = c1

   def isTrue(self, basedir):
      return (self.c0.isTrue(basedir) and self.c1.isTrue(basedir))

   def __str__(self):
      return "%s and %s" % (self.c0, self.c1)

class Or(Condition):
   def __init__(self, c0, c1, **kwargs):
      super(Condition, c0, c1).__init__(**kwargs)
      self.c0 = c0
      self.c1 = c1

   def isTrue(self, basedir):
      return (self.c0.isTrue(basedir) or self.c1.isTrue(basedir))

   def __str__(self):
      return "%s or %s" % (self.c0, self.c1)


class Delete(Action):
   CreatedDirs = set()
   
   def __init__(self, condition=None, invertCondition=False):
      super(Delete, self).__init__(condition, invertCondition)
      self.deletedir = None
   
   def setup(self, basedir, dryRun=False, verbose=False, **kwargs):
      if not super(Delete, self).setup(basedir, dryRun=dryRun, verbose=verbose, **kwargs):
         return False
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
      if not os.path.exists(arg):
         return
      if self.verbose:
         print("Move '%s' to '%s'" % (arg, self.deletedir))
      if not self.dryRun:
         shutil.move(arg, self.deletedir)
   

class Copy(Action):
   CreatedDirs = set()
   
   def __init__(self, todir, repl=[], condition=None, invertCondition=False):
      super(Copy, self).__init__(condition, invertCondition)
      self.todir = todir
      self.realtodir = None
      self.repl = repl
   
   def setup(self, basedir, dryRun=False, verbose=False, **kwargs):
      if not super(Copy, self).setup(basedir, dryRun=dryRun, verbose=verbose, **kwargs):
         return False
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
      if os.path.exists(self.realtodir + "/" + os.path.basename(arg)):
         return
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

KeepMakeTxCond = And(FileExists(r"^.*OpenColorIO.*\.(so|dll|dylib).*$", FileExists.RE_PATTERN, subdir="bin"),
                     FileExists(r"^.*synColor.*\.(so|dll|dylib).*$", FileExists.RE_PATTERN, subdir="bin"))

MtoA = {"bin": [(re.compile(r"^kick(\.exe)?$"), Delete()),
                (re.compile(r"^(lib)?ai\.(dll|so|dylib)$"), Delete()),
                (re.compile(r"^maketx(\.exe)?$"), Delete(condition=KeepMakeTxCond, invertCondition=True))],
        "scripts": [("arnold", Delete()),
                    ("pykick", Delete())],
        "shaders": [("*", Copy("../../../../../arnold/MtoAShaders/%s/%s/shaders", ["mtoaver", "platform"]))],
        "procedurals": [("*", Copy("../../../../../arnold/MtoAShaders/%s/%s/procedurals", ["mtoaver", "platform"]))]}

HtoA = {"scripts/bin": [(re.compile(r"^(py)?kick(\.exe)?$"), Delete()),
                        (re.compile(r"^(lib)?ai\.(dll|so|dylib)$"), Delete()),
                        (re.compile(r"^maketx(\.exe)?$"), Delete())],
        "scripts/python": [("arnold", Delete())],
        "arnold": [("plugins/*", Copy("../../../../../arnold/HtoAShaders/%s/%s/plugins", ["htoaver", "platform"])),
                   ("procedurals/*", Copy("../../../../../arnold/HtoAShaders/%s/%s/procedurals", ["htoaver", "platform"]))]}

if __name__ == "__main__":
   if "-h" in sys.argv or "--help" in sys.argv:
      print("Usage: python prepxtoa.py (-dr/--dry-run) (-v/--verbose) (-h/--help)")
      sys.exit(0)

   dryRun = ("-dr" in sys.argv or "--dry-run" in sys.argv)
   verbose = ("-v" in sys.argv or "--verbose" in sys.argv)
   
   thisdir = os.path.abspath(os.path.dirname(__file__))
   
   lst = [("/maya/MtoA/*", "mtoaver", "mayaver", "platform", MtoA), 
          ("/houdini/HtoA/*", "htoaver", "houver", "platform", HtoA)]
   
   for pattern, key1, key2, key3, aitems in lst:
      d = {}
      for dir1 in glob.glob(thisdir + pattern):
         d[key1] = os.path.basename(dir1)
         for dir2 in glob.glob(dir1 + "/*"):
            d[key2] = os.path.basename(dir2)
            if not re.match(r"[\d.]+", d[key2]):
               continue
            for dir3 in glob.glob(dir2 + "/*"):
               d[key3] = os.path.basename(dir3)
               if not d[key3] in ("darwin", "windows", "linux"):
                  continue
               for k, v in aitems.iteritems():
                  tgt = dir3 + "/" + k
                  if not os.path.isdir(tgt):
                     continue
                  contents = glob.glob(tgt + "/*")
                  for nameOrExp, action in v:
                     if not action.setup(dir3, dryRun=dryRun, verbose=verbose, **d):
                        continue
                     if type(nameOrExp) in (str, unicode):
                        for item in glob.glob(tgt + "/" + nameOrExp):
                           action.execute(item)
                     else:
                        for item in filter(lambda x: nameOrExp.match(os.path.basename(x)), contents):
                           action.execute(item)
