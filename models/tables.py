from datetime import datetime

# All db fields of type "text" should in truth contain only the key to a gdb text entry.
# Text is all stored in this table.
# The keyval table can also be used to store random other things.
gdb.define_table('keyval',
                 Field('content', 'blob'))

db.define_table('user',
                Field('email'), # This is the key
                Field('affiliation'),
                Field('link', requires=IS_URL()), # Url associated with user profile
                Field('blurb', 'text', requires=IS_LENGTH(250)), # This is a profile blurb shown together with the person.
                # We should have really a more complete user profile, but this will suffice for now.
                )

db.define_table('topic',
                Field('name'),
                Field('creation_date', 'datetime', default=datetime.utcnow()),
                Field('description', 'text'),
                )

# Many tables, among which paper, are versioned by having both a start_date and an end_date for the validity
# of an entry.  The data is current iff end_date is None.
db.define_table('paper',
                Field('paper_id'), # Identifier of this paper, common to all revisions of this paper.
                Field('topic', 'reference topic'),
                Field('title'),
                # Note that we need to list authors here as we find them, as we have
                # no guarantee that they are also system users.
                Field('authors', 'list:string'), # There can be lots of authors.
                Field('abstract', 'text'), # Put the gdb id of the abstract here.
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'), # If this is None, then the record is current.
                Field('file'), # This is either a pointer to GCS (or blobstore?), or a link to where the file can be found.
                Field('num_reviews', 'integer'), # We need to have this info fast, hence the denormalization.
                Field('score', 'double'),
                )

# This table explains the current roles of a user in a venue.
# The top question is: should this table be split into multiple separate tables,
# for admins, reviewers, authors, etc?
# Also it might mean lots of updates to the same table.
db.define_table('role',
                Field('user', 'reference user'),
                Field('topic', 'reference topic'),
                Field('is_reviewer', 'boolean'),
                Field('is_author', 'boolean'),
                Field('is_admin', 'boolean'),
                )

# user + topic form a key
db.define_table('review_score_history',
                Field('user', 'reference user'),
                Field('topic', 'reference topic'),
                Field('review_score', 'double'),
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'), # if empty, info is current.
                )

# author + paper form a key
db.define_table('review',
                Field('author', 'reference user'),
                Field('paper', 'reference paper'),
                Field('topic', 'reference topic'), # Strictly speaking useless as can be reconstructed.  Keep?
                Field('start_date', 'datetime', default=datetime.utcnow()),
                Field('end_date', 'datetime'),
                Field('content', 'text'),
                Field('useful_count', 'integer'), # How many times it was found useful.
                Field('score', 'double'), # Score of review.
                )
