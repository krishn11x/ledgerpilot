"""Pluggable matching rules, one module per cascade pass.

Each rule implements ``MatchRule`` (see ``base``) so the engine can order,
enable, disable and benchmark them independently. Adding a new matching
strategy means adding a module here -- the engine does not change.

    exact      pass 1  hard reference key join
    tolerance  pass 2  amount within epsilon + date window
    fuzzy      pass 3  blocking, scoring, threshold + margin
    aggregate  pass 4  N:1 payout batch to bank credit
"""
