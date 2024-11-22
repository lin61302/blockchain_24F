from web3 import Web3
from web3.contract import Contract
from web3.providers.rpc import HTTPProvider
from web3.middleware import geth_poa_middleware #Necessary for POA chains
import json
import sys
from pathlib import Path

source_chain = 'avax'
destination_chain = 'bsc'
contract_info = "contract_info.json"

def connectTo(chain):
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['avax','bsc']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def getContractInfo(chain):
    """
        Load the contract_info file into a dictinary
        This function is used by the autograder and will likely be useful to you
    """
    p = Path(__file__).with_name(contract_info)
    try:
        with p.open('r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( "Failed to read contract info" )
        print( "Please contact your instructor" )
        print( e )
        sys.exit(1)

    return contracts[chain]



def scanBlocks(chain):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return
    
        #YOUR CODE HERE
    # Map chain names to actual chain IDs
    if chain == 'source':
        chain_name = source_chain  # 'avax'
        other_chain_name = destination_chain  # 'bsc'
    else:
        chain_name = destination_chain  # 'bsc'
        other_chain_name = source_chain  # 'avax'

    # Connect to both chains
    w3 = connectTo(chain_name)
    w3_other = connectTo(other_chain_name)

    # Load contract info for both chains
    contract_info_chain = getContractInfo(chain_name)
    contract_info_other_chain = getContractInfo(other_chain_name)

    # Get contract addresses and ABIs
    contract_address = contract_info_chain['contract_address']
    contract_abi = contract_info_chain['contract_abi']

    contract_address_other = contract_info_other_chain['contract_address']
    contract_abi_other = contract_info_other_chain['contract_abi']

    # Load private key and account address for signing transactions on the other chain
    private_key = contract_info_other_chain['private_key']  # Private key for the account with permissions
    account_address = contract_info_other_chain['public_key']  # Public address of the account

    # Now, get the latest block number on the chain
    latest_block = w3.eth.blockNumber

    # Set the block range to scan
    start_block = latest_block - 5 if latest_block >= 5 else 0
    end_block = latest_block

    print(f"Scanning blocks {start_block} - {end_block} on {chain_name}")

    # Load the contracts
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    contract_other = w3_other.eth.contract(address=contract_address_other, abi=contract_abi_other)

    # Depending on the chain, look for specific events
    if chain == 'source':
        # Look for 'Deposit' events
        # Deposit(address indexed token, address indexed recipient, uint256 amount)
        event_filter = contract.events.Deposit.createFilter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()
        for evt in events:
            # Get event data
            token = evt.args['token']
            recipient = evt.args['recipient']
            amount = evt.args['amount']
            tx_hash = evt.transactionHash.hex()
            print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}, tx_hash={tx_hash}")

            # Now, call wrap() function on the destination chain
            # wrap(address _underlying_token, address _recipient, uint256 _amount)
            # Build transaction
            nonce = w3_other.eth.getTransactionCount(account_address)
            txn = contract_other.functions.wrap(token, recipient, amount).buildTransaction({
                'chainId': w3_other.eth.chain_id,
                'gas': 500000,
                'gasPrice': w3_other.toWei('10', 'gwei'),
                'nonce': nonce,
            })
            # Sign transaction
            signed_txn = w3_other.eth.account.signTransaction(txn, private_key=private_key)
            # Send transaction
            tx_hash = w3_other.eth.sendRawTransaction(signed_txn.rawTransaction)
            print(f"wrap() transaction sent on {other_chain_name}: tx_hash={tx_hash.hex()}")

    else:
        # chain == 'destination'
        # Look for 'Unwrap' events
        # Unwrap(address indexed underlying_token, address indexed wrapped_token, address frm, address indexed to, uint256 amount)
        event_filter = contract.events.Unwrap.createFilter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()
        for evt in events:
            # Get event data
            underlying_token = evt.args['underlying_token']
            wrapped_token = evt.args['wrapped_token']
            frm = evt.args['frm']
            to = evt.args['to']
            amount = evt.args['amount']
            tx_hash = evt.transactionHash.hex()
            print(f"Found Unwrap event: underlying_token={underlying_token}, wrapped_token={wrapped_token}, frm={frm}, to={to}, amount={amount}, tx_hash={tx_hash}")

            # Now, call withdraw() function on the source chain
            # withdraw(address _token, address _recipient, uint256 _amount)
            # Build transaction
            nonce = w3_other.eth.getTransactionCount(account_address)
            txn = contract_other.functions.withdraw(underlying_token, to, amount).buildTransaction({
                'chainId': w3_other.eth.chain_id,
                'gas': 500000,
                'gasPrice': w3_other.toWei('10', 'gwei'),
                'nonce': nonce,
            })
            # Sign transaction
            signed_txn = w3_other.eth.account.signTransaction(txn, private_key=private_key)
            # Send transaction
            tx_hash = w3_other.eth.sendRawTransaction(signed_txn.rawTransaction)
            print(f"withdraw() transaction sent on {other_chain_name}: tx_hash={tx_hash.hex()}")

