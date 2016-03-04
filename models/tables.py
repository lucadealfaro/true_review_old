from datetime import datetime

DATE_FORMAT = '%Y-%m-%d %H:%M %Z'
datetime_validator = IS_LOCALIZED_DATETIME(timezone=pytz.timezone(user_timezone), format=DATE_FORMAT)
FULL_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %Z'
full_datetime_validator = IS_LOCALIZED_DATETIME(timezone=pytz.timezone(user_timezone), format=FULL_DATE_FORMAT)

def represent_date(v, r):
    f = datetime_validator
    return f.formatter(v)

def get_email(u):
    return '' if u is None else (
        '' if u.email is None else
        '<' + u.email + '>'
    )

def represent_author(v, r):
    return format_author(db.auth_user(v))

def format_author(u):
    if u is None:
        return T('N/A')
    s = " ".join([u.first_name, u.last_name, get_email(u)])
    return A(s, _href=u.link)


db.auth_user.format = '%(email)s'

# All db fields of type "text" should in truth contain only the key to a gdb text entry.
# Text is all stored in this table.
# The keyval table can also be used to store random other things.
gdb.define_table('keyval',
                 Field('content', 'blob'))

# Functions for storing text
def text_store_read(k):
    """Reads a keystore value for key k."""
    return gdb.keyval(k).content

def text_store_write(v, key=None):
    """Writes a text store value of v, with key k if specified.  Returns the key."""
    if key is None:
        return gdb.keyval.insert(content=v)
    else:
        kk = int(key)
        gdb.keyval.update_or_insert((gdb.keyval.id == kk), id=kk, content=v)
        return kk

def represent_text_field(v, r):
    return text_store_read(int(v)) if v is not None else ""

db.define_table('topic',
                Field('name'),
                Field('creation_date', 'datetime', default=datetime.utcnow()),
                Field('description', 'text'), # Pointer to text table.
                format = '%(name)s'
                )
represent_paper_topic = lambda v, r: A(v, _href=URL('default', 'topic_index', args=[r.id]))
db.topic.name.represent = represent_paper_topic
db.topic.id.readable = db.topic.id.writable = False
db.topic.creation_date.readable = db.topic.creation_date.writable = False
db.topic.description.represent = represent_text_field

# A paper, which may belong to several topics, and can also be updated in time by its authors.
db.define_table('paper',
                Field('paper_id'), # Identifier of this paper, common to all revisions of this paper.
                Field('title'),
                # Note that we need to list authors here as we find them, as we have
                # no guarantee that they are also system users.
                Field('authors', 'list:string'), # There can be lots of authors.
                Field('primary_topic', 'reference topic'), # Primary topic of the paper.
                Field('abstract', 'text'), # Put the gdb id of the abstract here.
                Field('file'), # This is either a pointer to GCS (or blobstore?), or a link to where the file can be found.
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'), # If this is None, then the record is current.
                format = '%(title)s'
                )
db.paper.id.readable = False
db.paper.paper_id.readable = False
db.paper.abstract.represent = represent_text_field
db.paper.start_date.label = T("Submitted on")
db.paper.end_date.label = T("Current until")
db.paper.end_date.represent = lambda v, r: (T('Current') if v is None else represent_date(v, r))
db.paper.end_date.requires = datetime_validator
db.paper.start_date.represent = represent_date
db.paper.start_date.requires = datetime_validator

def represent_specific_paper_version(pid):
    paper = db.paper(pid)
    return A(paper.title, _href=URL('default', 'view_specific_paper_version', args=[pid]))


# Paper score in topic
db.define_table('paper_in_topic',
                Field('paper_id'),
                Field('topic', 'reference topic'),
                Field('is_primary', 'boolean'), # Is this the primary topic for the paper? If so it can be reviewed.
                Field('score', 'double', default=0),
                Field('num_reviews', 'integer', default=0), # We need to have this info fast, hence the denormalization.
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'), # If this is None, then the record is current.
                )
db.paper_in_topic.is_primary.readable = db.paper_in_topic.is_primary.writable = False
db.paper_in_topic.paper_id.readable = False
represent_paper_score = lambda v, r: "%.2f" % v
db.paper_in_topic.score.represent = represent_paper_score

# This table explains the current roles of a user in a venue.
# The top question is: should this table be split into multiple separate tables,
# for admins, reviewers, authors, etc?
# Also it might mean lots of updates to the same table.
db.define_table('reviewer',
                Field('user', db.auth_user, default=auth.user_id),
                Field('topic', 'reference topic'),
                Field('reputation', 'double', default=0),
                Field('is_reviewer', 'boolean'),
                Field('is_author', 'boolean'),
                Field('is_admin', 'boolean'),
                )

db.define_table('review_application',
                Field('user', db.auth_user, default=auth.user_id),
                Field('topic', 'reference topic'),
                Field('statement', 'text'),
                Field('outcome', 'integer')
                )
OUTCOME_TYPES = [
    (0, 'Pending'),
    (1, 'Approved'),
    (2, 'Rejected'),
]
OUTCOME_TYPES_DICT = dict(OUTCOME_TYPES)
db.review_application.outcome.represent = lambda v, r: OUTCOME_TYPES_DICT.get(v, '')
db.review_application.outcome.requires = IS_IN_SET(OUTCOME_TYPES, zero=0)
db.review_application.outcome.default = 0


# author + paper form a key
db.define_table('review',
                Field('author', db.auth_user, default=auth.user_id),
                Field('paper_id',), # Reference to the paper series of which this is a paper.
                Field('review_id'), # ID of this review through time.  Similar to paper_id for papers.
                Field('paper', 'reference paper'), # A review is of a specific paper instance.
                Field('topic', 'reference topic'), # Strictly speaking useless as can be reconstructed.  Keep?
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'),
                Field('content', 'text'), # Store pointer to text in other db.
                Field('useful_count', 'integer', default=0), # How many times it was found useful.
                Field('grade', 'double'), # Grade assigned by review.
                Field('old_score', 'double'), # Score of the paper at the time the review is initially made.
                )
db.review.author.label = T('Reviewer')
db.review.author.represent = represent_author
db.review.author.writable = False
db.review.review_id.readable = db.review.review_id.writable = False
db.review.paper_id.writable = False
db.review.topic.writable = False
db.review.start_date.writable = db.review.end_date.writable = False
db.review.useful_count.writable = False
db.review.old_score.readable = db.review.old_score.writable = False
db.review.start_date.requires = datetime_validator
db.review.end_date.requires = datetime_validator
db.review.start_date.label = T('Review date')
db.review.content.represent = represent_text_field
db.review.grade.requires = IS_FLOAT_IN_RANGE(0, 10.0)
db.review.grade.label = 'Grade [0..10]'
db.review.paper_id.readable = False
db.review.id.readable = False
db.review.content.label = T('Review')
db.review.end_date.readable = False
