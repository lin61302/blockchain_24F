from web3 import Web3
from eth_account.messages import encode_defunct
import random
import os

def signChallenge( challenge ):

    w3 = Web3()

    #This is the only line you need to modify
    # sk = os.getenv('PRIVATE_KEY')
    sk = '474d7cf21cb5cd83119901130c7f72ce9102cfa418ccb20aeb91df29708a3943'
    if not sk:
        raise Exception("Private key not found in environment variables.")

    acct = w3.eth.account.from_key(sk)

    signed_message = w3.eth.account.sign_message( challenge, private_key = acct._private_key )

    return acct.address, signed_message.signature


def verifySig():
    """
        This is essentially the code that the autograder will use to test signChallenge
        We've added it here for testing 
    """

    challenge_bytes = random.randbytes(32)

    challenge = encode_defunct(challenge_bytes)
    address, sig = signChallenge( challenge )

    w3 = Web3()

    return w3.eth.account.recover_message( challenge , signature=sig ) == address

if __name__ == '__main__':
    """
        Test your function
    """
    if verifySig():
        print( f"You passed the challenge!" )
    else:
        print( f"You failed the challenge!" )

