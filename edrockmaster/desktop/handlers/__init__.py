"""The interface's calls, one handler per context (ADR 0041).

Each handler checks a request of the page, runs the work on the core thread
through the ``CoreContext``, and answers or applies the notifications. Handlers
know neither the window nor one another.
"""
