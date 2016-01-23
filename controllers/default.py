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
    """Displays a topic.
    We display both the top reviewers, truncated, and the list of all papers."""
    topic = db.topic(request.args(0)) or redirect(URL('default', 'index'))
    # Truncated list of top reviewers in this topic.
    # We would better cache it, as it will be requested very often, but
    # for the moment we just produce it.
    top_reviewers = db((db.reviewer.topic == topic.id) &
                       (db.reviewer.user == db.auth_user.id)
                       ).select(orderby=~db.reviewer.reputation, limitby=(0, 10))
    q = ((db.paper_in_topic.topic == topic.id) &
         (db.paper_in_topic.paper_id == db.paper.paper_id) &
         (db.paper_in_topic.end_date == None) &
         (db.paper.end_date == None)
         )

    db.paper.title.represent = lambda v, r: A(v, _href=URL('default', 'view_paper_in_topic',
                                                           args=[r.paper_in_topic.paper_id, topic.id]))
    links = []
    links.append(dict(header='',
                      body=lambda r: A('Versions', _href=URL('default', 'view_paper_versions',
                                                            args=[r.paper_in_topic.paper_id]))))
    links.append(dict(header='',
                      body=lambda r: A('Edit', _href=URL('default', 'edit_paper',
                                                         args=[r.paper_in_topic.paper_id], vars=dict(topic=topic.id)))))
    grid = SQLFORM.grid(q,
        args=request.args[:1], # The first parameter is the topic number.
        orderby=~db.paper_in_topic.score,
        fields=[db.paper_in_topic.paper_id, db.paper.id, db.paper.paper_id, db.paper.title, db.paper.authors,
                db.paper_in_topic.num_reviews, db.paper_in_topic.score],
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


def view_paper_versions():
    q = (db.paper.paper_id == request.args(0))
    grid = SQLFORM.grid(q,
        args=request.args[:1],
        fields=[db.paper.title, db.paper.author, db.paper.file, db.paper.start_date, db.paper.end_date],
        orderby=~db.paper.start_date,
        editable=False, deletable=False, create=False,
        details=True,
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


def view_paper_in_topic():
    """Views a paper, as belonging to a specific topic.  This also gives access to all
    the reviews for that paper. The latest version of the paper is shown, but each review
    points to the version of the paper that was current then.  Arguments:
    - paper_id
    - topic id
    """
    paper = db((db.paper.paper_id == request.args(0)) &
               (db.paper.end_date == None)).select().first()
    topic = db.topic(request.args(1))
    if paper is None or topic is None:
        session.flash = T('No such paper.')
        redirect(URL('default', 'index'))
    form = SQLFORM(db.paper, record=paper, readonly=True)
    # Retrieves the edit history of reviews.
    def get_review_history(r):
        review_history_len = db((db.review.paper_id == paper.paper_id) &
                                (db.review.topic == topic.id) &
                                (db.review.author == r.author)).count()
        return '' if review_history_len < 2 else A(T('Edit history',
                                                     _href=URL('default', 'review_history',
                                                               args=[paper.paper_id, topic.id, r.author])))
    # Retrieves the version of paper reviewed, if different from current one.
    def get_reviewed_paper(r):
        return 'Current' if r.paper == paper.id else A(T('View'),
                                                _href=URL('default', 'view_specific_paper_version', args=[r.paper]))
    # Grid of reviews.
    q = ((db.review.paper_id == paper.paper_id) &
         (db.review.topic == topic.id) &
         (db.review.end_date == None))
    links = []
    # Link to review edit history if any.
    links.append(dict(header='',
                      body=lambda r: get_review_history(r)))
    # Link to actual version of paper reviewed, if different from current one.
    links.append(dict(header='Reviewed version',
                      body=lambda r: get_reviewed_paper(r)))
    edit_review_link=A(T('Edit'), _href=URL('default', 'do_review', args=[paper.paper_id, topic.id]))
    db.review.author.represent = lambda v, r: CAT(B('You'), SPAN('(', edit_review_link, ')')) if v == auth.user_id else v
    grid = SQLFORM.grid(q,
        args=request.args[:2],
        fields=[db.review.grade, db.review.useful_count, db.review.content,
                db.review.author, db.review.start_date],
        links=links,
        details=True,
        editable=False, deletable=False, create=False,
        maxtextlength=48,
        )
    do_review_link = None
    doesnt_have_review = db((db.review.author == auth.user_id) &
                            (db.review.paper_id == paper.paper_id) &
                            (db.review.topic == topic.id)).isempty()
    if doesnt_have_review:
        do_review_link = A(T('Write a review'), _href=URL('default', 'do_review', args=[paper.id, topic.id]))
    paper_revisions = None
    if db(db.paper.paper_id == request.args(0)).count() > 1:
        paper_revisions = A('Revisions', _href=URL('default', 'view_paper_revisions', args=[db.paper.paper_id]))
    return dict(paper=paper, topic=topic,
                paper_revisions=paper_revisions,
                do_review_link=do_review_link,
                form=form, grid=grid)


def view_paper():
    """Views a paper, allowing also reviews of that paper.  Arguments: paper_id , the random paper_id.
    This shows the latest copy of the paper, and gives access to reviews and previous versions of the paper itself."""
    paper = db((db.paper.paper_id == request.args(0)) &
               (db.paper.end_date == None)).select().first()
    if paper is None:
        session.flash = T('No such paper')
        redirect(URL('default', 'index'))
    # Form for the paper.
    form = SQLFORM(db.paper, record=paper, readonly=True)
    # Link to see all versions.
    version_link = A(T('All versions'), _href=URL('default', 'view_paper_versions', args=[paper.paper_id]))
    # Grid of review forums.
    q = ((db.paper_in_topic.paper_id == paper.paper_id) &
         (db.paper_in_topic.topic == db.topic.id))
    db.topic.name.represent = lambda v, r: A(v, _href=URL('default', 'view_paper_in_topic', args=[paper.paper_id, r.topic.id]))
    grid = SQLFORM.grid(q,
        args=request.args[:1],
        fields=[db.topic.name, db.topic.id],
        create=False, editable=False, deletable=False,
        maxtextlength=48,
        csv=False, details=False,
        )
    return dict(form=form,
                version_link=version_link,
                grid=grid)


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


@auth.requires_login()
def do_review():
    """Performs the review of a paper.  The arguments are:
    - paper_id : the actual paper the person read.
    - topic.id : the id of the topic.
    If there is a current review, then lets the user edit that instead,
    keeping track of the old review.
    """
    # TODO: verify permissions.
    paper = db.paper(request.args(0))
    topic = db.topic(request.args(1))
    if paper is None or topic is None:
        session.flash = T('No such paper')
        redirect(URL('default', 'index'))
    # Checks whether the paper is currently in the topic.
    paper_in_topic = db((db.paper_in_topic.paper_id == paper.paper_id) &
                        (db.paper_in_topic.topic == topic.id) &
                        (db.paper_in_topic.end_date == None)).select().first()
    if paper_in_topic is None:
        session.flash = T('The paper is not in the selected topic')
        redirect(URL('default', 'index'))
    # Fishes out the current review, if any.person
    current_review = db((db.review.author == auth.user_id) &
                        (db.review.paper_id == paper.paper_id) &
                        (db.review.topic == topic.id) &
                        (db.review.end_date == None)).select().first()
    # Sets some defaults.
    logger.info("My user id: %r" % auth.user_id)
    db.review.paper.writable = False
    db.review.paper_id.readable = False
    db.review.author.default = auth.user_id
    db.review.paper_id.default = paper.paper_id
    db.review.paper.default = paper.id
    db.review.topic.default = topic.id
    db.review.start_date.label = T('Review date')
    db.review.end_date.readable = False
    db.review.useful_count.readable = False
    db.review.old_score.default = paper_in_topic.score
    # Creates the form for editing.
    form = SQLFORM(db.review, record=current_review,)
    if form.validate():
        # We must write the review as a new review.
        # First, we close the old review if any.
        now = datetime.utcnow()
        if current_review is not None:
            current_review.update_record(end_date=now)
        # Then, writes the current review.
        db.review.insert(author=auth.user_id,
                         paper_id=paper.paper_id,
                         paper=paper.id,
                         topic=topic.id,
                         start_date=now,
                         end_date=None,
                         content=str(text_store_write(form.vars.content)),
                         old_score=paper_in_topic.score
                         )
        session.flash = T('Your review has been accepted.')
        redirect(URL('default', 'view_paper_in_topic', args=[paper.paper_id, topic.id]))
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


