CI's test job runs the tests in four processes (`pytest-xdist`, a file's
tests in one process) and fetches only the base commit to install the
artifact guard, instead of cloning the repository's 5.7 GB history. The test
session creates the default app's SQLite tables once, before the workers
start. The checks are unchanged.
