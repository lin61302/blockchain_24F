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

    # We always need the source account for withdraw
    source_account = source_info.get('public_key')
    source_key = source_info.get('private_key')

    start_block = 0
    end_block = 0

    if chain == 'source':
        end_block = source_w3.eth.block_number
        start_block = max(0, end_block - 5)
        
        try:
            event_filter = source_contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Deposit event(s).")

            for evt in events:
                try:
                    txn = dest_contract.functions.wrap(
                        evt.args['token'],
                        evt.args['recipient'],
                        evt.args['amount']
                    ).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(dest_w3.eth.gas_price, 10000000000),
                        'nonce': dest_w3.eth.get_transaction_count(source_account)
                    })

                    signed = dest_w3.eth.account.sign_transaction(txn, source_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed.rawTransaction)
                    print(f"Wrap transaction sent: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Error sending wrap: {e}")
                    
        except Exception as e:
            print(f"Error processing deposits: {e}")

    else:  # destination chain
        end_block = dest_w3.eth.block_number
        start_block = max(0, end_block - 5)

        try:
            event_filter = dest_contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Unwrap event(s).")

            for evt in events:
                try:
                    # Directly call withdraw on source contract
                    txn = source_contract.functions.withdraw(
                        evt.args['underlying_token'],
                        evt.args['to'],
                        evt.args['amount']
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(source_w3.eth.gas_price, 10000000000),
                        'nonce': source_w3.eth.get_transaction_count(source_account)
                    })

                    signed = source_w3.eth.account.sign_transaction(txn, source_key)
                    tx_hash = source_w3.eth.send_raw_transaction(signed.rawTransaction)
                    print(f"Withdraw transaction sent: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Error sending withdraw: {e}")

        except Exception as e:
            print(f"Error processing unwraps: {e}")
