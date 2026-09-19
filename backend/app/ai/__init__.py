"""SAHAYATA AI layer.

Design principles (see docs/ARCHITECTURE.md):
- Every inference is recorded in ai_predictions with provider/model/version.
- Local scikit-learn models work fully offline; external providers are optional
  and configured via environment variables only.
- Any failure degrades gracefully: reports are still accepted and can be
  triaged manually.
"""
