"""Worker entry points — Producer / Consumer / Saver.

Each worker is an independent process. Restarting one MUST NOT impact the
others; that is the load-bearing contract M0-S3 commits to.
"""

