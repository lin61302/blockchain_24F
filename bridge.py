from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"

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
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return

    other_chain = 'destination' if chain == 'source' else 'source'
    
    # Connect to both chains
    w3 = connectTo(chain)
    w3_other = connectTo(other_chain)

    if w3 is None or w3_other is None:
        print("Failed to connect to one or both chains.")
        return

    # Load contract info
    contract_info_chain = getContractInfo(chain)
    contract_info_other_chain = getContractInfo(other_chain)

    # Get contract addresses and ABIs
    contract_address = contract_info_chain['address']
    contract_abi = contract_info_chain['abi']
    contract_address_other = contract_info_other_chain['address']
    contract_abi_other = contract_info_other_chain['abi']

    # Load private key and account address
    private_key = contract_info_other_chain.get('private_key')
    account_address = contract_info_other_chain.get('public_key')

    if not private_key or not account_address:
        print(f"Missing private_key or public_key in contract_info for '{other_chain}'")
        return

    # Get latest block number
    latest_block = w3.eth.block_number
    start_block = max(0, latest_block - 5)
    end_block = latest_block

    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    # Initialize contracts
    try:
        contract = w3.eth.contract(address=contract_address, abi=contract_abi)
        contract_other = w3_other.eth.contract(address=contract_address_other, abi=contract_abi_other)
    except Exception as e:
        print(f"Error loading contracts: {e}")
        return

    if chain == 'source':
        try:
            event_filter = contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Deposit event(s).")

            for evt in events:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()
                print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}, tx_hash={tx_hash}")

                try:
                    nonce = w3_other.eth.get_transaction_count(account_address)
                    gas_price = min(20_000_000_000, w3_other.eth.gas_price)  # Cap at 20 Gwei

                    # Build wrap transaction
                    txn = contract_other.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': w3_other.eth.chain_id,
                        'gas': 200000,  # Lower gas limit
                        'gasPrice': gas_price,
                        'nonce': nonce,
                    })

                    signed_txn = w3_other.eth.account.sign_transaction(txn, private_key)
                    tx_hash = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"wrap() transaction sent on {other_chain}: tx_hash={tx_hash.hex()}")

                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Failed to send wrap() transaction: {e}")

        except Exception as e:
            print(f"Error creating event filter for 'Deposit': {e}")
            return

    else:  # chain == 'destination'
        try:
            event_filter = contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Unwrap event(s).")

            for evt in events:
                underlying_token = evt.args['underlying_token']
                to = evt.args['to']
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()

                try:
                    nonce = w3_other.eth.get_transaction_count(account_address)
                    gas_price = min(20_000_000_000, w3_other.eth.gas_price)  # Cap at 20 Gwei

                    # Build withdraw transaction
                    txn = contract_other.functions.withdraw(underlying_token, to, amount).build_transaction({
                        'chainId': w3_other.eth.chain_id,
                        'gas': 200000,  # Lower gas limit
                        'gasPrice': gas_price,
                        'nonce': nonce,
                    })

                    signed_txn = w3_other.eth.account.sign_transaction(txn, private_key)
                    tx_hash = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"withdraw() transaction sent on {other_chain}: tx_hash={tx_hash.hex()}")

                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash.hex()}")

                except Exception as e:
                    print(f"Failed to send withdraw() transaction: {e}")

        except Exception as e:
            print(f"Error creating event filter for 'Unwrap': {e}")
            return
