"""Ingest: get external data in, and make it comparable.

PLACEHOLDER package. Three responsibilities, kept separate:

    loaders    read CSV/JSON/Parquet into typed domain records
    normalize  canonicalise so records from different systems can be compared
    validate   enforce schema contracts; quarantine bad rows rather than crash

Normalisation is where a surprising amount of match rate is won or lost. Two
records that refer to the same payment can differ in date format, currency
representation, reference casing, and narration whitespace -- fix that before
matching and the deterministic passes do far more work.
"""
