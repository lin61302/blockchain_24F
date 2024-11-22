from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware  # Necessary for POA chains
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"

def connectTo(chain):
    """
    Connect to the blockchain network based on the chain identifier ('source' or 'destination').
    """
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    elif chain == 'destination':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet
    else:
        print(f"Invalid chain: {chain}")
        return None

    w3 = Web3(Web3.HTTPProvider(api_url))
    # Inject the POA compatibility middleware to the innermost layer
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # Optionally, print connection status
    print(f"Attempting to connect to {chain} network...")
    # if w3.isConnected():
    #     print(f"Successfully connected to {chain} network.")
    # else:
    #     print(f"Failed to connect to {chain} network.")
    return w3

def getContractInfo(chain):
    """
    Load the contract_info file into a dictionary.
    This function is used by the autograder and will likely be useful to you.
    """
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
    """
    Scan the last 5 blocks of the source or destination chain for relevant events
    and execute corresponding functions (wrap or withdraw).
    """
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return

    # Determine the other chain
    other_chain = 'destination' if chain == 'source' else 'source'

    # Connect to both chains
    w3 = connectTo(chain)
    w3_other = connectTo(other_chain)

    if w3 is None or w3_other is None:
        print("Failed to connect to one or both chains.")
        return

    # Load contract info for both chains
    contract_info_chain = getContractInfo(chain)
    contract_info_other_chain = getContractInfo(other_chain)

    # Get contract addresses and ABIs
    contract_address = contract_info_chain['address']
    contract_abi = contract_info_chain['abi']

    contract_address_other = contract_info_other_chain['address']
    contract_abi_other = contract_info_other_chain['abi']

    # Load private key and account address for signing transactions on the other chain
    private_key = contract_info_other_chain.get('private_key')
    account_address = contract_info_other_chain.get('public_key')

    if not private_key or not account_address:
        print(f"Missing private_key or public_key in contract_info for '{other_chain}'")
        return

    # Get the latest block number on the chain
    try:
        latest_block = w3.eth.block_number
    except Exception as e:
        print(f"Error fetching latest block number on {chain}: {e}")
        return

    # Set the block range to scan
    start_block = latest_block - 5 if latest_block >= 5 else 0
    end_block = latest_block

    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    # Load the contracts
    try:
        contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    except Exception as e:
        print(f"Error loading contract on {chain}: {e}")
        return

    try:
        contract_other = w3_other.eth.contract(address=contract_address_other, abi=contract_abi_other)
    except Exception as e:
        print(f"Error loading contract on {other_chain}: {e}")
        return

    # Depending on the chain, look for specific events
    if chain == 'source':
        # Look for 'Deposit' events
        try:
            event_filter = contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Deposit event(s).")
        except Exception as e:
            print(f"Error creating event filter for 'Deposit': {e}")
            return

        for evt in events:
            # Get event data
            try:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()
                print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}, tx_hash={tx_hash}")
            except KeyError as e:
                print(f"Missing event argument: {e}")
                continue

            try:
                # Now, call wrap() function on the destination chain
                nonce = w3_other.eth.get_transaction_count(account_address)
                gas_price = 10_000_000_000  # 10 Gwei in Wei
                txn = contract_other.functions.wrap(token, recipient, amount).build_transaction({
                    'chainId': w3_other.eth.chain_id,
                    'gas': 500000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                })
                print(f"Built wrap() transaction: {txn}")

                # Sign transaction
                signed_txn = w3_other.eth.account.sign_transaction(txn, private_key=private_key)
                print(f"Signed wrap() transaction.")

                # Send transaction
                tx_hash_sent = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                print(f"wrap() transaction sent on {other_chain}: tx_hash={tx_hash_sent.hex()}")

                # Optional: Wait for receipt and check status
                try:
                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash_sent.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash_sent.hex()}")
                except Exception as e:
                    print(f"Error waiting for transaction receipt: {e}")

            except Exception as e:
                print(f"Failed to send wrap() transaction: {e}")

    else:
        # chain == 'destination'
        # Look for 'Unwrap' events
        try:
            event_filter = contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Unwrap event(s).")
        except Exception as e:
            print(f"Error creating event filter for 'Unwrap': {e}")
            return

        for evt in events:
            # Get event data
            try:
                underlying_token = evt.args['underlying_token']
                wrapped_token = evt.args['wrapped_token']
                frm = evt.args['frm']
                to = evt.args['to']
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()
                print(f"Found Unwrap event: underlying_token={underlying_token}, wrapped_token={wrapped_token}, frm={frm}, to={to}, amount={amount}, tx_hash={tx_hash}")
            except KeyError as e:
                print(f"Missing event argument: {e}")
                continue

            try:
                # Now, call withdraw() function on the source chain
                nonce = w3_other.eth.get_transaction_count(account_address)
                gas_price = 10_000_000_000  # 10 Gwei in Wei
                txn = contract_other.functions.withdraw(underlying_token, to, amount).build_transaction({
                    'chainId': w3_other.eth.chain_id,
                    'gas': 500000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                })
                print(f"Built withdraw() transaction: {txn}")

                # Sign transaction
                signed_txn = w3_other.eth.account.sign_transaction(txn, private_key=private_key)
                print(f"Signed withdraw() transaction.")

                # Send transaction
                tx_hash_sent = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                print(f"withdraw() transaction sent on {other_chain}: tx_hash={tx_hash_sent.hex()}")

                # Optional: Wait for receipt and check status
                try:
                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash_sent.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash_sent.hex()}")
                except Exception as e:
                    print(f"Error waiting for transaction receipt: {e}")

            except Exception as e:
                print(f"Failed to send withdraw() transaction: {e}")
