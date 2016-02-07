# Here we put code for producing components that are in charge of
# rendering particular elements, and can be included in views.

import access

def paper_topic_grid(topic_id, all_papers=False):
    """Produces a grid containing the papers in a topic.
    The grid is done so that it can be easily included in a more complex page.
    The arguments are:
    - topic_id (in path)
    - all_papers=y (in query): if yes, then also papers that are not primary in the topic
      will be included.
    """
    topic = db.topic(topic_id) or redirect(URL('default', 'index'))
    fields = [db.paper_in_topic.paper_id, db.paper.id, db.paper.paper_id,
              db.paper.title, db.paper.authors, db.paper_in_topic.is_primary]
    orderby = db.paper.start_date
    links = []
    if all_papers:
        q = ((db.paper_in_topic.topic == topic.id) &
             (db.paper_in_topic.paper_id == db.paper.paper_id) &
             (db.paper_in_topic.end_date == None) &
             (db.paper.end_date == None) &
             (db.topic.id == db.paper.primary_topic)
             )
        fields.extend([db.paper.primary_topic, db.topic.name])
        # db.paper.primary_topic.represent = lambda v, r: '' if v == topic_id else v
        db.paper.primary_topic.label = T('Primary topic')
        db.topic.name.readable = False
        db.paper.primary_topic.represent = lambda v, r: A(r.topic.name, _href=URL('default', 'topic_index', args=[v]))
        links.append(dict(header='',
                          body=lambda r: (icon_primary_paper if r.paper_in_topic.is_primary else icon_all_paper)))

    else:
        q = ((db.paper.primary_topic == topic_id) &
             (db.paper.end_date == None) &
             (db.paper.paper_id == db.paper_in_topic.paper_id) &
             (db.paper_in_topic.topic == topic_id) &
             (db.paper_in_topic.end_date == None)
             )
        fields.extend([db.paper_in_topic.num_reviews, db.paper_in_topic.score])
        orderby = ~db.paper_in_topic.score
    db.paper.title.represent = lambda v, r: A(v, _href=URL('default', 'view_paper',
                                                           args=[r.paper_in_topic.paper_id, topic.id]))
    # links.append(dict(header='',
    #                   body=lambda r: A('Versions', _href=URL('default', 'view_paper_versions',
    #                                                         args=[r.paper_in_topic.paper_id]))))
    # links.append(dict(header='',
    #                   body=lambda r: A('Edit', _href=URL('default', 'edit_paper',
    #                                                      args=[r.paper_in_topic.paper_id], vars=dict(topic=topic.id)))))
    grid = SQLFORM.grid(q,
        args=request.args[:1], # The first parameter is the topic id.
        orderby=orderby,
        fields=fields,
        field_id=db.paper.id,
        csv=False, details=False,
        links=links,
        links_placement='left',
        # These all have to be done with special methods.
        create=False,
        editable=False,
        deletable=False,
        maxtextlength=48,
    )
    return grid


def paper_topic_index():
    """Returns a grid, and associated code, to display all papers in a topic.
    Arguments:
        - topic_id (in path): id of the topic
        - all_papers=y: in query, indicates whether all papers should be shown.
    """
    topic_id = request.args(0)
    all_papers = request.vars.all_papers == 'y'
    grid = paper_topic_grid(topic_id, all_papers=all_papers)
    # Creates buttons to see all papers, or only the papers that are primary.
    all_paper_vars = request.vars.copy()
    all_paper_vars.update(dict(all_papers='y'))
    topic_paper_vars = request.vars.copy()
    topic_paper_vars.update(dict(all_papers='n'))
    all_papers_classes = 'btn btn-success'
    primary_papers_classes = 'btn btn-success'
    if all_papers:
        all_papers_classes += ' disabled'
    else:
        primary_papers_classes += ' disabled'
    button_all_papers = A(icon_all_paper, T('All papers'), _id='all_papers_button',
                          cid=request.cid,  # trapped load
                          _class=all_papers_classes,
                          _href=URL('components', 'paper_topic_index',
                                    args=request.args, vars=all_paper_vars))
    button_topic_papers = A(icon_primary_paper, T('Primary topic papers'), _id='primary_papers_button',
                            cid=request.cid,  # trapped load
                            _class=primary_papers_classes,
                            _href=URL('components', 'paper_topic_index',
                                      args=request.args, vars=topic_paper_vars))
    button_list = [button_topic_papers, button_all_papers]
    if access.is_logged_in():
        pick_paper_review_link = A(icon_pick_review, T('Choose paper to review'),
                                   _class='btn btn-primary',
                                   _href=URL('default', 'pick_review', args=[topic_id]))
        button_list.append(pick_paper_review_link)
        add_paper_link = A(icon_add, 'Add a paper', _class='btn btn-danger',
                           _href=URL('default', 'edit_paper', vars=dict(topic=topic_id)))
        button_list.append(add_paper_link)
    return dict(grid=grid,
                button_list=button_list)


def reviewers_topic_grid():
    """Grid containing the reviewers in a topic.
    The grid is done so that it can be easily included in a more complex page.
    The arguments are:
    - topic_id (in path)
    """
    topic = db.topic(request.args(0)) or redirect(URL('default', 'index'))
    q = ((db.reviewer.topic == topic.id) &
         (db.reviewer.user == db.auth_user.id))
    grid = SQLFORM.grid(q,
        args = request.args[:1], # First is topic_id
        orderby=~db.reviewer.reputation,
        field_id=db.reviewer.id,
        fields=[db.reviewer.reputation, db.auth_user.display_name, db.auth_user.affiliation, db.auth_user.link],
        csv=False, details=True,
        create=False, editable=False, deletable=False,
        maxtextlength=48,
    )
    return grid


def paper_review_grid():
    """Grid of reviews for a paper.
    The arguments are:
    - paper_id
    - topic_id (optional)
    """
    paper_id = request.args(0)
    topic_id = request.args(1)
    # If topic_id is None, then uses as topic_id the main topic of the paper.
    if topic_id is None:
        paper = db((db.paper.paper_id == paper_id) &
                   (db.paper.end_date == None)).select().first()
        topic_id = paper.primary_topic
    q = ((db.review.paper_id == paper_id) &
         (db.review.topic == topic_id) &
         (db.review.end_date == None))
    # Retrieves the edit history of reviews.
    def get_review_history(r):
        review_history_len = db((db.review.paper_id == paper_id) &
                                (db.review.topic == topic_id) &
                                (db.review.author == r.author)).count()
        return '' if review_history_len < 2 else A(T('Review history'),
                                                     _href=URL('default', 'review_history',
                                                               args=[paper_id, topic_id, r.author]))
    # Retrieves the version of paper reviewed, if different from current one.
    def get_reviewed_paper(r):
        if r.paper == paper_id:
            return 'Current'
        else:
            return A(T('View'), _href=URL('default', 'view_specific_paper_version', args=[r.paper]))
    links = []
    db.review.paper.readable = False
    # Link to review edit history if any.
    links.append(dict(header='',
                      body=lambda r: get_review_history(r)))
    # Link to actual version of paper reviewed, if different from current one.
    links.append(dict(header='Reviewed version',
                      body=lambda r: get_reviewed_paper(r)))
    edit_review_link=A(T('Edit'), _href=URL('default', 'do_review', args=[paper_id, topic_id]))
    db.review.author.represent = lambda v, r: CAT(B('You'), ' ', SPAN('(', edit_review_link, ')')) if v == auth.user_id else v
    grid = SQLFORM.grid(q,
        args=request.args[:2],
        fields=[db.review.grade, db.review.useful_count, db.review.content,
                db.review.paper_id, db.review.paper, db.review.author, db.review.start_date],
        links=links,
        orderby=~db.review.start_date,
        details=True, csv=False,
        editable=False, deletable=False, create=False,
        maxtextlength=48,
        )
    return grid


def paper_reviews():
    """Returns a list of paper reviews, together if appropriate with a link
    to add one more review."""
    grid = paper_review_grid()
    paper_id = request.args(0)
    button_list = []
    button_review = A(icon_add, T('Write a review'),
                      _class='btn btn-danger',
                      _href=URL('default', 'do_review', args=[paper_id]))
    button_list.append(button_review)
    return dict(grid=grid, button_list=button_list)


def paper_info():
    """Returns information on a paper.
        Arguments:
        - paper_id (in path)
        Optional:
        - topic_id (in path)
        - id=pid (in query) where pid is the id of the paper in the version.
        - date=date (in query) shows the version that was active at a given date.
    """
    paper_id = request.args(0)
    topic_id = request.args(1)
    # If topic_id is None, then uses as topic_id the main topic of the paper.
    if topic_id is None:
        paper = db((db.paper.paper_id == paper_id) &
                   (db.paper.end_date == None)).select().first()
        topic_id = paper.primary_topic
    if request.vars.id is not None:
        paper = db(db.paper.id == id).select().first()
        paper_id = paper.paper_id # For consistency
    elif request.vars.date is not None:
        d = parse_date(request.vars.date)
        paper = db((db.paper.paper_id == paper_id) &
                   (db.paper.start_date <= d) &
                   ((db.paper.end_date == None) | (db.paper.end_date >= d))).select().first()
    else:
        # Selects last paper.
        paper = db((db.paper.paper_id == paper_id) &
                   (db.paper.end_date == None)).select().first()
    # Paper topics, score, and number of reviews.
    all_topics = db((db.paper_in_topic.paper_id == paper_id) &
                    (db.paper_in_topic.end_date == None) &
                    (db.topic.id == db.paper_in_topic.topic)).select()
    secondary_topics=[]
    primary_topic_name = None
    primary_topic = None
    primary_paper_topic = None
    for t in all_topics:
        if t.paper_in_topic.is_primary:
            primary_topic = t.topic
            primary_paper_topic = t.paper_in_topic
            primary_topic_name = represent_paper_topic(primary_topic.name, primary_topic)
        else:
            secondary_topics.append(represent_paper_topic(t.topic.name, t.topic))
    topics_els = [T('Primary topic: '), primary_topic_name]
    if len(secondary_topics) > 0:
        topics_els.append(SPAN(T(' Secondary topics:'), ' ', _class="second_span"))
        topics_els.append(secondary_topics[0])
        for t in secondary_topics[1:]:
            topics_els.extend([SPAN(', '), t])
    topics_span = SPAN(*topics_els)
    # Earliest, and latest dates.
    latest_version_date = represent_date(paper.start_date, paper)
    earliest_paper = db(db.paper.paper_id == paper_id).select(orderby=db.paper.start_date).first()
    first_version_date = earliest_paper.start_date
    return dict(paper=paper,
                topics=topics_span,
                first_version_date=first_version_date,
                latest_version_date=latest_version_date,
                abstract=text_store_read(paper.abstract),
                score=primary_paper_topic.score if primary_paper_topic else None,
                num_reviews=primary_paper_topic.num_reviews if primary_paper_topic else None,
                )

