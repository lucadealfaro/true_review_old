This repository contains the code of the true_review web2py app. 

Do not clone this repository directly. 
Rather, clone the repository for true_review_web2py, at https://github.com/lucadealfaro/true_review_web2py
This repository will then be included as a submodule.

To create the test database, a temporary hack is necessary due to a problem we are investigating:
- Drop the old test database true_review_test;
- Modify line 62 of db.py replacing migrate_enabled=False with migrate_enabled=True;
- Access the URL /dbupdate . It should produce an "ok" output.
- Modify line 62 of db.py replacing migrate_enabled=True with migrate_enabled=False;
