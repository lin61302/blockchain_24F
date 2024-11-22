from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"
WARDEN_ROLE = "0xa95a5379b182f9ab2dea1336b28c22442227353b86d7e0a968f68d98add11c07"

# ERC20 token ABI for approve
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
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
    print(f"\n=== Starting scanBlocks for {chain} chain ===")
    
    source_w3 = connectTo('source')
    dest_w3 = connectTo('destination')

    source_info = getContractInfo('source')
    dest_info = getContractInfo('destination')

    source_contract = source_w3.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = dest_w3.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    if chain == 'source':
        private_key = dest_info.get('private_key')
        account_address = dest_info.get('public_key')
        current_block = source_w3.eth.block_number
    else:
        private_key = source_info.get('private_key')
        account_address = source_info.get('public_key')
        current_block = dest_w3.eth.block_number

    start_block = max(0, current_block - 5)
    end_block = current_block
    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    if chain == 'source':
        try:
            deposits = source_contract.events.Deposit.create_filter(
                fromBlock=start_block, toBlock=end_block).get_all_entries()
            
            print(f"Found {len(deposits)} Deposit event(s)")
            for evt in deposits:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']

                print(f"\nProcessing Deposit:")
                print(f"Token: {token}")
                print(f"Recipient: {recipient}")
                print(f"Amount: {amount}")

                try:
                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    gas_price = min(dest_w3.eth.gas_price, 10000000000)

                    txn = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': gas_price,
                        'nonce': nonce
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Wrap transaction sent: {tx_hash.hex()}")

                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash)
                    print(f"Wrap status: {'success' if receipt.status == 1 else 'failed'}")

                except Exception as e:
                    print(f"Error in wrap: {e}")

        except Exception as e:
            print(f"Error processing deposits: {e}")

    else:  # destination chain
        try:
            unwraps = dest_contract.events.Unwrap.create_filter(
                fromBlock=start_block, toBlock=end_block).get_all_entries()
            
            print(f"Found {len(unwraps)} Unwrap event(s)")
            for evt in unwraps:
                underlying_token = evt.args['underlying_token']
                wrapped_token = evt.args['wrapped_token']
                frm = evt.args['frm']
                to = evt.args['to']
                amount = evt.args['amount']

                print(f"\nProcessing Unwrap:")
                print(f"From: {frm}")
                print(f"To: {to}")
                print(f"Underlying token: {underlying_token}")
                print(f"Wrapped token: {wrapped_token}")
                print(f"Amount: {amount}")

                try:
                    # First, approve wrapped token for burning
                    wrapped_token_contract = dest_w3.eth.contract(address=wrapped_token, abi=ERC20_ABI)
                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    gas_price = min(dest_w3.eth.gas_price, 10000000000)

                    # Approve wrapped token for burning
                    approve_txn = wrapped_token_contract.functions.approve(
                        dest_contract.address, amount
                    ).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 100000,
                        'gasPrice': gas_price,
                        'nonce': nonce
                    })

                    signed_approve = dest_w3.eth.account.sign_transaction(approve_txn, private_key)
                    approve_hash = dest_w3.eth.send_raw_transaction(signed_approve.rawTransaction)
                    print(f"Approve transaction sent: {approve_hash.hex()}")
                    dest_w3.eth.wait_for_transaction_receipt(approve_hash)

                    # Now unwrap
                    nonce = dest_w3.eth.get_transaction_count(account_address)
                    txn = dest_contract.functions.unwrap(wrapped_token, to, amount).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': gas_price,
                        'nonce': nonce
                    })

                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Unwrap transaction sent: {tx_hash.hex()}")

                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash)
                    print(f"Unwrap status: {'success' if receipt.status == 1 else 'failed'}")

                    # Now handle withdraw on source chain
                    nonce = source_w3.eth.get_transaction_count(account_address)
                    withdraw_txn = source_contract.functions.withdraw(
                        underlying_token, to, amount
                    ).build_transaction({
                        'chainId': source_w3.eth.chain_id,
                        'gas': 200000,
                        'gasPrice': min(source_w3.eth.gas_price, 10000000000),
                        'nonce': nonce
                    })

                    signed_withdraw = source_w3.eth.account.sign_transaction(withdraw_txn, private_key)
                    withdraw_hash = source_w3.eth.send_raw_transaction(signed_withdraw.rawTransaction)
                    print(f"Withdraw transaction sent: {withdraw_hash.hex()}")

                    withdraw_receipt = source_w3.eth.wait_for_transaction_receipt(withdraw_hash)
                    print(f"Withdraw status: {'success' if withdraw_receipt.status == 1 else 'failed'}")

                except Exception as e:
                    print(f"Error in unwrap/withdraw: {str(e)}")

        except Exception as e:
            print(f"Error processing unwraps: {str(e)}")
