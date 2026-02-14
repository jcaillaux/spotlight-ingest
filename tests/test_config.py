from config import *

def test_repo_host():
    assert SPOTLIGHT_REPO is not None
    assert isinstance(SPOTLIGHT_REPO, str)