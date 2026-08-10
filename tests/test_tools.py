from src.tools import calculator, word_count


def test_calculator_basic():
    assert calculator("2 + 2") == "4"


def test_calculator_precedence():
    assert calculator("2 + 3 * 4") == "14"


def test_calculator_rejects_invalid_expression():
    assert calculator("__import__('os')").startswith("Error")


def test_word_count():
    assert word_count("hola mundo") == "2 palabras, 10 caracteres"
