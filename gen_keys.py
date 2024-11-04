# gen_keys.py

from web3 import Web3
from eth_account import Account
import eth_account
import os
from mnemonic import Mnemonic
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
from dotenv import load_dotenv

# Load environment variables from .env file (if using)
load_dotenv()

def get_keys(challenge, keyId=0, filename="eth_mnemonic.txt"):
    """
    Retrieve the mnemonic from a file, derive the private key based on keyId,
    sign the given challenge, and return the signature along with the associated Ethereum address.

    Parameters:
    - challenge (bytes): The byte string to sign.
    - keyId (int): Index of the mnemonic to use (0-based).
    - filename (str): Filename to read the mnemonic phrases.

    Returns:
    - tuple: (signature (str), address (str))
    """
    
    # Encode the challenge as an Ethereum message
    msg = eth_account.messages.encode_defunct(challenge)

    # Check if the mnemonic file exists
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Mnemonic file '{filename}' not found.")

    # Read all mnemonics from the file
    with open(filename, "r") as f:
        mnemonics = [line.strip() for line in f.readlines() if line.strip()]

    # Ensure the keyId is within the range of available mnemonics
    if keyId >= len(mnemonics):
        raise IndexError(f"keyId {keyId} is out of range. Only {len(mnemonics)} mnemonic(s) available.")

    # Select the mnemonic based on keyId
    mnemonic = mnemonics[keyId]

    # Validate the mnemonic
    mnemo = Mnemonic("english")
    if not mnemo.check(mnemonic):
        raise ValueError(f"The mnemonic at keyId {keyId} is invalid.")

    # Derive the seed from the mnemonic
    seed = Bip39SeedGenerator(mnemonic).Generate()

    # Initialize BIP44 for Ethereum
    bip44_mst = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
    bip44_acc = bip44_mst.Purpose().Coin().Account(0)
    bip44_change = bip44_acc.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr = bip44_change.AddressIndex(keyId)

    # Get the private key in hex format
    private_key = bip44_addr.PrivateKey().Raw().ToHex()

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
