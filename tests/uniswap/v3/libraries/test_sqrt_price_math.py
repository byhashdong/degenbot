from decimal import Decimal, getcontext

import pytest

from degenbot.constants import MAX_UINT128, MAX_UINT256, MIN_UINT128
from degenbot.exceptions import EVMRevertError
from degenbot.uniswap.v3_libraries.sqrt_price_math import (
    get_amount0_delta,
    get_amount1_delta,
    get_next_sqrt_price_from_input,
    get_next_sqrt_price_from_output,
)

# Adapted from Typescript tests on Uniswap V3 Github repo
# ref: https://github.com/Uniswap/v3-core/blob/main/test/SqrtPriceMath.spec.ts


getcontext().prec = (
    40
    # Match the decimal places value specified in Uniswap tests
    # ref: https://github.com/Uniswap/v3-core/blob/d8b1c635c275d2a9450bd6a78f3fa2484fef73eb/test/shared/utilities.ts#L60
)

getcontext().rounding = (
    # Change the rounding method to match the BigNumber rounding mode "3",
    # which is 'ROUND_FLOOR' per https://mikemcl.github.io/bignumber.js/#bignumber
    # ref: https://github.com/Uniswap/v3-core/blob/d8b1c635c275d2a9450bd6a78f3fa2484fef73eb/test/shared/utilities.ts#L69
    "ROUND_FLOOR"
)


def expandTo18Decimals(x: int):
    return x * 10**18


def encodePriceSqrt(reserve1: int, reserve0: int) -> int:
    """
    Returns the sqrt price as a Q64.96 value
    """
    return int((Decimal(reserve1) / Decimal(reserve0)).sqrt() * Decimal(2**96))


def test_getNextSqrtPriceFromInput():
    # fails if price is zero
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_input(0, 0, expandTo18Decimals(1) // 10, False)

    # fails if liquidity is zero
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_input(1, 0, expandTo18Decimals(1) // 10, True)

    # fails if input amount overflows the price
    price = 2**160 - 1
    liquidity = 1024
    amountIn = 1024
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_input(price, liquidity, amountIn, False)

    # any input amount cannot underflow the price
    price = 1
    liquidity = 1
    amountIn = 2**255
    assert get_next_sqrt_price_from_input(price, liquidity, amountIn, True) == 1

    # returns input price if amount in is zero and zeroForOne = true
    price = encodePriceSqrt(1, 1)
    assert get_next_sqrt_price_from_input(price, expandTo18Decimals(1) // 10, 0, True) == price

    # returns input price if amount in is zero and zeroForOne = false
    price = encodePriceSqrt(1, 1)
    assert get_next_sqrt_price_from_input(price, expandTo18Decimals(1) // 10, 0, False) == price

    # returns the minimum price for max inputs
    sqrtP = 2**160 - 1
    liquidity = MAX_UINT128
    maxAmountNoOverflow = MAX_UINT256 - ((liquidity << 96) // sqrtP)
    assert get_next_sqrt_price_from_input(sqrtP, liquidity, maxAmountNoOverflow, True) == 1

    # input amount of 0.1 token1
    sqrtQ = get_next_sqrt_price_from_input(
        encodePriceSqrt(1, 1),
        expandTo18Decimals(1),
        expandTo18Decimals(1) // 10,
        False,
    )
    assert sqrtQ == 87150978765690771352898345369

    # input amount of 0.1 token0
    sqrtQ = get_next_sqrt_price_from_input(
        encodePriceSqrt(1, 1),
        expandTo18Decimals(1),
        expandTo18Decimals(1) // 10,
        True,
    )
    assert sqrtQ == 72025602285694852357767227579

    # amountIn > type(uint96).max and zeroForOne = true
    assert (
        get_next_sqrt_price_from_input(encodePriceSqrt(1, 1), expandTo18Decimals(10), 2**100, True)
        == 624999999995069620
    )
    # perfect answer: https://www.wolframalpha.com/input/?i=624999999995069620+-+%28%281e19+*+1+%2F+%281e19+%2B+2%5E100+*+1%29%29+*+2%5E96%29

    # can return 1 with enough amountIn and zeroForOne = true
    assert get_next_sqrt_price_from_input(encodePriceSqrt(1, 1), 1, MAX_UINT256 // 2, True) == 1


def test_getNextSqrtPriceFromOutput():
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(0, 0, expandTo18Decimals(1) // 10, False)

    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(1, 0, expandTo18Decimals(1) // 10, True)

    price = 20282409603651670423947251286016
    liquidity = 1024
    amountOut = 4
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(price, liquidity, amountOut, False)

    price = 20282409603651670423947251286016
    liquidity = 1024
    amountOut = 5
    with pytest.raises(EVMRevertError):
        # this test should fail
        assert get_next_sqrt_price_from_output(price, liquidity, amountOut, False)

    price = 20282409603651670423947251286016
    liquidity = 1024
    amountOut = 262145
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(price, liquidity, amountOut, True)

    price = 20282409603651670423947251286016
    liquidity = 1024
    amountOut = 262144
    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(price, liquidity, amountOut, True)

    price = 20282409603651670423947251286016
    liquidity = 1024
    amountOut = 262143
    sqrtQ = get_next_sqrt_price_from_output(price, liquidity, amountOut, True)
    assert sqrtQ == 77371252455336267181195264

    price = 20282409603651670423947251286016
    liquidity = 1024
    amountOut = 4

    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(price, liquidity, amountOut, False)

    price = encodePriceSqrt(1, 1)
    assert get_next_sqrt_price_from_output(price, expandTo18Decimals(1) // 10, 0, True) == price

    price = encodePriceSqrt(1, 1)
    assert get_next_sqrt_price_from_output(price, expandTo18Decimals(1) // 10, 0, False) == price

    sqrtQ = get_next_sqrt_price_from_output(
        encodePriceSqrt(1, 1),
        expandTo18Decimals(1),
        expandTo18Decimals(1) // 10,
        False,
    )
    assert sqrtQ == 88031291682515930659493278152

    sqrtQ = get_next_sqrt_price_from_output(
        encodePriceSqrt(1, 1),
        expandTo18Decimals(1),
        expandTo18Decimals(1) // 10,
        True,
    )
    assert sqrtQ == 71305346262837903834189555302

    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(encodePriceSqrt(1, 1), 1, MAX_UINT256, True)

    with pytest.raises(EVMRevertError):
        # this test should fail
        get_next_sqrt_price_from_output(encodePriceSqrt(1, 1), 1, MAX_UINT256, False)


def test_getAmount0Delta():
    with pytest.raises(EVMRevertError):
        get_amount0_delta(0, 0, 0, True)

    with pytest.raises(EVMRevertError):
        get_amount0_delta(1, 0, 0, True)

    with pytest.raises(EVMRevertError):
        get_amount0_delta(1, 0, MAX_UINT128 + 1)

    amount0 = get_amount0_delta(encodePriceSqrt(1, 1), encodePriceSqrt(2, 1), 0, True)
    assert amount0 == 0

    amount0 = get_amount0_delta(encodePriceSqrt(1, 1), encodePriceSqrt(1, 1), 0, True)
    assert amount0 == 0

    amount0 = get_amount0_delta(
        encodePriceSqrt(1, 1),
        encodePriceSqrt(121, 100),
        expandTo18Decimals(1),
        True,
    )
    assert amount0 == 90909090909090910

    amount0RoundedDown = get_amount0_delta(
        encodePriceSqrt(1, 1),
        encodePriceSqrt(121, 100),
        expandTo18Decimals(1),
        False,
    )
    assert amount0RoundedDown == amount0 - 1

    amount0Up = get_amount0_delta(
        encodePriceSqrt(2**90, 1),
        encodePriceSqrt(2**96, 1),
        expandTo18Decimals(1),
        True,
    )
    amount0Down = get_amount0_delta(
        encodePriceSqrt(2**90, 1),
        encodePriceSqrt(2**96, 1),
        expandTo18Decimals(1),
        False,
    )
    assert amount0Up == amount0Down + 1


def test_getAmount1Delta():
    get_amount1_delta(0, 1, MAX_UINT128 - 1, False)
    get_amount1_delta(1, 0, MAX_UINT128 - 1, False)
    get_amount1_delta(0, 1, MAX_UINT128 - 1, True)
    get_amount1_delta(1, 0, MAX_UINT128 - 1, True)

    get_amount1_delta(0, 0, MIN_UINT128 - 1)
    get_amount1_delta(0, 0, MIN_UINT128 - 1)

    amount1 = get_amount1_delta(encodePriceSqrt(1, 1), encodePriceSqrt(2, 1), 0, True)
    assert amount1 == 0

    amount1 = get_amount0_delta(encodePriceSqrt(1, 1), encodePriceSqrt(1, 1), 0, True)
    assert amount1 == 0

    # returns 0.1 amount1 for price of 1 to 1.21
    amount1 = get_amount1_delta(
        encodePriceSqrt(1, 1),
        encodePriceSqrt(121, 100),
        expandTo18Decimals(1),
        True,
    )
    assert amount1 == 100000000000000000

    amount1RoundedDown = get_amount1_delta(
        encodePriceSqrt(1, 1),
        encodePriceSqrt(121, 100),
        expandTo18Decimals(1),
        False,
    )
    assert amount1RoundedDown == amount1 - 1


def test_swap_computation():
    sqrtP = 1025574284609383690408304870162715216695788925244
    liquidity = 50015962439936049619261659728067971248
    zeroForOne = True
    amountIn = 406

    sqrtQ = get_next_sqrt_price_from_input(sqrtP, liquidity, amountIn, zeroForOne)
    assert sqrtQ == 1025574284609383582644711336373707553698163132913

    amount0Delta = get_amount0_delta(sqrtQ, sqrtP, liquidity, True)
    assert amount0Delta == 406
