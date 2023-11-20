from itertools import cycle
from typing import Iterable, List, Union

import eth_abi
from eth_typing import ChecksumAddress
from eth_utils.address import to_checksum_address
from web3 import Web3
from hexbytes import HexBytes


def decode_v3_path(path: bytes) -> List[Union[ChecksumAddress, int]]:
    """
    Decode the `path` byte string used by the Uniswap V3 Router/Router2 contracts.
    `path` is a close-packed encoding of pool addresses (20 bytes) and fees
    (3 bytes).
    """

    path_pos = 0
    decoded_path: List[Union[ChecksumAddress, int]] = []

    # read alternating 20 and 3 byte chunks from the encoded path,
    # store each address (hex string) and fee (int)
    for byte_length, extraction_func in cycle(
        (
            (20, lambda chunk: to_checksum_address(chunk)),
            (3, lambda chunk: int.from_bytes(chunk)),
        ),
    ):
        chunk = HexBytes(path[path_pos : path_pos + byte_length])
        decoded_path.append(extraction_func(chunk))

        path_pos += byte_length

        if path_pos == len(path):
            break

    return decoded_path


def generate_v3_pool_address(
    token_addresses: Iterable[str],
    fee: int,
    factory_address: str,
    init_hash: str,
) -> ChecksumAddress:
    """
    Generate the deterministic pool address from the token addresses and fee.

    Adapted from https://github.com/Uniswap/v3-periphery/blob/main/contracts/libraries/PoolAddress.sol
    """

    token_addresses = sorted([address.lower() for address in token_addresses])

    return to_checksum_address(
        Web3.keccak(
            hexstr="0xff"
            + factory_address[2:]
            + Web3.keccak(
                eth_abi.encode(
                    types=("address", "address", "uint24"),
                    args=(*token_addresses, fee),
                )
            ).hex()[2:]
            + init_hash[2:]
        )[12:]
    )
