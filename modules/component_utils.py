from gluon import current, redirect, URL

def component_fail(message):
    if current.session is not None:
        current.session.flash = message
    redirect(URL('components', 'empty'))
