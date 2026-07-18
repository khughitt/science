"""Reusable status-vs-reality core: probe a record's promised deliverables against
the tree, adjudicate a lifecycle state deterministically, and sign the evidence.

Extracted from the frozen `drift_sample` study so production checks and the study
share ONE definition (design §4.1). The study's statistics stay in `drift_sample`.
"""
