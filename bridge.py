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
    
    # Connect to chains and get info
    source_w3 = connectTo('source')
    dest_w3 = connectTo('destination')
    
    source_info = getContractInfo('source')
    dest_info = getContractInfo('destination')
    
    source_contract = source_w3.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = dest_w3.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    # Account setup
    if chain == 'source':
        key_info = dest_info  # For wrapping, we need destination keys
    else:
        key_info = source_info  # For unwrapping, we need source keys

    private_key = key_info.get('private_key')
    account_address = key_info.get('public_key')
    print(f"Active account: {account_address}")

    # Get block range
    current_block = source_w3.eth.block_number if chain == 'source' else dest_w3.eth.block_number
    start_block = max(0, current_block - 5)
    end_block = current_block
    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    if chain == 'source':
        # Handle Deposit -> Wrap flow
        try:
            deposits = source_contract.events.Deposit.create_filter(
                fromBlock=start_block, 
                toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(deposits)} Deposit event(s).")
            for evt in deposits:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']
                print(f"\nProcessing Deposit:")
                print(f"Token: {token}")
                print(f"Recipient: {recipient}")
                print(f"Amount: {amount}")

                try:
                    # Verify warden role
                    has_role = dest_contract.functions.hasRole(WARDEN_ROLE, account_address).call()
                    print(f"Has WARDEN_ROLE on destination: {has_role}")

                    # Send wrap transaction
                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    gas_price = dest_w3.eth.gas_price
                    
                    txn = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(gas_price, 10000000000),
                        'nonce': nonce,
                        'from': account_address
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Wrap transaction sent: {tx_hash.hex()}")

                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print("Wrap transaction successful")
                    else:
                        print("Wrap transaction failed")

                except Exception as e:
                    print(f"Error in wrap: {str(e)}")

        except Exception as e:
            print(f"Error handling deposits: {str(e)}")

    else:  # destination chain
        # Handle Unwrap -> Withdraw flow
        try:
            unwraps = dest_contract.events.Unwrap.create_filter(
                fromBlock=start_block, 
                toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(unwraps)} Unwrap event(s).")
            for evt in unwraps:
                try:
                    underlying_token = evt.args['underlying_token']
                    wrapped_token = evt.args['wrapped_token']
                    from_address = evt.args['frm']
                    to_address = evt.args['to']
                    amount = evt.args['amount']

                    print(f"\nProcessing Unwrap:")
                    print(f"From: {from_address}")
                    print(f"To: {to_address}")
                    print(f"Underlying token: {underlying_token}")
                    print(f"Wrapped token: {wrapped_token}")
                    print(f"Amount: {amount}")

                    # Verify warden role
                    has_role = source_contract.functions.hasRole(WARDEN_ROLE, account_address).call()
                    print(f"Has WARDEN_ROLE on source: {has_role}")

                    if has_role:
                        nonce = source_w3.eth.get_transaction_count(account_address)
                        gas_price = source_w3.eth.gas_price

                        txn = source_contract.functions.withdraw(
                            underlying_token,
                            to_address,
                            amount
                        ).build_transaction({
                            'chainId': source_w3.eth.chain_id,
                            'gas': 200000,
                            'gasPrice': min(gas_price, 10000000000),
                            'nonce': nonce,
                            'from': account_address
                        })

                        signed_txn = source_w3.eth.account.sign_transaction(txn, private_key)
                        tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                        print(f"Withdraw transaction sent: {tx_hash.hex()}")

                        receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                        if receipt.status == 1:
                            print("Withdraw transaction successful")
                        else:
                            print("Withdraw transaction failed")
                    else:
                        print("Account doesn't have WARDEN_ROLE, skipping withdrawal")

                except Exception as e:
                    print(f"Error processing unwrap: {str(e)}")

        except Exception as e:
            print(f"Error scanning unwraps: {str(e)}")

    print("=== scanBlocks completed ===")
