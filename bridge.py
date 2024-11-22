from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path

contract_info = "contract_info.json"
WARDEN_ROLE = "0xa95a5379b182f9ab2dea1336b28c22442227353b86d7e0a968f68d98add11c07"

# Add approval method to BridgeToken ABI
BRIDGE_TOKEN_ABI = [
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
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
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

    WARDEN = "0x634D745F4f3d26759Dd6836Ba25B16Ba3050d3D6"  # Your address
    RECIPIENT = "0x6E346B1277e545c5F4A9BB602A220B34581D068B"  # Recipient address
    WRAPPED_TOKEN = "0x87D6538156aF81C500aaeEB6e61ceDfA04DE5e67"  # Known wrapped token

    if chain == 'source':
        # Handle Deposit -> Wrap
        end_block = source_w3.eth.block_number
        start_block = max(0, end_block - 5)
        print(f"Scanning blocks {start_block} - {end_block}")

        try:
            deposits = source_contract.events.Deposit.create_filter(
                fromBlock=start_block, toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(deposits)} Deposit event(s)")
            
            for evt in deposits:
                token = evt.args['token']
                recipient = evt.args['recipient']
                amount = evt.args['amount']

                # Send wrap transaction
                nonce = dest_w3.eth.get_transaction_count(WARDEN)
                txn = dest_contract.functions.wrap(
                    token, recipient, amount
                ).build_transaction({
                    'chainId': dest_w3.eth.chain_id,
                    'gas': 200000,
                    'gasPrice': min(dest_w3.eth.gas_price, 10000000000),
                    'nonce': nonce
                })

                signed = source_w3.eth.account.sign_transaction(txn, source_info['private_key'])
                tx_hash = dest_w3.eth.send_raw_transaction(signed.rawTransaction)
                print(f"Wrap tx: {tx_hash.hex()}")

        except Exception as e:
            print(f"Error in wrap: {e}")

    else:
        # Handle Unwrap -> Withdraw
        end_block = dest_w3.eth.block_number
        start_block = max(0, end_block - 5)
        print(f"Scanning blocks {start_block} - {end_block}")

        try:
            # First approve wrapped tokens
            token_contract = dest_w3.eth.contract(address=WRAPPED_TOKEN, abi=BRIDGE_TOKEN_ABI)
            
            try:
                # Check allowance
                allowance = token_contract.functions.allowance(RECIPIENT, dest_contract.address).call()
                print(f"Current allowance: {allowance}")

                if allowance == 0:
                    # Try to approve
                    nonce = dest_w3.eth.get_transaction_count(RECIPIENT)
                    approve_txn = token_contract.functions.approve(
                        dest_contract.address,
                        2**256 - 1  # max uint256
                    ).build_transaction({
                        'chainId': dest_w3.eth.chain_id,
                        'gas': 100000,
                        'gasPrice': min(dest_w3.eth.gas_price, 10000000000),
                        'nonce': nonce,
                        'from': RECIPIENT
                    })
                    
                    signed = dest_w3.eth.account.sign_transaction(approve_txn, dest_info['private_key'])
                    tx_hash = dest_w3.eth.send_raw_transaction(signed.rawTransaction)
                    print(f"Approval tx: {tx_hash.hex()}")
            except Exception as e:
                print(f"Error in approval: {e}")

            # Now handle Unwrap events
            unwraps = dest_contract.events.Unwrap.create_filter(
                fromBlock=start_block, toBlock=end_block
            ).get_all_entries()

            print(f"Found {len(unwraps)} Unwrap event(s)")
            
            for evt in unwraps:
                underlying_token = evt.args['underlying_token']
                to = evt.args['to']
                amount = evt.args['amount']

                print(f"\nProcessing Unwrap:")
                print(f"To: {to}")
                print(f"Amount: {amount}")

                # Send withdraw transaction
                nonce = source_w3.eth.get_transaction_count(WARDEN)
                txn = source_contract.functions.withdraw(
                    underlying_token,
                    to,
                    amount
                ).build_transaction({
                    'chainId': source_w3.eth.chain_id,
                    'gas': 200000,
                    'gasPrice': min(source_w3.eth.gas_price, 10000000000),
                    'nonce': nonce
                })

                signed = source_w3.eth.account.sign_transaction(txn, source_info['private_key'])
                tx_hash = source_w3.eth.send_raw_transaction(signed.rawTransaction)
                print(f"Withdraw tx: {tx_hash.hex()}")

        except Exception as e:
            print(f"Error in unwrap: {e}")
