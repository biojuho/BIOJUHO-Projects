"""Workspace-level pytest configuration.

getdaytrends has a bare ``models`` module that collides with
biolinker/models.py when both are collected in the same pytest process.
Run getdaytrends tests separately::

    python -m pytest getdaytrends/tests/ -q
"""
collect_ignore_glob = ["getdaytrends/tests/*"]
