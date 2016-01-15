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


def topic_index():
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
         (db.paper_in_topic.end_date == None) &
         (db.paper.end_date == None)
         )

    links = []
    links.append(dict(header='',
                      body=lambda r: A('Edit', _href=URL('default', 'edit_paper',
                                                         args=[r.paper_in_topic.paper_id], vars=dict(topic=topic.id)))))
    grid = SQLFORM.grid(q,
        args=request.args[:1], # The first parameter is the topic number.
        orderby=~db.paper_in_topic.score,
        fields=[db.paper_in_topic.paper_id, db.paper.id, db.paper.paper_id, db.paper.title, db.paper.authors],
        csv=False, details=False,
        links=links,
        # These all have to be done with special methods.
        create=False,
        editable=False,
        deletable=False,
        maxtextlength=48,
    )
    add_paper_link = A(icon_add, 'Add a paper', _class='btn btn-success',
                       _href=URL('default', 'edit_paper', vars=dict(topic=topic.id)))
    return dict(top_reviewers=top_reviewers,
                grid=grid,
                topic=topic,
                add_paper_link=add_paper_link)


def edit_paper():
    """This is a temporary page, so that we can add papers to
    a series of topics.
    In reality we need a more sophisticated method for adding or editing
    papers, and for importing from ArXiV.
    If args(0) is specified, it is the id of the paper to edit.
    If the variable 'topic' is specified, it is taken to be the topic id
    of a paper to which the paper belongs by default."""
    paper = db(db.paper.paper_id == request.args(0)).select(orderby=~db.paper.start_date).first()
    is_create = paper is None
    topic = db.topic(request.vars.topic)
    # Creates the form.
    form = SQLFORM.factory(
        Field('title', default=None if is_create else paper.title),
        Field('authors', 'list:string', default=None if is_create else paper.authors),
        Field('abstract', 'text', default=None if is_create else text_store_read(paper.abstract)),
        Field('file', default=None if is_create else paper.file),
        # Here we would need multiple=True and a different interface (write and autocomplete?),
        # but multiple=True seems to be broken.
        Field('topics', 'list:reference topic', default=[topic.id], requires=IS_IN_DB(db, 'topic.id', '%(name)s', multiple=False))
    )
    if form.process().accepted:
        # We have to carry out the requests in the form.
        now = datetime.utcnow()
        if is_create:
            # We have to come up with a new random id.
            random_paper_id = review_utils.get_random_id()
            abstract_id = text_store_write(form.vars.abstract)
            # We write the paper.
            db.paper.insert(paper_id=random_paper_id,
                            title=form.vars.title,
                            authors=form.vars.authors,
                            abstract=abstract_id,
                            file=form.vars.file,
                            start_date=datetime.utcnow(),
                            end_date=None
                            )
        else:
            random_paper_id = paper.paper_id
            # Checks if anything has changed about the paper, as opposed to the topics.
            is_abstract_different = False
            abstract_id = paper.abstract
            if form.vars.abstract != text_store_read(paper.abstract):
                abstract_id = text_store_write(form.vars.abstract)
                is_abstract_different = True
            if ((form.vars.title != paper.title) or
                    (form.vars.authors != paper.authors) or
                    is_abstract_different):
                logger.info("The paper itself changed; moving to a new paper instance.")
                # Closes the validity period of the previous instance of this paper.
                paper.update_record(end_date=now)
                # We write the paper.
                db.paper.insert(paper_id=random_paper_id,
                                title=form.vars.title,
                                authors=form.vars.authors,
                                abstract=abstract_id,
                                file=form.vars.file,
                                start_date=datetime.utcnow(),
                                end_date=None
                                )
            else:
                logger.info("The paper itself is unchanged.")
        # Then, we take care of the topics.
        # First, we close the topics to which the paper no longer belongs.
        previous_occurrences = db((db.paper_in_topic.paper_id == random_paper_id) &
                                  (db.paper_in_topic.end_date == None)).select()
        topic_list = review_utils.clean_int_list(form.vars.topics)
        logger.info("topic_list: %r" % topic_list)
        for t in previous_occurrences:
            if t.topic not in topic_list:
                logger.info("Removing paper from topic %r" % t.topic)
                t.update_record(end_date=now)
        # Second, for each new topic, searches.  If the paper has never been in that topic before,
        # it adds the paper to that topic.  Otherwise, it re-opens the previous tenure of the paper
        # in that topic.
        for tid in topic_list:
            last_occurrence = db((db.paper_in_topic.paper_id == random_paper_id) &
                                 (db.paper_in_topic.topic == tid)).select(orderby=~db.paper_in_topic.start_date).first()
            if last_occurrence is None:
                # We need to insert.
                logger.info("Adding paper to new topic %r" % tid)
                db.paper_in_topic.insert(paper_id=random_paper_id,
                                         topic=tid,
                                         start_date=now)
            elif last_occurrence.end_date is not None:
                # There was a previous occurrence, but it has now been closed.
                # We reopen it.
                logger.info("Reopening paper presence in topic %r" % tid)
                db.paper_in_topic.insert(paper_id=random_paper_id,
                                         topic=tid,
                                         start_date=now,
                                         num_reviews=last_occurrence.num_reviews,
                                         score=last_occurrence.score,
                                         )
        # The paper has been updated.
        session.flash = T('The paper has been updated.')
        # If we were looking at a specific topic, goes back to it.
        if request.vars.topic is not None:
            redirect(URL('default', 'topic_index', args=[request.vars.topic]))
        else:
            redirect(URL('default', 'index'))
    return dict(form=form)


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


