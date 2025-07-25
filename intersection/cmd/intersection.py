import sys
import re
import os
import time
import spack.config
import spack.cmd
import spack.environment as ev
import spack.cmd.common.arguments as arguments
import spack.util.spack_yaml as syaml
try:
    import ruamel.yaml as ruamel_yaml
except:
    import spack.vendor.ruamel.yaml as ruamel_yaml
from spack.cmd.env import _env_create
import spack.llnl.util.tty.color
import spack.llnl.util.tty as tty


description = "Build spack.yaml for an environment which is the intersection of the dependencies of several spack.yaml files"
section = "environments"
level = "short"


def setup_parser(subparser):
    subparser.add_argument("--threshold", help="package must be in more than this many environments to be included")
    subparser.add_argument("--keep-envs", action="store_true", help="keep temporary environments for concretizing")
    subparser.add_argument("--unify", action="store_true", help="use unify: true instaed of unify: when_possible")
    subparser.add_argument("spack_yaml", nargs='+', help="environment spack.yaml file(s)",  action="append") 
  


def intersection(parser, args):
    
    ''' find common "intersection" packages between a set/list
        of environment spack.yaml files.'''

    tty.debug(f"args.spack_yaml is {repr(args.spack_yaml)}")

    # pick a unique base for environment names...
    base = f"cs_env_{os.getpid()}_{int(time.time())}"
    yaml_merge = ruamel_yaml.YAML(typ="rt", pure=True)
    count = 0
    merged_content = {'spack':{}}
    
    # regexp to substitute with blank to cleanup specs
    cleanupre = re.compile( r"(patches|build_system):?=[a-z0-9_,]*" )

    for syf in args.spack_yaml[0]:
        tty.debug(f"examining {syf}")
        count = count + 1
        _env_create( f"{base}_{count}", init_file = syf )  
        with open(syf,"r") as syfd:
            content = yaml_merge.load(syfd)

        for k in content['spack']:
            tty.debug(f"examining key: spack.{k}")
            sys.stdout.flush()
            if k in merged_content['spack']:
                if isinstance(merged_content['spack'][k], list):
                    tty.debug(f"extending list under 'spack.{k}:'")
                    merged_content['spack'][k].extend(content['spack'][k])
                elif isinstance(merged_content['spack'][k], dict) and isinstance(content['spack'][k], dict):
                    tty.debug(f"updating dict under 'spack.{k}:'")
                    merged_content['spack'][k].update(content['spack'][k])
                elif isinstance(merged_content['spack'][k], dict) and not isinstance(content['spack'][k], dict):
                    # if we have a dict and they have a 'true', then or some such, skip it
                    pass
                else:
                    tty.debug(f"replacing 'spack.{k}:'")
                    merged_content['spack'][k] = content['spack'][k]
            else:
                merged_content['spack'][k] = content['spack'][k]
            sys.stdout.flush()

    if args.threshold:
        threshold = int(args.threshold)
    else:
        threshold = (count + 1) // 2

    if args.unify:
        unify_val = True
    else:
        unify_val = 'when_possible'

    # turn off views in the merge as they *never* come out happy from the merge...
    merged_content['spack']['view'] = False
    # set the concretizer how we like it...
    merged_content['spack']['concretizer'] = {
      "unify": unify_val,
      "reuse": {
        "roots": True,
        "from": [
          {"type": "local"},
          {"type": "external"},
        ]
      },
    }
#      "duplicates": {
#        "strategy": "none",
#      }
    merged_content['spack']['include_concrete'] = []

    msyf = base+"_merge_spack.yaml"
    with open(msyf, "w") as msy:
        yaml_merge.dump(merged_content, stream=msy)

    _env_create( f"{base}_0", init_file = msyf)
    
    deps_l_l = []
    dep_depth = {}
    scan = []
    maxl = 0
    depcounts = {}
    last_dep_env = {}
    combdeps = {}
    roots = {}
    squashre = re.compile('  *')
    for i in range(count+1):
        saw_conc = False
        cmd = f"spack -e {base}_{i} concretize --deprecated -f 2>&1 | tee {base}_conc_{i}.out"
        tty.debug(f"running: {cmd}")
        depset = set()
        ok = True
        scf = os.popen(cmd,"r")
        if scf:
            for dep_l in scf.readlines():

                if (dep_l.find("satisfy a requirement for package") >= 0 or
                   dep_l.find("Error: failed to concretize ") >= 0):
                    ok = False

                # skip information messages/warnings
                if dep_l.find('==> ') == 0:
                    continue
                # skip externals
                if dep_l.startswith('[e]'):
                    continue
                dep_l = squashre.sub(' ', dep_l)
                is_root = False
                pos = dep_l.find('^')
                if pos == -1:
                     # when its in the output wihtout a hat (^)
                     # then it is a root spec in that environment
                     # so we flag it so we can mark it as a root
                     # also we snip off up to the blank after the hash...
                     is_root = True
                     pos = dep_l.find(' ',7)
                # trim to just package name and later
                dep_l = dep_l[pos+1:]
                dep_pkg = dep_l[0:dep_l.find('@')]

                if is_root:
                    roots[dep_pkg] = True

                if dep_pkg in ['libc','gmake','gcc-runtime']:
                    # skip certain packages...
                    continue

                if i == 0 and dep_pkg not in combdeps:
                    combdeps[dep_pkg] = dep_l
                    dep_depth[dep_pkg] = pos

                if combdeps.get(dep_pkg,'').strip() != dep_l.strip():
                    tty.warn(f"conflicts for {dep_pkg}:\n   {dep_l}   {combdeps.get(dep_pkg,'')}")
                    # if it is a less deeply nested package, take it
                    tty.debug(f"depth: {pos} vs {dep_depth.get(dep_pkg,0)}")
                    if pos > dep_depth.get(dep_pkg,0):
                        tty.warn(f"updated {dep_pkg}.")
                        combdeps[dep_pkg] = dep_l
                        dep_depth[dep_pkg] = pos

                depset.add(dep_pkg)

            for dep_pkg in depset:
                # bookkeeping...
                if not (dep_pkg in depcounts):
                    depcounts[dep_pkg] = 0

                if not (dep_pkg in last_dep_env):
                    # setting it to zero means we won't count it in 
                    # the zeroth env (the combined one) due to the if
                    # below...
                    last_dep_env[dep_pkg] = 0

                if last_dep_env[dep_pkg] != i:
                    depcounts[dep_pkg] = depcounts[dep_pkg] + 1
                    # mark it so we don't count it in this env again
                    last_dep_env[dep_pkg] = i


        res = scf.close()
        if res != None or not ok:
            tty.warn(f"concretizing {base}_{i} failed, leaving temp environments, see {base}_conc_{i}.out")
            exit(1)

    tty.debug("last_dep_env: ", repr(last_dep_env))
    tty.debug("depcounts: ", repr(depcounts))
    tty.debug("combdeps: ", repr(combdeps))

    # now that we concretized everything and did bookkeeping
    # come up with the acutal list of shared specs from the
    # combined deps...
    shareddeps = []
    for dep_pkg in depcounts:
        if depcounts[dep_pkg] > threshold and dep_pkg in combdeps and not dep_pkg in roots:
            shareddeps.append( cleanupre.sub('', combdeps[dep_pkg]).strip() )

    # cleanup, pick up, put away... 
    if not args.keep_envs:
        for i in range(count+1):
            saw_conc = False
            cmd = f"spack env remove -y {base}_{i}"
            tty.info(f"running: {cmd}")
            os.system(cmd)
            os.unlink( f"{base}_conc_{i}.out" )
        os.unlink( msyf )

    # now make the intersection.spack.yaml
    # it's the union one, but with unify concretization and just the
    # shared dependencies as specs
    shareddeps.sort()
    merged_content['spack']['specs'] =  shareddeps
    merged_content['spack']['concretizer']['unify'] = True

    msyf = "intersection_spack.yaml"
    with open(msyf, "w") as msy:
        yaml_merge.dump(merged_content, stream=msy)

    tty.info(f"wrote {len(shareddeps)} specs into {msyf}")

