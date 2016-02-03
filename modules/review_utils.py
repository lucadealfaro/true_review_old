from gluon import utils as gluon_utils


def get_random_id(length=64):
    m = (length * 8) / 128
    sl = [get_clean_uuid() for _ in range(m)]
    return ''.join(sl)

def get_clean_uuid():
    u = gluon_utils.web2py_uuid()
    return u.replace('-', '')

def clean_int_list(s):
    """Returns a list out of a request variable that is supposed to
        contain a list."""
    if isinstance(s, basestring):
        return [int(s)]
    elif isinstance(s, int):
        return [s]
    return [int(x) for x in s]

def safe_int(s):
    """Returns an int if possible, otherwise None."""
    try:
        return int(s)
    except Exception, e:
        return None

def reputation_atom(old_score, grade, current_score):
    """Returns the reputation boost due to having assigned [grade] to a paper
       that at the time had score [old_score] 
       and currently has score [current_score]."""
    offset = 10
    alpha = 0.5
    return offset + alpha*(old_score-current_score)**2 - (1-alpha)*(grade-current_score)**2
