import eth_account
import random
import string
import json
from pathlib import Path
from web3 import Web3
from web3.middleware import geth_poa_middleware  # Necessary for POA chains
# from sympy import primerange

def is_prime(n):
    """Check if a number is prime."""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def merkle_assignment():
    """
        The only modifications you need to make to this method are to assign
        your "random_leaf_index" and uncomment the last line when you are
        ready to attempt to claim a prime. You will need to complete the
        methods called by this method to generate the proof.
    """
    # Generate the list of primes as integers
    num_of_primes = 8192
    primes = generate_primes(num_of_primes)

    # Create a version of the list of primes in bytes32 format
    leaves = convert_leaves(primes)

    # Build a Merkle tree using the bytes32 leaves as the Merkle tree's leaves
    tree = build_merkle(leaves)

    # Select a random leaf and create a proof for that leaf
    random_leaf_index = select_unclaimed_leaf_index(leaves) #TODO generate a random index from primes to claim (0 is already claimed)
    if random_leaf_index is None:
        print("No unclaimed leaves available.")
        return

    proof = prove_merkle(tree, random_leaf_index)

    selected_leaf = leaves[random_leaf_index]

    # This is the same way the grader generates a challenge for sign_challenge()
    challenge = ''.join(random.choice(string.ascii_letters) for i in range(32))
    # Sign the challenge to prove to the grader you hold the account
    addr, sig = sign_challenge(challenge)

    if sign_challenge_verify(challenge, addr, sig):
        tx_hash = '0x'
        # TODO, when you are ready to attempt to claim a prime (and pay gas fees),
        #  complete this method and run your code with the following line un-commented
        # tx_hash = send_signed_msg(proof, leaves[random_leaf_index])
        tx_hash = send_signed_msg(proof, selected_leaf)
        print(f"Transaction successful with hash: {tx_hash}")
    else:
        print("Signature verification failed.")

def select_unclaimed_leaf_index(leaves):
    """
        Selects a random unclaimed leaf index.

        Args:
            leaves (list): List of bytes32 leaves.

        Returns:
            int or None: Index of an unclaimed leaf or None if all are claimed.
    """
    chain = 'bsc'
    w3 = connect_to(chain)
    address, abi = get_contract_info(chain)
    contract = w3.eth.contract(address=address, abi=abi)

    indices = list(range(len(leaves)))
    random.shuffle(indices)

    for idx in indices:
        # Convert bytes32 to integer
        prime_int = int.from_bytes(leaves[idx], byteorder='big')
        owner = contract.functions.getOwnerByPrime(prime_int).call()
        if owner == '0x0000000000000000000000000000000000000000':
            
            return idx # Leaf is unclaimed

    return None



def generate_primes(num_primes):
    """
        Function to generate the first 'num_primes' prime numbers
        returns list (with length n) of primes (as ints) in ascending order
    """
    primes_list = []

    #TODO YOUR CODE HERE

    # current = 2 

    # while len(primes_list) < num_primes:
    #     next_primes = list(primerange(current, current * 2))
    #     primes_list.extend(next_primes)
    #     current = primes_list[-1] + 1  # Update current to the next number after the last prime found

    # return primes_list[:num_primes]
    num = 2
    while len(primes_list) < num_primes:
        if is_prime(num):
            primes_list.append(num)
        num += 1
    return primes_list


def convert_leaves(primes_list):
    """
        Converts the leaves (primes_list) to bytes32 format
        returns list of primes where list entries are bytes32 encodings of primes_list entries
    """

    # TODO YOUR CODE HERE

    bytes32_leaves = []
    for prime in primes_list:
        # Calculate the minimum number of bytes needed to represent the prime
        byte_length = (prime.bit_length() + 7) // 8
    
        prime_bytes = prime.to_bytes(byte_length, byteorder='big')

        # Pad with leading zeros to make it 32 bytes
        padded_prime = prime_bytes.rjust(32, b'\x00')

        bytes32_leaves.append(padded_prime)

    return bytes32_leaves


def build_merkle(leaves):
    """
        Function to build a Merkle Tree from the list of prime numbers in bytes32 format
        Returns the Merkle tree (tree) as a list where tree[0] is the list of leaves,
        tree[1] is the parent hashes, and so on until tree[n] which is the root hash
        the root hash produced by the "hash_pair" helper function
    """

    #TODO YOUR CODE HERE
    tree = []
    current_level = leaves.copy()
    tree.append(current_level)

    while len(current_level) > 1:
        next_level = []

        # If the number of nodes is odd, duplicate the last node
        if len(current_level) % 2 != 0:
            current_level.append(current_level[-1])

        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1]
            parent = hash_pair(left, right)
            next_level.append(parent)

        tree.append(next_level)
        current_level = next_level

    return tree


def prove_merkle(merkle_tree, random_indx):
    """
        Takes a random_index to create a proof of inclusion for and a complete Merkle tree
        as a list of lists where index 0 is the list of leaves, index 1 is the list of
        parent hash values, up to index -1 which is the list of the root hash.
        returns a proof of inclusion as list of values
    """
    merkle_proof = []
    # TODO YOUR CODE HERE
    index = random_indx

    for level in merkle_tree[:-1]:  # Exclude the root level
        
        if index % 2 == 0: # Determine sibling index
            sibling_index = index + 1
        else:
            sibling_index = index - 1

        if sibling_index >= len(level):
            sibling_index = index  # Duplicate if no sibling

        sibling = level[sibling_index]
        merkle_proof.append(sibling)

        # Move to the next level
        index = index // 2

    return merkle_proof



def sign_challenge(challenge):
    """
        Takes a challenge (string)
        Returns address, sig
        where address is an ethereum address and sig is a signature (in hex)
        This method is to allow the auto-grader to verify that you have
        claimed a prime
    """
    acct = get_account()

    addr = acct.address
    eth_sk = acct.key

    # TODO YOUR CODE HERE
    eth_encoded_msg = eth_account.messages.encode_defunct(text=challenge)
    eth_sig_obj = acct.sign_message(eth_encoded_msg)

    return addr, eth_sig_obj.signature.hex()


def send_signed_msg(proof, random_leaf):
    """
        Takes a Merkle proof of a leaf, and that leaf (in bytes32 format)
        builds signs and sends a transaction claiming that leaf (prime)
        on the contract
    """
    chain = 'bsc'

    acct = get_account()
    address, abi = get_contract_info(chain)
    w3 = connect_to(chain)

    # TODO YOUR CODE HERE
    # Initialize contract
    contract = w3.eth.contract(address=address, abi=abi)

    # Convert proof to list of hex strings
    # proof_hex = [p.hex() for p in proof]
    proof_bytes32 = proof
    leaf_bytes32 = random_leaf

    leaf_hex = random_leaf.hex()

    try:
        gas_estimate = contract.functions.submit(proof_bytes32, leaf_bytes32).estimateGas({
            'from': acct.address
        })
        txn = contract.functions.submit(proof_bytes32, leaf_bytes32).build_transaction({
            'from': acct.address,
            'nonce': w3.eth.get_transaction_count(acct.address),
            'gas': gas_estimate + 10000,  # Add buffer to gas estimate
            'gasPrice': w3.toWei('5', 'gwei')  
        })
    except Exception as e:
        print(f"Gas estimation failed: {e}")
        return '0x'

    signed_txn = acct.sign_transaction(txn)
    try:
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(f"Transaction sent with hash: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        print(f"Transaction failed: {e}")
        return '0x'


# Helper functions that do not need to be modified
def connect_to(chain):
    """
        Takes a chain ('avax' or 'bsc') and returns a web3 instance
        connected to that chain.
    """
    if chain not in ['avax','bsc']:
        print(f"{chain} is not a valid option for 'connect_to()'")
        return None
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    else:
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet
    w3 = Web3(Web3.HTTPProvider(api_url))
    # inject the poa compatibility middleware to the innermost layer
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    return w3


def get_account():
    """
        Returns an account object recovered from the secret key
        in "sk.txt"
    """
    cur_dir = Path(__file__).parent.absolute()
    with open(cur_dir.joinpath('sk.txt'), 'r') as f:
        sk = f.readline().rstrip()
    # if sk[0:2] == "0x":
    #     sk = sk[2:]
    # return eth_account.Account.from_key(sk)
    if sk.startswith("0x"):
        sk = sk[2:]
    return eth_account.Account.from_key(bytes.fromhex(sk))


def get_contract_info(chain):
    """
        Returns a contract address and contract abi from "contract_info.json"
        for the given chain
    """
    cur_dir = Path(__file__).parent.absolute()
    with open(cur_dir.joinpath("contract_info.json"), "r") as f:
        d = json.load(f)
        d = d[chain]
    return d['address'], d['abi']


def sign_challenge_verify(challenge, addr, sig):
    """
        Helper to verify signatures, verifies sign_challenge(challenge)
        the same way the grader will. No changes are needed for this method
    """
    eth_encoded_msg = eth_account.messages.encode_defunct(text=challenge)

    if eth_account.Account.recover_message(eth_encoded_msg, signature=sig) == addr:
        print(f"Success: signed the challenge {challenge} using address {addr}!")
        return True
    else:
        print(f"Failure: The signature does not verify!")
        print(f"signature = {sig}\naddress = {addr}\nchallenge = {challenge}")
        return False


def hash_pair(a, b):
    """
        The OpenZeppelin Merkle Tree Validator we use sorts the leaves
        https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/MerkleProof.sol#L217
        So you must sort the leaves as well

        Also, hash functions like keccak are very sensitive to input encoding, so the solidity_keccak function is the function to use

        Another potential gotcha, if you have a prime number (as an int) bytes(prime) will *not* give you the byte representation of the integer prime
        Instead, you must call int.to_bytes(prime,'big').
    """
    if a < b:
        return Web3.solidity_keccak(['bytes32', 'bytes32'], [a, b])
    else:
        return Web3.solidity_keccak(['bytes32', 'bytes32'], [b, a])


if __name__ == "__main__":
    merkle_assignment()
