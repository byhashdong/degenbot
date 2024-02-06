from degenbot import ChainlinkPriceContract, set_web3
from eth_utils import to_checksum_address


def test_chainlink_feed(ethereum_full_node_web3):
    set_web3(ethereum_full_node_web3)

    # Load WETH price feed
    # ref: https://data.chain.link/ethereum/mainnet/crypto-usd/eth-usd
    weth_price_feed = ChainlinkPriceContract(
        to_checksum_address("0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419")
    )
    assert isinstance(weth_price_feed.update_price(), float)
