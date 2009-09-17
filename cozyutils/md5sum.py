from __future__ import with_statement

from hashlib import md5

def sumfile(fobj):
    '''Returns an md5 hash for an object with read() method.'''
    m = md5()
    while True:
        d = fobj.read(8096)
        if not d:
            break
        m.update(d)
    return m.hexdigest()


def md5sum(fname):
    '''Returns an md5 hash for file fname'''
    with open(fname, 'rb') as f:
        ret = sumfile(f)
    return ret

def md5sum_from_string(string):
    return md5(string).hexdigest()
