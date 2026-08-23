"""Synthetic data generation with ground truth.

PLACEHOLDER package.

The generator does not merely produce plausible data -- it injects breaks from a
declared specification and records the correct answer for every one. That is
what turns a demo into a measurable system: because ground truth is known, the
evaluation harness can report real precision, recall and false-positive rates
rather than anecdotes.

    generator   happy-path chain: orders -> gateway -> payouts -> bank
    breaks      break injectors, each emitting a ground-truth label
    scenarios   named, reproducible datasets for demos and regression tests

Everything is seeded. The same seed always produces the same dataset, so a
match-rate change is always attributable to a code change and never to data
luck.
"""
