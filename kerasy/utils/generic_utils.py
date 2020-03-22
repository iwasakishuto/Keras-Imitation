import os
import sys
import time
import datetime
import numpy as np
from six.moves.urllib.request import urlretrieve

from collections import defaultdict

def flatten_dual(lst):
    return [e for sublist in lst for e in sublist]

_UID_PREFIXES = defaultdict(int)
def get_file(fname, origin, cache_subdir='datasets', file_hash=None):
    """Downloads a file from a URL if not already in the cache.
    ref: https://github.com/keras-team/keras/blob/7a39b6c62d43c25472b2c2476bd2a8983ae4f682/keras/utils/data_utils.py#L123

    By default the file at the url `origin` is downloaded to the
    cache_dir `~/.kerasy`, placed in the cache_subdir `datasets`,
    and given the filename `fname`. The final location of a file
    `example.txt` would therefore be `~/.kerasy/datasets/example.txt`.

    You have to make a directory `~/.kerasy` and `~./kerasy/datasets`,
    and check whether you can access these directories using `os.access("DIRECOTRY", os.W_OK)`
    If this method returns False, you have to change the ownership of them like
    ```
    $ sudo chown iwasakioshuto: ~/.kerasy
    $ sudo chown iwasakioshuto: ~/.kerasy/datasets
    ```
    """
    cache_dir = os.path.join(os.path.expanduser('~'), '.kerasy')
    datadir_base = os.path.expanduser(cache_dir)
    if not os.access(datadir_base, os.W_OK):
        datadir_base = os.path.join('/tmp', '.kerasy')
    datadir = os.path.join(datadir_base, cache_subdir)
    if not os.path.exists(datadir):
        os.makedirs(datadir)
    fpath = os.path.join(datadir, fname)

    if not os.path.exists(fpath):
        print('Downloading data from', origin)
        error_msg = 'URL fetch failure on {} : {} -- {}'
        try:
            try:
                urlretrieve(origin, fpath)
            except HTTPError as e:
                raise Exception(error_msg.format(origin, e.code, e.msg))
            except URLError as e:
                raise Exception(error_msg.format(origin, e.errno, e.reason))
        except (Exception, KeyboardInterrupt):
            if os.path.exists(fpath):
                os.remove(fpath)
            raise
    return fpath

def get_uid(prefix=""):
    _UID_PREFIXES[prefix] += 1
    return _UID_PREFIXES[prefix]

class priColor:
    BLACK     = '\033[30m'
    RED       = '\033[31m'
    GREEN     = '\033[32m'
    YELLOW    = '\033[33m'
    BLUE      = '\033[34m'
    PURPLE    = '\033[35m'
    CYAN      = '\033[36m'
    WHITE     = '\033[37m'
    RETURN    = '\033[07m'    # 反転
    ACCENT    = '\033[01m'    # 強調
    FLASH     = '\033[05m'    # 点滅
    RED_FLASH = '\033[05;41m' # 赤背景+点滅
    END       = '\033[0m'
    @staticmethod
    def color(value, color="RED"):
        color = color.upper()
        handleKeyError(priColor.__dict__.keys(), color=color)
        return f"{priColor.__dict__[color.upper()]}{value}{priColor.END}"

def handleKeyError(lst, message="", **kwargs):
    k,v = kwargs.popitem()
    if v not in lst:
        raise KeyError(f"Please chose the argment `{k}` from f{', '.join(lst)}.\n{message}")

def urlDecorate(url, addDate=True):
    """ Decorate URL like Wget. (Add datetime information and coloring url to blue.) """
    now = datetime.datetime.now().strftime("--%Y-%m-%d %H:%M:%S--  ") if addDate else ""
    return now + priColor.color(url, color="BLUE")

def measure_complexity(func, *args, repetitions_=10, **kwargs):
    times=0
    metrics=[]
    if "random_state" in kwargs:
        base_seed = kwargs.get("random_state")
        for i in range(repetitions_):
            kwargs["random_state"] = base_seed+i
            s = time.time()
            ret = func(*args, **kwargs)
            times += time.time()-s
            metrics.append(ret)
    else:
        for _ in range(repetitions_):
            s = time.time()
            ret = func(*args, **kwargs)
            times += time.time()-s
            metrics.append(ret)
    if metrics[0] is None:
        return times/repetitions_
    else:
        return (times/repetitions_, metrics)

def has_not_attrs(obj, *names):
    return [name for name in names if not hasattr(obj, name)]

def has_all_attrs(obj, *names):
    return sum([1 for name in names if not hasattr(obj, name)])==0

def handle_random_state(seed):
    """ Turn `np.random.RandomState` """
    if seed is None:
        return np.random.mtrand._rand
    if isinstance(seed, np.random.RandomState):
        return seed
    if isinstance(seed, int):
        return np.random.RandomState(seed)
    raise ValueError(f"Could not conver {seed} to numpy.random.RandomState instance.")

def fout_args(*args, sep="\t"):
    return sep.join([str(e) for e in args])+"\n"
