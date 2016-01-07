
db.define_table

db.define_table('paper',
                Field('title'),
                Field('abstract', 'text'), # Put the gdb id of the abstract here.
                Field('date', 'datetime'),

                )