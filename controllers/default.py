# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

from google.appengine.api import taskqueue
import json
import review_utils

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
                       _href=URL('default', 'add_paper', vars=dict(topic=topic.id)))
    return dict(top_reviewers=top_reviewers,
                grid=grid,
                add_paper_link=add_paper_link)


def edit_paper():
    """This is a temporary page, so that we can add papers to
    a series of topics.
    In reality we need a more sophisticated method for adding or editing
    papers, and for importing from ArXiV.
    If args(0) is specified, it is the id of the paper to edit.
    If the variable 'topic' is specified, it is taken to be the topic id
    of a paper to which the paper belongs by default."""
    is_create = request.args(0) is None
    paper = None if is_create else db.paper(request.args(0))
    if not (is_create or paper):
        redirect(URL('default', 'index')) # Edit of non-existing paper.
    topics = set()
    if is_create and request.vars.topic is not None:
        topics = {request.vars.topic}
    if not is_create:
        topics = set(db(db.paper_in_topic.paper_id == paper.paper_id).select(db.paper_in_topic.topic).as_list())
    # Creates the form.
    form = SQLFORM.factory(
        Field('title', default=None if is_create else paper.title),
        Field('authors', 'list:string', default=None if is_create else paper.authors),
        Field('abstract', 'text', default=None if is_create else paper.abstract),
        Field('file', default=None if is_create else paper.file),
        Field('topics', 'list:reference topic', default=topics, requires=IS_IN_DB(db, db.topic.id, multiple=True))
    )
    if form.process().accepted:
        # We have to carry out the requests in the form.
        if is_create:
            # We have to come up with a new random id.
            random_paper_id = review_utils.get_random_id()
            # We write the paper.
            i = db.paper.insert(paper_id=random_paper_id,
                                title=form.vars.title,
                                authors=form.vars.authors,
                                abstract=text_store_write(form.vars.abstract),
                                file=form.vars.file,
                                start_date=datetime.utcnow(),
                                end_date=None
                                )
            # Then, we add the paper to each topic.
            for t in form.vars.topics:
                db.paper_in_topic.insert(paper_id=random_paper_id, topic=t)

        else:
            # This is an update of an existing paper.
    


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


