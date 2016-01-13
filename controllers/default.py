# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

from google.appengine.api import taskqueue
import json

def dbupdate():
    return "ok"

def index():
    """ Serves the main page."""
    # Displays list of topics.
    q = db.topic
    grid = SQLFORM.grid(q,
        csv=False, details=True,
        create=is_logged_in,
        editable=is_logged_in,
        deletable=is_logged_in,
        maxtextlength=48,
    )
    return dict(grid=grid)

def topic():
    """Displays a topic.
    We display both the top reviewers, truncated, and the list of all papers."""
    topic = db.topic(request.args(0)) or redirect(URL('default', 'index'))
    # Truncated list of top reviewers in this topic.
    # We would better cache it, as it will be requested very often, but
    # for the moment we just produce it.
    top_reviewers = db((db.reviewer.topic == topic.id) &
                       (db.reviewer.user == db.person.id)
                       ).select(orderby=~db.reviewer.reputation, limitby=(0, 10))
    q = ((db.paper_in_topic.topic == topic.id) &
         (db.paper_in_topic.paper_id == db.paper.paper_id) &
         (db.paper.end_date == None))
    grid = SQLFORM.grid(q,
        args=request.args[:1], # The first parameter is the topic number.
        orderby=~db.paper_in_topic.score,
        csv=False, details=True,
        create=False,
        editable=is_logged_in,
        deletable=is_logged_in,
        maxtextlength=48,
    )
    add_paper_link = A(icon_add, 'Add a paper', _class='btn btn-success',
                       _href=URL('default', 'add_paper', args=[topic.id]))
    return dict(top_reviewers=top_reviewers,
                grid=grid,
                add_paper_link=add_paper_link)


def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/manage_users (requires membership in
    http://..../[app]/default/user/bulk_register
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())


@cache.action()
def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()


