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
    # Connect to both chains
    source_w3 = connectTo('source')
    dest_w3 = connectTo('destination')

    if not source_w3 or not dest_w3:
        print("Failed to connect to chains.")
        return

    # Load contract info for both chains
    source_info = getContractInfo('source')
    dest_info = getContractInfo('destination')

    # Initialize contracts
    source_contract = source_w3.eth.contract(
        address=source_info['address'],
        abi=source_info['abi']
    )
    dest_contract = dest_w3.eth.contract(
        address=dest_info['address'],
        abi=dest_info['abi']
    )

    # Get the key for sending transactions
    if chain == 'source':
        key_info = dest_info  # For wrapping, we need destination keys
    else:
        key_info = source_info  # For unwrapping, we need source keys

    private_key = key_info.get('private_key')
    account_address = key_info.get('public_key')

    if not private_key or not account_address:
        print(f"Missing private_key or public_key in contract_info")
        return

    # Get block range to scan
    if chain == 'source':
        current_block = source_w3.eth.block_number
    else:
        current_block = dest_w3.eth.block_number

    start_block = max(0, current_block - 5)
    end_block = current_block
    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    if chain == 'source':
        # Handle Deposit -> Wrap flow
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
                print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}, tx_hash={tx_hash}")

                try:
                    # Check if we have WARDEN_ROLE on destination
                    has_role = dest_contract.functions.hasRole(WARDEN_ROLE, account_address).call()
                    if not has_role:
                        print(f"Account {account_address} doesn't have WARDEN_ROLE on destination chain")
                        continue

                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    gas_price = dest_w3.eth.gas_price

                    # Build wrap transaction
                    txn = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(gas_price, 10000000000),
                        'nonce': nonce,
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"wrap() transaction sent on destination: tx_hash={tx_hash.hex()}")

                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Failed to send wrap() transaction: {e}")

        except Exception as e:
            print(f"Error processing Deposit events: {e}")

    else:
        # Handle Unwrap -> Withdraw flow
        try:
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

                try:
                    # Check if we have WARDEN_ROLE on source
                    has_role = source_contract.functions.hasRole(WARDEN_ROLE, account_address).call()
                    if not has_role:
                        print(f"Account {account_address} doesn't have WARDEN_ROLE on source chain")
                        continue

                    nonce = source_w3.eth.get_transaction_count(account_address)
                    gas_price = source_w3.eth.gas_price

                    # Build withdraw transaction
                    txn = source_contract.functions.withdraw(
                        underlying_token,  # Use underlying token address
                        to,               # Use recipient from event
                        amount           # Use amount from event
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(gas_price, 10000000000),
                        'nonce': nonce,
                        'from': account_address
                    })

                    signed_txn = source_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"withdraw() transaction sent on source: tx_hash={tx_hash.hex()}")

                    receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Failed to send withdraw() transaction: {e}")

        except Exception as e:
            print(f"Error processing Unwrap events: {e}")
