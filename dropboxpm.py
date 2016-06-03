import os
import re
import sys
import json
import glob
import shutil
import tarfile
import zipfile
import platform
from urllib2 import urlopen, URLError, HTTPError


url_prefix = "https://www.dropbox.com/s/"
url_suffix = "?dl=1"

def dropbox_download_url(url):
    return url_prefix + url + url_suffix

def download(url, outdir, outname=None):
    try:
        u = urlopen(url)
        print("Downloading %s" % url)
        
        if outname is None:
            outname = os.path.basename(url.split("?")[0])
        
        outpath = outdir + "/" + outname
        
        with open(outpath, "wb") as f:
            f.write(u.read())
        
        return outpath
    
    except HTTPError, e:
        print("HTTP Error: %s %s" % (e.code, url))
        return None
    
    except URLError, e:
        print("URL Error: %s %s" % (e.reason, url))
        return None
    
    except Exception, e:
        print("Unexpected error: %s" % e)
        return None

def list_packages(index):
    tools = index.keys()
    tools.sort()
    for toolname in tools:
        d0 = index[toolname]
        category = d0.get("category", "")
        if category:
            print("%s [%s]" % (toolname, category))
        else:
            print(toolname)
        versions = d0.get("versions", {}).keys()
        versions.sort(reverse=True)
        for version in versions:
            d1 = d0["versions"][version]
            plats = d1.keys()
            if len(plats) == 0:
                continue
            cmndeps = {}
            cmnenv = None
            if "common" in plats:
                cmndeps = d1["common"].get("dependencies", {})
                cmnenv = d1["common"].get("environment", None)
                plats.remove("common")
            print("  %s" % version)
            if len(plats) != 0:
                print("    Availibility: %s" % ", ".join(plats))
            else:
                print("    Availibility: any")
            if len(cmndeps) > 0:
                print("    Dependencies: %s" % (", ".join(map(lambda x: "%s %s" % x, cmndeps.items()))))
            if cmnenv is not None:
                print("    Environment: %s" % os.path.basename(cmnenv))
            for plat in plats:
                deps = d1[plat].get("dependencies", {})
                if len(deps) > 0:
                    print("    %s dependencies: %s" % (plat, ", ".join(map(lambda x: "%s %s" % x, deps.items()))))
                env = d1[plat].get("environment", None)
                if env is not None:
                    print("    %s environment: %s" % (plat, os.path.basename(env)))

def list_installed(index, outdir, env=False):
    plat = platform.system().lower()
    
    rv = set()
    
    if env:
        envtopkg = {}
        
        for name, v in index.iteritems():
            category = v.get("category", "")
            versions = v.get("versions", {})
            for version, info in versions.iteritems():
                url = info.get(plat, {}).get("environment", None)
                if url is None:
                    url = info.get("common", {}).get("environment", None)
                if url is not None:
                    bn = os.path.basename(url)
                    lst = envtopkg.get(bn, [])
                    lst.append((name, version))
                    envtopkg[bn] = lst
        
        for item in glob.glob(outdir + "/downloads/*.env"):
            bn = os.path.basename(item)
            if bn in envtopkg:
                for name, version in envtopkg[bn]:
                    category = index[name].get("category", "")
                    prefix = ("/%s" % category if category else "")
                    envfile = outdir + prefix + "/" + bn
                    if os.path.isfile(envfile):
                        rv.add((name, version))
    
    else:
        names = index.keys()
        names.sort(key=lambda x: len(x), reverse=True)
        
        for item in glob.glob(outdir + "/downloads/*.tgz"):
            bn = os.path.splitext(os.path.basename(item))[0]
            for name in names:
                if bn.startswith(name):
                    category = index[name].get("category", "")
                    installname = index[name].get("installname", name)
                    version = re.sub(r"_(darwin|windows|linux|common)$", "", bn.replace(name, ""))
                    prefix = ("/%s" % category if category else "")
                    verinfo = index[name].get("versions", {}).get(version, {})
                    checklist = verinfo.get(plat, {}).get("checklist", []) + verinfo.get("common", {}).get("checklist", [])
                    foundall = True
                    topdir = outdir + prefix + "/" + installname + "/" + version + "/" + plat
                    if len(checklist) == 0:
                        checklist.append(topdir)
                    for entry in checklist:
                        if not os.path.exists(topdir + "/" + entry):
                            foundall = False
                            break
                    if foundall:
                        rv.add((name, version))
                    break
    
    rv = list(rv)
    rv.sort()
    
    return rv

def list_installed_packages(index, outdir, indent=""):
    for name, version in list_installed(index, outdir, env=False):
        print("%s%s %s" % (indent, name, version))

def list_installed_environments(index, outdir, indent=""):
    for name, version in list_installed(index, outdir, env=True):
        print("%s%s %s" % (indent, name, version))

def list_tar(path):
    try:
        with tarfile.open(path, "r") as t:
            return [x.name for x in filter(lambda x: not os.path.basename(x.name).startswith("._"), t.getmembers())]
    except Exception, e:
        print("Failed to list %s (%s)." % (path, e))
        return []

def extract_tar(path, outdir, verbose=False):
    try:
        if verbose:
            print("Extracting %s..." % path)
        with tarfile.open(path, "r") as t:
            members = filter(lambda x: not os.path.basename(x.name).startswith("._"), t.getmembers())
            t.extractall(outdir, members=members)
    except Exception, e:
        print("Failed to extract %s (%s)." % (path, e))

def list_zip(path):
    raise Exception("Not Yet Implemented.")

def extract_zip(path, outdir, verbose=False):
    raise Exception("Not Yet Implemented.")

def build_package_urls(index, packages, outdir, ignoredeps=False, verbose=False):
    names = index.keys()
    names.sort(key=lambda x: len(x), reverse=True)
    
    plat = platform.system().lower()
    urls = {}
    
    n = len(packages)
    i = 0
    
    while i < n:
        package = packages[i]
        
        if package in index:
            # No version specified
            vers = []
            for ver, verinfo in index[package].get("versions", {}).iteritems():
                valid = False
                if plat in verinfo:
                    pkg = verinfo[plat].get("package", None)
                    if pkg is not None:
                        valid = True
                if not valid and "common" in verinfo:
                    pkg = verinfo["common"].get("package", None)
                    if pkg is not None:
                        valid = True
                
                if valid:
                    vers.append(ver)
            
            if len(vers) > 0:
                vers.sort(reverse=True)
                if verbose:
                    print("Use version %s for %s (latest)." % (vers[0], package))
                packages[i] = "%s%s" % (package, vers[0])
                continue
            
            else:
                print("%s is not available for %s." % (package, plat))
        
        else:
            found = False
            
            for name in names:
                if package.startswith(name):
                    version = package.replace(name, "")
                    category = index[name].get("category", "")
                    versions = index[name].get("versions", {})
                    if version in versions:
                        verinfo = versions[version]
                        
                        deps = {}
                        if not ignoredeps:
                            deps = verinfo.get("common", {}).get("dependencies", {})
                            deps.update(verinfo.get(plat, {}).get("dependencies", {}))
                        
                        pkgurls = []
                        pkgurl = verinfo.get("common", {}).get("package", None)
                        if pkgurl is not None:
                            pkgurls.append("%s/%s%s_common.tgz" % (pkgurl, name, version))
                        pkgurl = verinfo.get(plat, {}).get("package", None)
                        if pkgurl is not None:
                            pkgurls.append("%s/%s%s_%s.tgz" % (pkgurl, name, version, plat))
                        
                        if len(pkgurls) > 0:
                            for depname, depver in deps.iteritems():
                                depkey = "%s%s" % (depname, depver)
                                if depname in packages:
                                    # already specified without version but not yet processed
                                    # (would have been replaced)
                                    if verbose:
                                        print("Use version %s for %s (fix by dependency)." % (depver, depname))
                                    idx = packages.index(name)
                                    packages[idx] = depkey
                                    continue
                                elif depkey in packages:
                                    if verbose:
                                        print("%s %s dependency %s %s already required." % (name, version, depname, depver))
                                else:
                                    if verbose:
                                        print("Add %s %s dependency: %s %s." % (name, version, depname, depver))
                                    packages.append(depkey)
                                    n = len(packages)
                            urls[(name, version)] = (category, map(dropbox_download_url, pkgurls))
                            found = True
                    break
            
            if not found:
                print("%s not found" % package)
        i += 1
    
    return urls

def install_packages(index, packages, outdir, ignoredeps=False, force=False, verbose=False):
    urls = build_package_urls(index, packages, outdir, ignoredeps, verbose)
    
    plat = platform.system().lower()
    
    downloaddir = outdir + "/downloads"
    if not os.path.isdir(downloaddir):
        os.makedirs(downloaddir)
    
    for k, v in urls.iteritems():
        name, version = k
        category, urll = v
        installname = index[name].get("installname", name)
        
        prefix = ("/%s" % category if category else "")
        prefix += "/" + installname + "/" + version + "/" + plat
        
        for url in urll:
            targetname = os.path.basename(url.split("?")[0])
            targetpath = downloaddir + "/" + targetname
            dl = True
            
            if not force:
                foundall = True
                
                verinfo = index[name].get("versions", {}).get(version, {})
                checklist = verinfo.get("common", {}).get("checklist", []) + verinfo.get(plat, {}).get("checklist", [])
                
                for entry in checklist:
                    if not os.path.exists(outdir + prefix + "/" + entry):
                        foundall = False
                        break
                
                if foundall:
                    if verbose:
                        print("%s %s already installed." % (name, version))
                    continue
                
                if os.path.isfile(targetpath) and os.stat(targetpath).st_size > 0:
                    if verbose:
                        print("%s %s already downloaded." % (name, version))
                    dl = False
            
            if dl:
                path = download(url, downloaddir)
            else:
                path = targetpath
            
            extract = None
            ext = os.path.splitext(path)[1]
            if ext == ".tgz":
                extract = extract_tar
            elif ext == ".zip":
                extract = extract_zip
            elif ext == ".gz":
                ext = os.path.splitext(os.path.splitext(path)[0])[1]
                if ext == ".tar":
                    extract = extract_tar
            
            if extract is None:
                print("Cannot install %s (unsupported package format)." % path)
            else:
                print("Install %s %s to %s%s" % (name, version, outdir, prefix))
                extract(path, outdir + prefix, verbose=verbose)

def uninstall_packages(index, packages, outdir, ignoredeps=False, force=False, verbose=False):
    urls = build_package_urls(index, packages, outdir, ignoredeps, verbose)
    
    plat = platform.system().lower()
    
    # when including dependencies, keep packages to be removed that are
    # required by other installed packages not to be uninstalled
    if not force:
        for pkgname, pkgver in list_installed(index, outdir):
            pkginfo = index[pkgname]
            verinfo = pkginfo["versions"][pkgver]
            uninstall = False
            
            for k, v in urls.iteritems():
                name, version = k
                if name == pkgname:
                    uninstall = (version == pkgver)
                    break
            
            if not uninstall:
                deps = verinfo.get("common", {}).get("dependencies", {})
                deps.update(verinfo.get(plat, {}).get("dependencies", {}))
                for depname, depver in deps.iteritems():
                    if (depname, depver) in urls:
                        print("Remove %s %s from uninstall list as it is required for %s %s" % (depname, depver, pkgname, pkgver))
                        print("  (use -f/--force to ignore this check at your own risk)")
                        del(urls[(depname, depver)])
    
    if len(urls) == 0:
        print("Nothing to uninstall")
        return
    
    downloaddir = outdir + "/downloads"
    if not os.path.isdir(downloaddir):
        return
    
    for k, v in urls.iteritems():
        name, version = k
        installname = index[name].get("installname", name)
        category, urll = v
        
        prefix = ("/%s" % category if category else "")
        prefix += "/" + installname + "/" + version + "/" + plat
        
        print("Uninstall %s %s from %s%s" % (name, version, outdir, prefix))
        
        for url in urll:
            targetname = os.path.basename(url.split("?")[0])
            targetpath = downloaddir + "/" + targetname
            
            for f in list_tar(targetpath):
                installedfile = outdir + prefix + "/" + f
                if os.path.isdir(installedfile):
                    shutil.rmtree(installedfile)
                elif os.path.isfile(installedfile):
                    os.remove(installedfile)
            
            # TODO
            #   if outdir + prefix is empty, remove
            #   recursively up to outdir it self

def build_environment_urls(index, packages, ignoredeps=False, verbose=False):
    names = index.keys()
    names.sort(key=lambda x: len(x), reverse=True)
    
    plat = platform.system().lower()
    urls = {}
    
    n = len(packages)
    i = 0
    
    while i < n:
        package = packages[i]
        
        if package in index:
            # No version specified
            vers = []
            for ver, verinfo in index[package].get("versions", {}).iteritems():
                valid = False
                if plat in verinfo:
                    env = verinfo[plat].get("environment", None)
                    if env is not None:
                        valid = True
                if not valid and "common" in verinfo:
                    env = verinfo["common"].get("environment", None)
                    if env is not None:
                        valid = True
                
                if valid:
                    vers.append(ver)
            
            if len(vers) > 0:
                vers.sort(reverse=True)
                if verbose:
                    print("Use version %s for %s (latest)." % (vers[0], package))
                packages[i] = "%s%s" % (package, vers[0])
                continue
            
            else:
                print("%s is not available for %s." % (package, plat))
        
        else:
            found = False
            
            for name in names:
                if package.startswith(name):
                    version = package.replace(name, "")
                    category = index[name].get("category", "")
                    versions = index[name].get("versions", {})
                    if version in versions:
                        verinfo = versions[version]
                        
                        deps = {}
                        if not ignoredeps:
                            deps = verinfo.get("common", {}).get("dependencies", {})
                            deps.update(verinfo.get(plat, {}).get("dependencies", {}))
                        
                        envurl = verinfo.get(plat, {}).get("environment", None)
                        if envurl is None:
                            envurl = verinfo.get("common", {}).get("environment", None)
                        
                        if envurl is not None:
                            for depname, depver in deps.iteritems():
                                depkey = "%s%s" % (depname, depver)
                                if depname in packages:
                                    # already specified without version but not yet processed
                                    # (would have been replaced)
                                    if verbose:
                                        print("Use version %s for %s (fix by dependency)." % (depver, depname))
                                    idx = packages.index(name)
                                    packages[idx] = depkey
                                    continue
                                elif depkey in packages:
                                    if verbose:
                                        print("%s %s dependency %s %s already required." % (name, version, depname, depver))
                                else:
                                    if verbose:
                                        print("Add %s %s dependency: %s %s." % (name, version, depname, depver))
                                    packages.append(depkey)
                                    n = len(packages)
                            urls[(name, version)] = (category, dropbox_download_url(envurl))
                            found = True
                    break
            
            if not found:
                print("%s not found" % package)
        i += 1
    
    return urls

def install_environments(index, packages, outdir, ignoredeps=False, force=False, verbose=False):
    urls = build_environment_urls(index, packages, ignoredeps, verbose)
    
    downloaddir = outdir + "/downloads"
    if not os.path.isdir(downloaddir):
        os.makedirs(downloaddir)
    
    for k, v in urls.iteritems():
        name, version = k
        category, url = v
        
        prefix = ("/%s" % category if category else "")
        
        targetname = os.path.basename(url.split("?")[0])
        targetpath = downloaddir + "/" + targetname
        outenv = outdir + prefix + "/" + targetname
        dl = True
            
        if not force:
            if os.path.exists(outenv) and os.stat(outenv).st_size > 0:
                if verbose:
                    print("%s %s already installed." % (name, version))
                continue
            
            if os.path.isfile(targetpath) and os.stat(targetpath).st_size > 0:
                if verbose:
                    print("%s %s already downloaded." % (name, version))
                dl = False
        
        if dl:
            path = download(url, downloaddir)
        else:
            path = targetpath
        
        shutil.copy(targetpath, outenv)

def uninstall_environments(index, packages, outdir, ignoredeps=False, force=False, verbose=False):
    urls = build_environment_urls(index, packages, ignoredeps, verbose)
    
    plat = platform.system().lower()
    
    # when including dependencies, keep packages to be removed that are
    # required by other installed packages not to be uninstalled
    if not force:
        for pkgname, pkgver in list_installed(index, outdir):
            pkginfo = index[pkgname]
            verinfo = pkginfo["versions"][pkgver]
            uninstall = False
            
            for k, v in urls.iteritems():
                name, version = k
                if name == pkgname:
                    uninstall = (version == pkgver)
                    break
            
            if not uninstall:
                deps = verinfo.get("common", {}).get("dependencies", {})
                deps.update(verinfo.get(plat, {}).get("dependencies", {}))
                for depname, depver in deps.iteritems():
                    if (depname, depver) in urls:
                        print("Remove %s %s from uninstall list as it is required for %s %s" % (depname, depver, pkgname, pkgver))
                        print("  (use -f/--force to ignore this check at your own risk)")
                        del(urls[(depname, depver)])
    
    if len(urls) == 0:
        print("Nothing to uninstall")
        return
    
    downloaddir = outdir + "/downloads"
    if not os.path.isdir(downloaddir):
        return
    
    for k, v in urls.iteritems():
        name, version = k
        category, url = v
        
        targetname = os.path.basename(url.split("?")[0])
        
        prefix = ("/%s" % category if category else "")
        
        outenv = outdir + prefix + "/" + targetname
        
        if os.path.isfile(outenv):
            if verbose:
                print("Remove %s" % outenv)
            os.remove(outenv)

def help():
    name = os.path.splitext(os.path.basename(__file__))[0]
    
    print("""NAME
  dropboxpm - Simple dropbox based package manager

SYNOPSIS
  %s [-l/--list] [-i/--install] [-o/--output-directory DIR] [-f/--force] [-v/--verbose] [-h/--help] ARGUMENTS

ARGUMENTS
  List of packages <name>(<version>)

OPTIONS
  -i/--install               Install packages and/or environments
  -u/--uninstall             Uninstall packages and/or environments
  -r/--reinstall             Re-install packages and/or environments
  -m/--mode MODE             Install mode as a string
                             One of 'env', 'pkg', 'both'
                             Default is 'pkg'
  -o/--output-directory DIR  Specify output directory ('.' by default)
  -e/--exclude-dependencies  Do not follow dependencies
  -n/--installed             List installed packages
  -l/--list                  List available packages
  -v/--verbose               Verbose output
  -f/--force                 Force index update
  -h/--help                  Show this help

EXAMPLE
  python %s.py -i -m both -v alembic_devel
  python %s.py -u -m pkg -v alembic1.5.7
""" % (name, name, name))

if __name__ == "__main__":
    
    args = sys.argv[1:]
    
    outdir = "."
    verbose = False
    force = False
    excludedeps = False
    packages = []
    op = None
    mode = "pkg"
    
    i = 0
    n = len(args)
    while i < n:
        if args[i] in ("-v", "--verbose"):
            verbose = True
        elif args[i] in ("-f", "--force"):
            force = True
        elif args[i] in ("-e", "--exclude-dependencies"):
            excludedeps = True
        elif args[i] in ("-h", "--help"):
            help()
            sys.exit(0)
        elif args[i] in ("-l", "--list"):
            op = "list"
        elif args[i] in ("-n", "--installed"):
            op = "listinstalled"
        elif args[i] in ("-m", "--mode"):
            i += 1
            if i >= n:
                print("Missing required argument for -m/--mode")
                sys.exit(1)
            mode = args[i]
            if not mode in ("env", "pkg", "both"):
                print("Invalid mode '%s'" % mode)
                sys.exit(1)
        elif args[i] in ("-o", "--output-directory"):
            i += 1
            if i >= n:
                print("Missing required argument for -o/--output-directory")
                sys.exit(1)
            outdir = args[i]
            if not os.path.isdir(outdir):
                try:
                    os.makedirs(outdir)
                except Exception, e:
                    print("Failed to create output directory (%s)" % e)
                    sys.exit(1)
        elif args[i] in ("-i", "--install", "-r", "--reinstall", "-u", "--uninstall"):
            if args[i] in ("-r", "--reinstall"):
                op = "reinstall"
            elif args[i] in ("-u", "--uninstall"):
                op = "uninstall"
            else:
                op = "install"
        else:
            packages.append(args[i])
        i += 1
    
    if op is None:
        print("No operation specified.")
        sys.exit(1)
    
    index = None
    indexpath = outdir + "/index.json"
    dl = (force or not os.path.isfile(indexpath))
    
    if not dl:
        try:
            with open(indexpath, "r") as f:
                index = json.load(f)
        except:
            # Invalid index content -> force download
            dl = True
    
    if dl:
        try:
            indexurl = "https://www.dropbox.com/s/eg1wqjr1gdrx2u6/index.json?dl=1"
            download(indexurl, outdir)
            with open(indexpath, "r") as f:
                index = json.load(f)
        except Exception, e:
            print("Failed to retrieve index (%s)" % e)
            sys.exit(1)
    
    if op == "list":
        list_packages(index)
        sys.exit(0)
    
    if op == "listinstalled":
        if mode in ("both", "pkg"):
            print("PACKAGES")
            list_installed_packages(index, outdir, "  ")
        if mode in ("both", "env"):
            print("ENVIRONMENTS")
            list_installed_environments(index, outdir, "  ")
        sys.exit(0)
    
    if op in ("uninstall", "reinstall"):
        if mode in ("both", "pkg"):
            uninstall_packages(index, packages, outdir, ignoredeps=excludedeps, force=(force or op == "reinstall"), verbose=verbose)
        if mode in ("both", "env"):
            uninstall_environments(index, packages, outdir, ignoredeps=excludedeps, force=(force or op == "reinstall"), verbose=verbose)
    
    if op in ("install", "reinstall"):
        if mode in ("both", "pkg"):
            install_packages(index, packages, outdir, ignoredeps=excludedeps, force=force, verbose=verbose)
        if mode in ("both", "env"):
            install_environments(index, packages, outdir, ignoredeps=excludedeps, force=force, verbose=verbose)
    
