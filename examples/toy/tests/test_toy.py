from toy import clamp


def test_middle():
    assert clamp(5, 0, 10) == 5

