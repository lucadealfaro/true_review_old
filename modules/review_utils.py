from gluon import utils as gluon_utils


def get_random_id(length=64):
    m = (length * 8) / 128
    sl = [get_clean_uuid() for _ in range(m)]
    return ''.join(sl)

def get_clean_uuid():
    u = gluon_utils.web2py_uuid()
    return u.replace('-', '')
