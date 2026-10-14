from tra.privacy.validators import abn_valid, luhn_valid, medicare_valid, tfn_valid


def test_tfn_valid_generated_9_and_8_digit(make_tfn):
    assert all(tfn_valid(make_tfn(9)) for _ in range(200))
    assert all(tfn_valid(make_tfn(8)) for _ in range(200))


def test_tfn_invalid():
    assert tfn_valid("123456789") is False
    assert tfn_valid("12345678") is False
    assert tfn_valid("1234567") is False


def test_tfn_single_digit_change_invalidates(make_tfn):
    changed = invalid = 0
    for _ in range(50):
        tfn = make_tfn()
        for pos in range(9):
            for digit in "0123456789":
                if digit == tfn[pos]:
                    continue
                changed += 1
                invalid += not tfn_valid(tfn[:pos] + digit + tfn[pos + 1:])
    assert invalid / changed >= 0.90


def test_medicare_valid_and_first_digit(make_medicare):
    for _ in range(100):
        number = make_medicare()
        assert medicare_valid(number) is True
        assert medicare_valid("1" + number[1:]) is False
        assert medicare_valid("7" + number[1:]) is False
        wrong_check = str((int(number[8]) + 1) % 10)
        assert medicare_valid(number[:8] + wrong_check + number[9:]) is False
    assert medicare_valid(make_medicare(irn=True)) is True


def test_luhn():
    assert luhn_valid("4111111111111111") is True
    assert luhn_valid("4111111111111112") is False


def test_abn():
    assert abn_valid("51824753556") is True
    assert abn_valid("51824753557") is False


def test_wrong_length_and_non_digits():
    assert tfn_valid("") is False
    assert medicare_valid("212345") is False
    assert abn_valid("5182475355") is False
    assert tfn_valid("12345678a") is False
