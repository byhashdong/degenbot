# noqa: A005

import dataclasses

from degenbot.types import AbstractPoolState


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class BalancerV2PoolState(AbstractPoolState):
    balances: list[int]
