from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
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

    # Get contract details
    contract_address = contract_info_chain['address']
    contract_abi = contract_info_chain['abi']
    contract_address_other = contract_info_other_chain['address']
    contract_abi_other = contract_info_other_chain['abi']

    # Load account details
    private_key = contract_info_other_chain.get('private_key')
    account_address = contract_info_other_chain.get('public_key')

    if not private_key or not account_address:
        print(f"Missing private_key or public_key in contract_info for '{other_chain}'")
        return

    # Get block range
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
        # Handle Deposit events
        try:
            deposit_filter = contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
            deposit_events = deposit_filter.get_all_entries()
            print(f"Found {len(deposit_events)} Deposit event(s).")
            
            for evt in deposit_events:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']
                
                # Build and send wrap transaction
                try:
                    nonce = w3_other.eth.get_transaction_count(account_address)
                    
                    # Estimate gas for the transaction
                    gas_estimate = contract_other.functions.wrap(
                        token, recipient, amount
                    ).estimate_gas({'from': account_address})
                    
                    gas_price = w3_other.eth.gas_price
                    
                    txn = contract_other.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': w3_other.eth.chain_id,
                        'gas': gas_estimate,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': account_address
                    })
                    
                    signed_txn = w3_other.eth.account.sign_transaction(txn, private_key)
                    tx_hash = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                    
                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print(f"Wrap transaction successful: {tx_hash.hex()}")
                    else:
                        print(f"Wrap transaction failed: {tx_hash.hex()}")
                        
                except Exception as e:
                    print(f"Error processing wrap: {e}")
                    
        except Exception as e:
            print(f"Error processing Deposit events: {e}")
            
    else:  # destination chain
        # Handle Unwrap events
        try:
            unwrap_filter = contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
            unwrap_events = unwrap_filter.get_all_entries()
            print(f"Found {len(unwrap_events)} Unwrap event(s).")
            
            for evt in unwrap_events:
                underlying_token = evt.args['underlying_token']
                to = evt.args['to']
                amount = evt.args['amount']
                
                # Build and send withdraw transaction
                try:
                    nonce = w3_other.eth.get_transaction_count(account_address)
                    
                    # Estimate gas for the transaction
                    gas_estimate = contract_other.functions.withdraw(
                        underlying_token, to, amount
                    ).estimate_gas({'from': account_address})
                    
                    gas_price = w3_other.eth.gas_price
                    
                    txn = contract_other.functions.withdraw(underlying_token, to, amount).build_transaction({
                        'chainId': w3_other.eth.chain_id,
                        'gas': gas_estimate,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': account_address
                    })
                    
                    signed_txn = w3_other.eth.account.sign_transaction(txn, private_key)
                    tx_hash = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
                    
                    receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        print(f"Withdraw transaction successful: {tx_hash.hex()}")
                    else:
                        print(f"Withdraw transaction failed: {tx_hash.hex()}")
                        
                except Exception as e:
                    print(f"Error processing withdraw: {e}")
                    
        except Exception as e:
            print(f"Error processing Unwrap events: {e}")
