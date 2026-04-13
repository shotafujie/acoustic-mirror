"""Sprint 0: Verify project structure and imports."""


def test_import_acoustic_mirror():
    import acoustic_mirror

    assert hasattr(acoustic_mirror, "__doc__")


def test_import_subpackages():
    import acoustic_mirror.audio
    import acoustic_mirror.analysis
    import acoustic_mirror.feedback
    import acoustic_mirror.dashboard

    assert acoustic_mirror.audio is not None
    assert acoustic_mirror.analysis is not None
    assert acoustic_mirror.feedback is not None
    assert acoustic_mirror.dashboard is not None
