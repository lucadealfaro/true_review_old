from datetime import datetime

# All db fields of type "text" should in truth contain only the key to a gdb text entry.
# Text is all stored in this table.
# The keyval table can also be used to store random other things.
gdb.define_table('keyval',
                 Field('content', 'blob'))

db.define_table('person',
                Field('email'), # This is the key
                Field('name'), # Name to be used for display purposes.
                Field('affiliation'),
                Field('link', requires=IS_URL()), # Url associated with user profile
                Field('blurb', 'text', requires=IS_LENGTH(250)), # This is a profile blurb shown together with the person.
                # We should have really a more complete user profile, but this will suffice for now.
                )
db.person.name.represent = lambda v, r: A(v, _href=r.link)


db.define_table('topic',
                Field('name'),
                Field('creation_date', 'datetime', default=datetime.utcnow()),
                Field('description', 'text'),
                )
db.topic.name.represent = lambda v, r: A(v, _href=URL('default', 'topic', args=[r.id]))
db.topic.id.readable = db.topic.id.writable = False
db.topic.creation_date.readable = db.topic.creation_date.writable = False

# A paper, which may belong to several topics, and can also be updated in time by its authors.
db.define_table('paper',
                Field('paper_id'), # Identifier of this paper, common to all revisions of this paper.
                Field('title'),
                # Note that we need to list authors here as we find them, as we have
                # no guarantee that they are also system users.
                Field('authors', 'list:string'), # There can be lots of authors.
                Field('abstract', 'text'), # Put the gdb id of the abstract here.
                Field('file'), # This is either a pointer to GCS (or blobstore?), or a link to where the file can be found.
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'), # If this is None, then the record is current.
                )

# Paper score in topic
db.define_table('paper_in_topic',
                Field('paper_id'),
                Field('topic', 'reference topic'),
                Field('num_reviews', 'integer', default=0), # We need to have this info fast, hence the denormalization.
                Field('score', 'double', default=0),
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'), # If this is None, then the record is current.
                )

# This table explains the current roles of a user in a venue.
# The top question is: should this table be split into multiple separate tables,
# for admins, reviewers, authors, etc?
# Also it might mean lots of updates to the same table.
db.define_table('reviewer',
                Field('user', 'reference person'),
                Field('topic', 'reference topic'),
                Field('reputation', 'double'),
                Field('is_reviewer', 'boolean'),
                Field('is_author', 'boolean'),
                Field('is_admin', 'boolean'),
                )

db.define_table('review_application',
                Field('user', 'reference person'),
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
                Field('author', 'reference person'),
                Field('paper', 'reference paper'),
                Field('topic', 'reference topic'), # Strictly speaking useless as can be reconstructed.  Keep?
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'),
                Field('content', 'text'),
                Field('useful_count', 'integer'), # How many times it was found useful.
                Field('grade', 'double'), # Grade assigned by review.
                Field('old_score', 'double'), # Score of the paper at the time the review is initially made.
                )
