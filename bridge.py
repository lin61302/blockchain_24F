from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"
WARDEN_ROLE = "0xa95a5379b182f9ab2dea1336b28c22442227353b86d7e0a968f68d98add11c07"
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

def connectTo(chain):
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'destination':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        print(f"Invalid chain: {chain}")
        return None

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def getContractInfo(chain):
    p = Path(__file__).with_name(contract_info)
    try:
        with p.open('r') as f:
            contracts = json.load(f)
    except Exception as e:
        print("Failed to read contract info")
        print("Please contact your instructor")
        print(e)
        sys.exit(1)

    if chain not in contracts:
        print(f"Chain '{chain}' not found in contract_info.json")
        sys.exit(1)

    return contracts[chain]

def scanBlocks(chain):
    print(f"\n=== Starting scanBlocks for {chain} chain ===")
    
    source_w3 = connectTo('source')
    dest_w3 = connectTo('destination')

    source_info = getContractInfo('source')
    dest_info = getContractInfo('destination')

    source_contract = source_w3.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = dest_w3.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    your_address = "0x634D745F4f3d26759Dd6836Ba25B16Ba3050d3D6"  # Your MetaMask address
    private_key = source_info.get('private_key')
    WRAPPED_TOKEN = "0x87D6538156aF81C500aaeEB6e61ceDfA04DE5e67"  # Known wrapped token

    if chain == 'source':
        current_block = source_w3.eth.block_number
        start_block = max(0, current_block - 5)
        end_block = current_block

        print(f"Scanning blocks {start_block} - {end_block} on source chain")
        
        try:
            deposit_filter = source_contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
            events = deposit_filter.get_all_entries()
            print(f"Found {len(events)} Deposit event(s)")

            for evt in events:
                try:
                    nonce = dest_w3.eth.get_transaction_count(your_address)
                    gas_price = min(dest_w3.eth.gas_price, 10000000000)

                    txn = dest_contract.functions.wrap(
                        evt.args['token'],
                        evt.args['recipient'],
                        evt.args['amount']
                    ).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': your_address
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Wrap transaction sent: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Error in wrap: {e}")

        except Exception as e:
            print(f"Error in deposits: {e}")

    else:  # destination chain
        current_block = dest_w3.eth.block_number
        start_block = max(0, current_block - 5)
        end_block = current_block

        print(f"Scanning blocks {start_block} - {end_block} on destination chain")

        # Check balances
        wrapped_token = dest_w3.eth.contract(address=WRAPPED_TOKEN, abi=ERC20_ABI)
        balance = wrapped_token.functions.balanceOf("0x6E346B1277e545c5F4A9BB602A220B34581D068B").call()
        print(f"Recipient's wrapped token balance: {balance}")
        my_balance = wrapped_token.functions.balanceOf(your_address).call()
        print(f"Your wrapped token balance: {my_balance}")
        
        try:
            unwrap_filter = dest_contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
            events = unwrap_filter.get_all_entries()
            print(f"Found {len(events)} Unwrap event(s)")

            for evt in events:
                try:
                    underlying_token = evt.args['underlying_token']
                    wrapped_token = evt.args['wrapped_token']
                    frm = evt.args['frm']
                    to = evt.args['to']
                    amount = evt.args['amount']

                    print(f"Processing Unwrap:")
                    print(f"From: {frm}")
                    print(f"To: {to}")
                    print(f"Underlying: {underlying_token}")
                    print(f"Wrapped: {wrapped_token}")
                    print(f"Amount: {amount}")

                    nonce = source_w3.eth.get_transaction_count(your_address)
                    gas_price = min(source_w3.eth.gas_price, 10000000000)

                    txn = source_contract.functions.withdraw(
                        underlying_token,
                        to,
                        amount
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': your_address
                    })

                    signed_txn = source_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Withdraw transaction sent: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Error in withdraw: {e}")

        except Exception as e:
            print(f"Error in unwraps: {e}")
