from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path
import traceback

contract_info = "contract_info.json"

# Standard ERC20 ABI (only the transfer function)
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
    """
    Connect to the specified blockchain network.
    """
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    elif chain == 'destination':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet
    else:
        print(f"Invalid chain: {chain}")
        return None

    w3 = Web3(Web3.HTTPProvider(api_url))
    if not w3.isConnected():
        print(f"Failed to connect to {chain} chain at {api_url}")
        return None
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def getContractInfo(chain):
    """
    Load the contract information from 'contract_info.json'.
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

def get_revert_reason(w3, tx_hash):
    """
    Retrieve the revert reason from a failed transaction.
    """
    try:
        tx = w3.eth.get_transaction(tx_hash)
        tx_receipt = w3.eth.get_transaction_receipt(tx_hash)
        if tx_receipt.status == 1:
            return None  # Transaction succeeded

        # Attempt to call the transaction to get the revert reason
        try:
            w3.eth.call(tx, block_identifier=tx_receipt.blockNumber)
        except Exception as e:
            revert_reason = str(e)
            return revert_reason
    except Exception as e:
        print(f"Error retrieving revert reason: {e}")
        traceback.print_exc()
        return "Unknown revert reason"

def scanBlocks(chain):
    """
    Scan the latest blocks for relevant events and execute corresponding functions.
    """
    print(f"\n=== Starting scanBlocks for {chain} chain ===")
    
    # Connect to both chains
    source_w3 = connectTo('source')
    dest_w3 = connectTo('destination')

    if source_w3 is None or dest_w3 is None:
        print("Failed to connect to one or both chains.")
        return

    # Get contract info
    source_info = getContractInfo('source')
    dest_info = getContractInfo('destination')

    # Initialize contracts with checksum addresses
    try:
        source_contract = source_w3.eth.contract(
            address=Web3.to_checksum_address(source_info['address']),
            abi=source_info['abi']
        )
    except Exception as e:
        print(f"Error loading source contract: {e}")
        traceback.print_exc()
        return

    try:
        dest_contract = dest_w3.eth.contract(
            address=Web3.to_checksum_address(dest_info['address']),
            abi=dest_info['abi']
        )
    except Exception as e:
        print(f"Error loading destination contract: {e}")
        traceback.print_exc()
        return

    # Define WARDEN accounts and keys for both chains
    source_warden = Web3.to_checksum_address(source_info['public_key'])
    source_private_key = source_info.get('private_key')
    
    dest_warden = Web3.to_checksum_address(dest_info['public_key'])
    dest_private_key = dest_info.get('private_key')

    # Print WARDEN addresses to verify separation
    print(f"Source WARDEN Address: {source_warden}")
    print(f"Destination WARDEN Address: {dest_warden}")

    # Check if WARDEN accounts are the same
    if source_warden.lower() == dest_warden.lower():
        print("Warning: Source and Destination WARDEN addresses are the same. It's recommended to use separate accounts for each chain.")
    
    if not source_private_key or not dest_private_key:
        print(f"Missing private_key in contract_info for 'source' or 'destination'")
        return

    if chain == 'source':
        # Handle Deposit events: wrap on destination chain
        current_block = source_w3.eth.block_number
        start_block = max(0, current_block - 5)
        end_block = current_block
        print(f"Scanning blocks {start_block} - {end_block} on source")
    
        try:
            deposits = source_contract.events.Deposit.create_filter(
                fromBlock=start_block,
                toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(deposits)} Deposit event(s)")
            for evt in deposits:
                try:
                    token = Web3.to_checksum_address(evt.args['token'])
                    recipient = Web3.to_checksum_address(evt.args['recipient'])
                    amount = evt.args['amount']
                    tx_hash = evt.transactionHash.hex()
                    print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}, tx_hash={tx_hash}")

                    # Build wrap transaction on destination chain
                    nonce = dest_w3.eth.get_transaction_count(dest_warden)
                    gas_price = dest_w3.eth.gas_price
                    gas_price = min(gas_price, 10_000_000_000)  # 10 Gwei cap

                    print(f"Preparing to send wrap transaction:")
                    print(f"  From (destination WARDEN): {dest_warden}")
                    print(f"  Token: {token}")
                    print(f"  Recipient: {recipient}")
                    print(f"  Amount: {amount}")
                    print(f"  Gas Price: {gas_price}")
                    print(f"  Nonce: {nonce}")

                    txn = dest_contract.functions.wrap(
                        token,
                        recipient,
                        amount
                    ).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,  # Increased gas limit for wrap function
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': dest_warden
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, dest_private_key)
                    tx_hash_sent = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Wrap tx sent on destination chain: {tx_hash_sent.hex()}")

                    # Wait for receipt
                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
                    if receipt.status == 1:
                        print(f"Wrap transaction successful: {tx_hash_sent.hex()}")
                    else:
                        print(f"Wrap transaction failed: {tx_hash_sent.hex()}")
                        # Attempt to get revert reason
                        revert_reason = get_revert_reason(dest_w3, tx_hash_sent)
                        print(f"Revert Reason: {revert_reason}")

        except Exception as e:
            print(f"Error scanning deposits: {e}")
            traceback.print_exc()

    else:  # chain == 'destination'
        # Handle Unwrap events: transfer underlying tokens on source chain
        current_block = dest_w3.eth.block_number
        start_block = max(0, current_block - 5)
        end_block = current_block
        print(f"Scanning blocks {start_block} - {end_block} on destination")

        try:
            unwraps = dest_contract.events.Unwrap.create_filter(
                fromBlock=start_block,
                toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(unwraps)} Unwrap event(s)")
            for evt in unwraps:
                try:
                    underlying_token = Web3.to_checksum_address(evt.args['underlying_token'])
                    to = Web3.to_checksum_address(evt.args['to'])
                    amount = evt.args['amount']
                    frm = Web3.to_checksum_address(evt.args['frm'])

                    print(f"\nProcessing Unwrap:")
                    print(f"  From: {frm}")
                    print(f"  To: {to}")
                    print(f"  Token: {underlying_token}")
                    print(f"  Amount: {amount}")

                    # Initialize the underlying ERC20 token contract on the source chain
                    underlying_token_contract = source_w3.eth.contract(
                        address=underlying_token,
                        abi=ERC20_ABI
                    )

                    # Check source WARDEN token balance
                    balance = underlying_token_contract.functions.balanceOf(source_warden).call()
                    print(f"  Source WARDEN token balance: {balance}")

                    if balance < amount:
                        print(f"  Insufficient token balance. Required: {amount}, Available: {balance}")
                        continue

                    # Build transaction to transfer underlying tokens to 'to' on source chain
                    nonce = source_w3.eth.get_transaction_count(source_warden)
                    gas_price = source_w3.eth.gas_price
                    gas_price = min(gas_price, 10_000_000_000)  # 10 Gwei cap

                    print(f"  Preparing to send transfer transaction:")
                    print(f"    From (source WARDEN): {source_warden}")
                    print(f"    To: {to}")
                    print(f"    Amount: {amount}")
                    print(f"    Gas Price: {gas_price}")
                    print(f"    Nonce: {nonce}")

                    txn = underlying_token_contract.functions.transfer(
                        to,
                        amount
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 100000,  # Adjust gas limit as needed
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'from': source_warden
                    })

                    # Sign the transaction
                    signed_txn = source_w3.eth.account.sign_transaction(txn, source_private_key)
                    tx_hash_sent = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"  Transfer tx sent on source chain: {tx_hash_sent.hex()}")

                    # Wait for receipt
                    receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
                    if receipt.status == 1:
                        print(f"  Transfer transaction successful: {tx_hash_sent.hex()}")
                    else:
                        print(f"  Transfer transaction failed: {tx_hash_sent.hex()}")
                        # Attempt to get revert reason
                        revert_reason = get_revert_reason(source_w3, tx_hash_sent)
                        print(f"  Revert Reason: {revert_reason}")

                except Exception as e:
                    print(f"Error processing withdrawal: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"Error scanning unwraps: {e}")
            traceback.print_exc()
