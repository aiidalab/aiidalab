def test_imports():
    """Test that most important modules can be imported

    This is just a basic smoke test.
    """
    # ruff: noqa: F401

    import aiidalab
    import aiidalab.__main__
    import aiidalab.app
    import aiidalab.config
    import aiidalab.utils
