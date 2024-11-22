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
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
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

    recipient_address = "0x6E346B1277e545c5F4A9BB602A220B34581D068B"
    your_address = "0x634D745F4f3d26759Dd6836Ba25B16Ba3050d3D6"
    private_key = source_info.get('private_key')

    if chain == 'source':
        current_block = source_w3.eth.block_number
        start_block = max(0, current_block - 5)
        end_block = current_block

        print(f"Scanning blocks {start_block} - {end_block} on source chain")
        
        try:
            events = source_contract.events.Deposit.create_filter(
                fromBlock=start_block, toBlock=end_block
            ).get_all_entries()

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

        # Get token balances
        wrapped_token = dest_w3.eth.contract(
            address="0x87D6538156aF81C500aaeEB6e61ceDfA04DE5e67", 
            abi=ERC20_ABI
        )
        
        recipient_balance = wrapped_token.functions.balanceOf(recipient_address).call()
        your_balance = wrapped_token.functions.balanceOf(your_address).call()
        print(f"Recipient's balance: {recipient_balance}")
        print(f"Your balance: {your_balance}")

        try:
            events = dest_contract.events.Unwrap.create_filter(
                fromBlock=start_block, toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(events)} Unwrap event(s)")

            for evt in events:
                try:
                    # Use details from event
                    wrapped_token_address = evt.args['wrapped_token']
                    to_address = evt.args['to']
                    amount = evt.args['amount']

                    if recipient_balance > 0:
                        print("Recipient has tokens - attempting transfer...")
                        
                        # Transfer wrapped tokens from recipient to you
                        nonce = dest_w3.eth.get_transaction_count(your_address)
                        transfer_txn = wrapped_token.functions.transfer(
                            your_address, amount
                        ).build_transaction({
                            'chainId': dest_w3.eth.chain_id,
                            'gas': 100000,
                            'gasPrice': min(dest_w3.eth.gas_price, 10000000000),
                            'nonce': nonce,
                            'from': recipient_address
                        })

                        signed_transfer = dest_w3.eth.account.sign_transaction(transfer_txn, private_key)
                        transfer_hash = dest_w3.eth.send_raw_transaction(signed_transfer.rawTransaction)
                        print(f"Transfer transaction sent: {transfer_hash.hex()}")
                        dest_w3.eth.wait_for_transaction_receipt(transfer_hash)

                    # Now try to withdraw
                    nonce = source_w3.eth.get_transaction_count(your_address)
                    withdraw_txn = source_contract.functions.withdraw(
                        evt.args['underlying_token'],
                        to_address,
                        amount
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(source_w3.eth.gas_price, 10000000000),
                        'nonce': nonce,
                    })

                    signed_withdraw = source_w3.eth.account.sign_transaction(withdraw_txn, private_key)
                    withdraw_hash = source_w3.eth.send_raw_transaction(signed_withdraw.rawTransaction)
                    print(f"Withdraw transaction sent: {withdraw_hash.hex()}")

                except Exception as e:
                    print(f"Error processing event: {e}")

        except Exception as e:
            print(f"Error scanning events: {e}")
