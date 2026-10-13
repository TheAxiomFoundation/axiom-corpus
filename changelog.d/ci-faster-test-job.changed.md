CI's test job runs the tests in four processes (`pytest-xdist`, a file's
tests in one process), fetches only the base commit to install the artifact
guard, and checks the repository out with every commit but file contents on
demand; the 5.7 GB history holds the corpus bytes from before the lock
switch. The checks are unchanged.
