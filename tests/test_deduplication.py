from survey_deduplication.cli import chunks


def test_chunks_preserves_order():
    assert list(chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]