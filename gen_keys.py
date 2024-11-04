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

	#YOUR CODE HERE
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Private key file '{filename}' not found.")

    with open(filename, "r") as f:
        private_key = f.read().strip()

    acct = Account.from_key(private_key)

    eth_addr = acct.address

    sig = acct.sign_message(msg)

    recovered_addr = Account.recover_message(msg, signature=sig.signature.hex())
    assert recovered_addr == eth_addr, "Failed to sign message properly"

    return sig.signature.hex(), eth_addr

    # assert eth_account.Account.recover_message(msg,signature=sig.signature.hex()) == eth_addr, f"Failed to sign message properly"

    #return sig, acct #acct contains the private key
    # return sig, eth_addr

if __name__ == "__main__":
    for i in range(4):
        challenge = os.urandom(64)
        sig, addr= get_keys(challenge=challenge,keyId=i)
        # print( addr )
        print(f"Address: {addr}")
        print(f"Signature: {sig}\n")
