from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"
WARDEN_ROLE = "0xa95a5379b182f9ab2dea1336b28c22442227353b86d7e0a968f68d98add11c07"

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

    private_key = source_info.get('private_key')
    account_address = source_info.get('public_key')

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
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']

                print(f"\nProcessing Deposit: recipient={recipient}")
                
                try:
                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    gas_price = min(dest_w3.eth.gas_price, 10000000000)

                    txn = dest_contract.functions.wrap(
                        token,
                        recipient,
                        amount
                    ).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': account_address
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Wrap transaction sent: {tx_hash.hex()}")

                    # Wait for receipt just to be sure
                    dest_w3.eth.wait_for_transaction_receipt(tx_hash)

                except Exception as e:
                    print(f"Error in wrap: {e}")

        except Exception as e:
            print(f"Error in source chain processing: {e}")

    else:  # destination chain processing
        current_block = dest_w3.eth.block_number
        start_block = max(0, current_block - 5)
        end_block = current_block

        print(f"Scanning blocks {start_block} - {end_block} on destination chain")
        
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

                    print(f"\nProcessing Unwrap: from={frm}, to={to}")

                    # Build and send withdraw transaction
                    nonce = source_w3.eth.get_transaction_count(account_address)
                    gas_price = min(source_w3.eth.gas_price, 10000000000)

                    txn = source_contract.functions.withdraw(
                        underlying_token,  # Use underlying token address
                        to,               # Send to the recipient from unwrap event
                        amount           # Use the same amount
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': account_address
                    })

                    signed_txn = source_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Withdraw transaction sent: {tx_hash.hex()}")

                    # Wait for receipt just to be sure
                    source_w3.eth.wait_for_transaction_receipt(tx_hash)

                except Exception as e:
                    print(f"Error in withdraw: {e}")

        except Exception as e:
            print(f"Error in destination chain processing: {e}")
