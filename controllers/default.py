# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

from google.appengine.api import taskqueue
import json
import review_utils

def dbupdate():
    return "ok"

def set_timezone():
    """Ajax call to set the timezone information for the session."""
    tz_name = request.vars.name
    # Validates the name.
    from pytz import all_timezones_set
    if tz_name in all_timezones_set:
        session.user_timezone = tz_name
        # If the user is logged in, sets also the timezone for the user.
        # Otherwise, it can happen that a user expires a cookie, then click on edit.
        # When the user is presented the edit page, the translation is done according to UTC,
        # but when the user is done editing, due to autodetection, the user is then in
        # it's own time zone, and the dates of an assignment change.
        # This really happened.
        if auth.user is not None:
            db.auth_user[auth.user.id] = dict(user_timezone = tz_name)
        logger.info("Set timezone to: %r" % tz_name)
    else:
        logger.warning("Invalid timezone received: %r" % tz_name)


def index():
    """ Serves the main page."""
    # Displays list of topics.
    q = db.topic
    links=[]
    if auth.user_id:
        links.append(dict(header='',
                          body=lambda r: A('Edit', _href=URL('default', 'edit_topic', args=[r.id]))))
        links.append(dict(header='',
                          body=lambda r: A('Delete', _href=URL('default', 'delete_topic', args=[r.id]))))
    grid = SQLFORM.grid(q,
        csv=False, details=False,
        links=links,
        create=False,
        editable=False,
        deletable=False,
        maxtextlength=48,
    )
    add_button = A(icon_add, 'Add topic', _class='btn btn-success',
                    _href=URL('default', 'create_topic')) if auth.user_id else None
    return dict(grid=grid, add_button=add_button)


@auth.requires_login()
def delete_topic():
    """Deletion of a topic.  We would need to unlink from the topic all the papers that are in it.
    Deletion should be possible only if there are no reviews. Otherwise we need to figure out
    what to do; perhaps simply hide the topic from the main listing."""
    return dict()


@auth.requires_login()
def create_topic():
    form = SQLFORM(db.topic)
    if form.validate():
        db.topic.insert(name=form.vars.name,
                        description=text_store_write(form.vars.description))
        session.flash = T('The topic has been created')
        redirect(URL('default', 'index'))
    return dict(form=form)


@auth.requires_login()
def edit_topic():
    """Allows editing of a topic.  The parameter is the topic id."""
    topic = db.topic(request.args(0))
    form = SQLFORM(db.topic, record=topic)
    form.vars.description = text_store_read(topic.description)
    if form.validate():
        topic.update_record(
            name=form.vars.name,
        )
        text_store_write(form.vars.description, key=topic.description)
        session.flash = T('The topic has been created')
        redirect(URL('default', 'index'))
    return dict(form=form)


def topic_index():
    """Displays a topic.  This is a simple method, as most information
    on the papers and on the reviews is provided via included tables and/or AJAX."""
    topic = db.topic(request.args(0)) or redirect(URL('default', 'index'))
    return dict(topic=topic)

def view_paper_versions():
    q = (db.paper.paper_id == request.args(0))
    grid = SQLFORM.grid(q,
        args=request.args[:1],
        fields=[db.paper.title, db.paper.authors, db.paper.file, db.paper.start_date],
        orderby=~db.paper.start_date,
        editable=False, deletable=False, create=False,
        details=True,
        csv=False,
        maxtextlength=32,
        )
    return dict(grid=grid)


def view_specific_paper_version():
    """Displays a specific paper version.  Called by paper id."""
    paper = db.paper(request.args(0))
    if paper is None:
        session.flash = T('No such paper')
        redirect(URL('default', 'index'))
    form = SQLFORM(db.paper, record=paper, readonly=True)
    all_versions_link = A('All versions', _href=URL('default', 'view_paper_versions', args=[paper.paper_id]))
    return dict(form=form,
                all_versions_link=all_versions_link)


def view_paper():
    """Views a paper, including the details of the paper, and all the reviews.
     Arguments:
         - paper_id
    """
    return dict(paper_id=request.args(0),
                topic_id=request.args(1))


@auth.requires_login()
def edit_paper():
    """This is a temporary page, so that we can add papers to
    a series of topics.
    In reality we need a more sophisticated method for adding or editing
    papers, and for importing from ArXiV.
    If args(0) is specified, it is the id of the paper to edit.
    If the variable 'topic' is specified, it is taken to be the topic id
    of a paper to which the paper belongs by default.

    Note that I am assuming here that anyone can edit a paper.
    """
    # TODO: verify permissions.
    paper = db(db.paper.paper_id == request.args(0)).select(orderby=~db.paper.start_date).first()
    is_create = paper is None
    # If there is no topic,
    # Creates the form.
    default_topic_id = paper.primary_topic if paper else request.vars.topic
    form = SQLFORM.factory(
        Field('title', default=None if is_create else paper.title),
        Field('authors', 'list:string', default=None if is_create else paper.authors),
        Field('abstract', 'text', default=None if is_create else text_store_read(paper.abstract)),
        Field('file', default=None if is_create else paper.file),
        Field('primary_topic', 'reference topic', default=default_topic_id, requires=IS_IN_DB(db, 'topic.id', '%(name)s')),
        Field('secondary_topics'),
    )
    def validate_paper_edit_form(form):
        # Checks the names of the secondary topics.
        primary_topic_id = form.vars.primary_topic
        secondary_topic_ids = []
        if form.vars.secondary_topics is not None:
            secondary_topics_raw_names = form.vars.secondary_topics.split(';')
            for n in secondary_topics_raw_names:
                nn = n.strip()
                if nn != '':
                    t = db(db.topic.name == nn).select().first()
                    if t is None:
                        form.errors.secondary_topics = T('The topic %r does not exist') % nn
                        return form
                    else:
                        secondary_topic_ids.append(t.id)
            form.vars.secondary_topic_ids = list(set(secondary_topic_ids) - {primary_topic_id})
        return form

    if form.process(onvalidation=validate_paper_edit_form).accepted:
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
                            primary_topic=form.vars.primary_topic,
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
                                primary_topic=form.vars.primary_topic,
                                start_date=datetime.utcnow(),
                                end_date=None
                                )
            else:
                logger.info("The paper itself is unchanged.")
        # Then, we take care of the topics.
        new_topics = set({form.vars.primary_topic}) | set(form.vars.secondary_topic_ids)
        logger.info("new topics: %r" % new_topics)
        # First, we close the topics to which the paper no longer belongs.
        previous_occurrences = db((db.paper_in_topic.paper_id == random_paper_id) &
                                  (db.paper_in_topic.end_date == None)).select()
        for t in previous_occurrences:
            if t.topic not in new_topics:
                logger.info("Removing paper from topic %r" % t.topic)
                t.update_record(end_date=now)
        # Second, for each new topic, searches.  If the paper has never been in that topic before,
        # it adds the paper to that topic.  Otherwise, it re-opens the previous tenure of the paper
        # in that topic.
        for tid in new_topics:
            last_occurrence = db((db.paper_in_topic.paper_id == random_paper_id) &
                                 (db.paper_in_topic.topic == tid)).select(orderby=~db.paper_in_topic.start_date).first()
            if last_occurrence is None:
                # We need to insert.
                logger.info("Adding paper to new topic %r" % tid)
                db.paper_in_topic.insert(paper_id=random_paper_id,
                                         topic=tid,
                                         is_primary = tid == form.vars.primary_topic,
                                         start_date=now)
            elif last_occurrence.end_date is not None:
                # There was a previous occurrence, but it has now been closed.
                # We reopen it.
                logger.info("Reopening paper presence in topic %r" % tid)
                db.paper_in_topic.insert(paper_id=random_paper_id,
                                         topic=tid,
                                         is_primary = tid == form.vars.primary_topic,
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
    return dict(form=form, is_create=is_create)


@auth.requires_login()
def do_review():
    """Performs the review of a paper.  The arguments are:
    - paper_id : the actual paper the person read.
    - topic.id : the id of the topic.
    If there is a current review, then lets the user edit that instead,
    keeping track of the old review.
    """
    return dict(paper_id=request.args(0), topic_id=request.args(1))


def review_history():
    """Shows the review history of a certain paper by a certain author.
    The arguments are:
    - paper_id
    - topic id
    - author
    """
    db.review.start_date.label = T('Review date')
    db.review.content.label = T('Review')
    db.review.paper.represent = lambda v, r: represent_specific_paper_version(v)
    q = ((db.review.paper_id == request.args(0)) &
         (db.review.topic == request.args(1)) &
         (db.review.author == review_utils.safe_int(request.args(1))))
    grid = SQLFORM.grid(q,
        args=request.args[:3],
        fields=[db.review.grade, db.review.useful_count, db.review.content,
                db.review.paper, db.review.start_date],
        details=False,
        editable=False, deletable=False, create=False,
        maxtextlength=48,
        )
    author = db.auth_user(request.args(2))
    return dict(grid=grid,
                author=author)

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


