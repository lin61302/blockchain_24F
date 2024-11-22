from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"

# Standard ERC20 ABI (only the functions we need)
ERC20_ABI = [
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
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return

    other_chain = 'destination' if chain == 'source' else 'source'
    
    w3 = connectTo(chain)
    w3_other = connectTo(other_chain)

    if w3 is None or w3_other is None:
        print("Failed to connect to one or both chains.")
        return

    contract_info_chain = getContractInfo(chain)
    contract_info_other_chain = getContractInfo(other_chain)

    contract_address = Web3.to_checksum_address(contract_info_chain['address'])
    contract_abi = contract_info_chain['abi']
    contract_address_other = Web3.to_checksum_address(contract_info_other_chain['address'])
    contract_abi_other = contract_info_other_chain['abi']

    private_key = contract_info_other_chain.get('private_key')
    account_address = Web3.to_checksum_address(contract_info_other_chain.get('public_key'))

    if not private_key or not account_address:
        print(f"Missing private_key or public_key in contract_info for '{other_chain}'")
        return

    latest_block = w3.eth.block_number
    start_block = max(0, latest_block - 5)
    end_block = latest_block

    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

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

    if chain == 'source':
        # Handle Deposit events and call wrap() on destination chain
        try:
            event_filter = contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Deposit event(s).")

            for evt in events:
                token = Web3.to_checksum_address(evt.args['token'])
                recipient = Web3.to_checksum_address(evt.args['recipient'])
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()
                print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}, tx_hash={tx_hash}")

                try:
                    nonce = w3_other.eth.get_transaction_count(account_address)
                    gas_price = w3_other.eth.gas_price

                    txn = contract_other.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': w3_other.eth.chain_id,
                        'gas': 200000,  # Increased gas limit for wrap function
                        'gasPrice': min(gas_price, 10000000000),  # 10 Gwei cap
                        'nonce': nonce,
                    })

                    signed_txn = w3_other.eth.account.sign_transaction(txn, private_key)
                    tx_hash_sent = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"wrap() transaction sent on {other_chain}: tx_hash={tx_hash_sent.hex()}")

                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash_sent.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash_sent.hex()}")

                except Exception as e:
                    print(f"Failed to send wrap() transaction: {e}")

        except Exception as e:
            print(f"Error processing Deposit events: {e}")

    else:
        # Handle Unwrap events and transfer underlying tokens on source chain
        try:
            event_filter = contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
            events = event_filter.get_all_entries()
            print(f"Found {len(events)} Unwrap event(s).")

            for evt in events:
                underlying_token = Web3.to_checksum_address(evt.args['underlying_token'])
                wrapped_token = Web3.to_checksum_address(evt.args['wrapped_token'])
                frm = Web3.to_checksum_address(evt.args['frm'])
                to = Web3.to_checksum_address(evt.args['to'])
                amount = evt.args['amount']
                tx_hash = evt.transactionHash.hex()

                print(f"Found Unwrap event: underlying_token={underlying_token}, wrapped_token={wrapped_token}, frm={frm}, to={to}, amount={amount}, tx_hash={tx_hash}")

                try:
                    # Connect to the source chain
                    w3_source = connectTo(other_chain)
                    if w3_source is None:
                        print("Failed to connect to source chain.")
                        continue

                    # Load the underlying ERC20 token contract on the source chain
                    token_contract = w3_source.eth.contract(address=underlying_token, abi=ERC20_ABI)

                    # Build transaction to transfer underlying tokens to the recipient
                    nonce = w3_source.eth.get_transaction_count(account_address)
                    gas_price = w3_source.eth.gas_price

                    txn = token_contract.functions.transfer(to, amount).build_transaction({
                        'chainId': w3_source.eth.chain_id,
                        'gas': 100000,  # Adjust gas limit as needed
                        'gasPrice': min(gas_price, 10000000000),  # 10 Gwei cap
                        'nonce': nonce,
                    })

                    # Sign the transaction
                    signed_txn = w3_source.eth.account.sign_transaction(txn, private_key)
                    tx_hash_sent = w3_source.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Underlying token transfer transaction sent on {other_chain}: tx_hash={tx_hash_sent.hex()}")

                    # Wait for the transaction receipt
                    receipt = w3_source.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
                    if receipt.status == 1:
                        print(f"Transaction successful: {tx_hash_sent.hex()}")
                    else:
                        print(f"Transaction failed: {tx_hash_sent.hex()}")

                except Exception as e:
                    print(f"Failed to transfer underlying token: {e}")

        except Exception as e:
            print(f"Error processing Unwrap events: {e}")
