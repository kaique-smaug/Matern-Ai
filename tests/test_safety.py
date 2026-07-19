from materai_rag.safety import assess_safety


def test_detects_emergency_signal() -> None:
    result = assess_safety("Estou com sangramento intenso e muita dor")
    assert result.emergency is True


def test_normal_question_is_not_emergency() -> None:
    result = assess_safety("Quais exames são feitos no segundo trimestre?")
    assert result.emergency is False
