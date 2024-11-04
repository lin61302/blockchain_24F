from web3 import Web3
from eth_account import Account
import eth_account
import os

def get_keys(challenge, filename="eth_mnemonic.txt"):
    """
    Retrieve the private key from a file, sign the given challenge,
    and return the signature along with the associated Ethereum address.

    Parameters:
    - challenge (bytes): The byte string to sign.
    - filename (str): Filename to read the private key.

    Returns:
    - tuple: (signature (str), address (str))
    """

    w3 = Web3()

    msg = eth_account.messages.encode_defunct(challenge)

    # Check if the private key file exists
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Private key file '{filename}' not found.")

    # Read the private key from the file
    with open(filename, "r") as f:
        private_key = f.read().strip()

    # Create an account instance from the private key
    acct = Account.from_key(private_key)

    # Get the Ethereum address
    eth_addr = acct.address

    # Sign the challenge message
    sig = acct.sign_message(msg)

    # Verify the signature
    recovered_addr = Account.recover_message(msg, signature=sig.signature.hex())
    assert recovered_addr == eth_addr, "Failed to sign message properly"

    # Return the signature (as a hex string) and the Ethereum address
    return sig.signature.hex(), eth_addr

if __name__ == "__main__":
    # Only run once since there's only one private key
    challenge = os.urandom(64)
    try:
        sig, addr = get_keys(challenge=challenge)
        print(f"Address: {addr}")
        print(f"Signature: {sig}\n")
    except Exception as e:
        print(f"Error: {e}\n")
