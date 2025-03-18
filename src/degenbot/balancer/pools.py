from fractions import Fraction
from threading import Lock
from typing import cast

import eth_abi.abi
from eth_typing import BlockNumber, ChecksumAddress

from degenbot.balancer.libraries.fixed_point import mulUp
from degenbot.balancer.libraries.scaling_helpers import (
    _computeScalingFactor,
    _downscaleDown,
    _upscale,
    _upscaleArray,
)
from degenbot.balancer.libraries.weighted_math import _calcOutGivenIn, _subtractSwapFeeAmount
from degenbot.balancer.types import BalancerV2PoolState
from degenbot.cache import get_checksum_address
from degenbot.config import connection_manager
from degenbot.erc20_token import Erc20Token
from degenbot.functions import encode_function_calldata
from degenbot.managers.erc20_token_manager import Erc20TokenManager
from degenbot.types import AbstractLiquidityPool, PublisherMixin


class BalancerV2Pool(PublisherMixin, AbstractLiquidityPool):
    type PoolState = BalancerV2PoolState
    FEE_DENOMINATOR = 1 * 10**18

    def __init__(
        self,
        address: ChecksumAddress | str,
        *,
        chain_id: int | None = None,
        state_block: int | None = None,
        verify_address: bool = True,
        silent: bool = False,
    ):
        self.address = get_checksum_address(address)

        self._chain_id = chain_id if chain_id is not None else connection_manager.default_chain_id
        w3 = connection_manager.get_web3(self.chain_id)
        state_block = (
            cast("BlockNumber", state_block) if state_block is not None else w3.eth.block_number
        )

        pool_id: bytes
        (pool_id,) = eth_abi.abi.decode(
            types=["bytes32"],
            data=w3.eth.call(
                transaction={
                    "to": self.address,
                    "data": encode_function_calldata(
                        function_prototype="getPoolId()",
                        function_arguments=None,
                    ),
                },
                block_identifier=state_block,
            ),
        )
        self.pool_id = pool_id
        self.pool_specialization = int.from_bytes(self.pool_id[20:22], byteorder="big")

        vault_address: str
        (vault_address,) = eth_abi.abi.decode(
            types=["address"],
            data=w3.eth.call(
                transaction={
                    "to": self.address,
                    "data": encode_function_calldata(
                        function_prototype="getVault()",
                        function_arguments=None,
                    ),
                },
                block_identifier=state_block,
            ),
        )
        self.vault = get_checksum_address(vault_address)

        tokens: list[str]
        balances: list[int]
        tokens, balances, _ = eth_abi.abi.decode(
            types=["address[]", "uint256[]", "uint256"],
            data=w3.eth.call(
                transaction={
                    "to": self.vault,
                    "data": encode_function_calldata(
                        function_prototype="getPoolTokens(bytes32)",
                        function_arguments=[self.pool_id],
                    ),
                },
                block_identifier=state_block,
            ),
        )

        token_manager = Erc20TokenManager(chain_id=self.chain_id)
        self.tokens = tuple(
            [
                token_manager.get_erc20token(
                    address=get_checksum_address(token),
                    silent=silent,
                )
                for token in tokens
            ]
        )
        self.scaling_factors = tuple([_computeScalingFactor(token) for token in self.tokens])

        self._state_lock = Lock()
        self._state = BalancerV2PoolState(
            address=self.address,
            block=state_block,
            balances=balances,
        )

        (fee,) = eth_abi.abi.decode(
            types=["uint256"],
            data=w3.eth.call(
                transaction={
                    "to": self.address,
                    "data": encode_function_calldata(
                        function_prototype="getSwapFeePercentage()",
                        function_arguments=None,
                    ),
                },
                block_identifier=state_block,
            ),
        )
        self.fee = Fraction(fee, self.FEE_DENOMINATOR)

        (weights,) = eth_abi.abi.decode(
            types=["uint256[]"],
            data=w3.eth.call(
                transaction={
                    "to": self.address,
                    "data": encode_function_calldata(
                        function_prototype="getNormalizedWeights()",
                        function_arguments=None,
                    ),
                },
                block_identifier=state_block,
            ),
        )
        self.weights = tuple(weights)

    @property
    def balances(self) -> list[int]:
        return self.state.balances

    @property
    def chain_id(self) -> int:
        return self._chain_id

    @property
    def state(self) -> PoolState:
        return self._state

    def calculate_tokens_out_from_tokens_in(
        self,
        token_in: Erc20Token,
        token_in_quantity: int,
        token_out: Erc20Token,
        override_state: PoolState | None = None,
    ) -> int:
        token_in_index = self.tokens.index(token_in)
        token_out_index = self.tokens.index(token_out)

        fee_amount = mulUp(token_in_quantity, self.fee * self.FEE_DENOMINATOR)

        amount_new = _subtractSwapFeeAmount(
            amount=token_in_quantity,
            fee_percentage=self.fee * self.FEE_DENOMINATOR,
        )

        assert token_in_quantity - fee_amount == amount_new

        balances = self.balances.copy()
        _upscaleArray(balances, scalingFactors=self.scaling_factors)
        amount_new = _upscale(amount_new, scalingFactor=self.scaling_factors[token_in_index])

        amountOut = _calcOutGivenIn(
            balanceIn=int(balances[token_in_index]),
            weightIn=self.weights[token_in_index],
            balanceOut=int(balances[token_out_index]),
            weightOut=self.weights[token_out_index],
            amountIn=int(amount_new),
        )

        return int(
            _downscaleDown(amount=amountOut, scalingFactor=self.scaling_factors[token_out_index])
        )
