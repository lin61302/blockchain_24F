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
    
    # Connect to both chains
    source_w3 = connectTo('source')
    dest_w3 = connectTo('destination')
    print("Connected to both chains successfully")

    # Load contract info
    source_info = getContractInfo('source')
    dest_info = getContractInfo('destination')
    print(f"Loaded contract info. Source address: {source_info['address']}, Dest address: {dest_info['address']}")

    # Initialize contracts
    source_contract = source_w3.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = dest_w3.eth.contract(address=dest_info['address'], abi=dest_info['abi'])
    print("Initialized both contracts")

    # Get account info
    if chain == 'source':
        key_info = dest_info
        print("Using destination chain keys for wrap operation")
    else:
        key_info = source_info
        print("Using source chain keys for withdraw operation")

    private_key = key_info.get('private_key')
    account_address = key_info.get('public_key')
    print(f"Using account: {account_address}")

    # Get block range
    if chain == 'source':
        current_block = source_w3.eth.block_number
    else:
        current_block = dest_w3.eth.block_number

    start_block = max(0, current_block - 5)
    end_block = current_block
    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    if chain == 'source':
        try:
            deposit_filter = source_contract.events.Deposit.create_filter(
                fromBlock=start_block, 
                toBlock=end_block
            )
            events = deposit_filter.get_all_entries()
            print(f"Found {len(events)} Deposit event(s).")

            for evt in events:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()
                print(f"\nProcessing Deposit: token={token}, recipient={recipient}, amount={amount}")

                try:
                    print(f"Checking WARDEN_ROLE for {account_address} on destination")
                    has_role = dest_contract.functions.hasRole(WARDEN_ROLE, account_address).call()
                    print(f"Has WARDEN_ROLE on destination: {has_role}")

                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    gas_price = dest_w3.eth.gas_price

                    print("Building wrap transaction...")
                    txn = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(gas_price, 10000000000),
                        'nonce': nonce,
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"wrap() transaction sent: {tx_hash.hex()}")

                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    print(f"Transaction status: {'success' if receipt.status == 1 else 'failed'}")

                except Exception as e:
                    print(f"Error in wrap process: {e}")

        except Exception as e:
            print(f"Error in Deposit processing: {e}")

    else:  # destination chain
        try:
            print("\n=== Looking for Unwrap events ===")
            unwrap_filter = dest_contract.events.Unwrap.create_filter(
                fromBlock=start_block, 
                toBlock=end_block
            )
            events = unwrap_filter.get_all_entries()
            print(f"Found {len(events)} Unwrap event(s).")

            for evt in events:
                underlying_token = evt.args['underlying_token']
                wrapped_token = evt.args['wrapped_token']
                to = evt.args['to']
                amount = evt.args['amount']
                print(f"\nProcessing Unwrap event:")
                print(f"Underlying token: {underlying_token}")
                print(f"Wrapped token: {wrapped_token}")
                print(f"Recipient: {to}")
                print(f"Amount: {amount}")

                try:
                    print(f"\nChecking WARDEN_ROLE for {account_address} on source")
                    has_role = source_contract.functions.hasRole(WARDEN_ROLE, account_address).call()
                    print(f"Has WARDEN_ROLE on source: {has_role}")

                    if not has_role:
                        print("ERROR: Account doesn't have WARDEN_ROLE, skipping withdraw")
                        continue

                    nonce = source_w3.eth.get_transaction_count(account_address)
                    gas_price = source_w3.eth.gas_price
                    print(f"Nonce: {nonce}, Gas price: {gas_price}")

                    print("Building withdraw transaction...")
                    txn = source_contract.functions.withdraw(
                        underlying_token,
                        to,
                        amount
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(gas_price, 10000000000),
                        'nonce': nonce,
                        'from': account_address
                    })
                    print("Transaction built successfully")

                    print("Signing transaction...")
                    signed_txn = source_w3.eth.account.sign_transaction(txn, private_key)
                    
                    print("Sending withdraw transaction...")
                    tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"withdraw() transaction sent: {tx_hash.hex()}")

                    print("Waiting for receipt...")
                    receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    print(f"Transaction status: {'success' if receipt.status == 1 else 'failed'}")

                except Exception as e:
                    print(f"Error in withdraw process: {str(e)}")
                    print(f"Error type: {type(e)}")

        except Exception as e:
            print(f"Error in Unwrap processing: {str(e)}")
            print(f"Error type: {type(e)}")

    print("\n=== scanBlocks completed ===")
