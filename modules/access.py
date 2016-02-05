# Utility for access control.

from gluon import current

def is_logged_in():
    return current.auth.user_id is not None
