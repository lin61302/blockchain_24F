from web3 import Web3
from eth_account import Account
import eth_account
import os

def get_keys(challenge,keyId = 0, filename = "eth_mnemonic.txt"):
    """
    Generate a stable private key
    challenge - byte string
    keyId (integer) - which key to use
    filename - filename to read and store mnemonics

    Each mnemonic is stored on a separate line
    If fewer than (keyId+1) mnemonics have been generated, generate a new one and return that
    """

    w3 = Web3()

    msg = eth_account.messages.encode_defunct(challenge)

    # Determine the absolute path to the private_key.txt file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)

    # Check if the private key file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Private key file '{filename}' not found in {script_dir}.")

    # Read all private keys from the file, each on a separate line
    with open(file_path, "r") as f:
        private_keys = [line.strip() for line in f if line.strip()]

    # Ensure the keyId is within the range of available private keys
    if keyId >= len(private_keys):
        raise IndexError(f"keyId {keyId} is out of range. Only {len(private_keys)} private key(s) available.")

    # Select the private key based on keyId
    private_key = private_keys[keyId]

    # Create an account instance from the private key
    acct = Account.from_key(private_key)

    # Get the Ethereum address
    eth_addr = acct.address

    # Sign the challenge message
    sig = acct.sign_message(msg)

    # Verify the signature
    recovered_addr = Account.recover_message(msg, signature=sig.signature.hex())
    assert recovered_addr == eth_addr, "Failed to sign message properly"

    # Return the signature object and the Ethereum address
    return sig, eth_addr
