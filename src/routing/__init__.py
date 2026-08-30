"""Adaptive routing. Owned by Chuba.

An explicit route() pipeline operation is not part of interface freeze v1 (M5).
Until then, temporary routing may live behind generate_representation or match
and may read PairCharacterization. Do not add route() to the frozen pipeline.
"""
