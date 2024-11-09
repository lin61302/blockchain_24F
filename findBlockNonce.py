#!/bin/python
import hashlib
import os
import random

def count_trailing_zero_bits(hash_bytes):
    """
        Counts the number of trailing zero bits in the binary representation of the hash.

        Args:
            hash_bytes (bytes): The SHA256 hash in bytes.

        Returns:
            int: Number of trailing zero bits.
    """
    binary_str = bin(int.from_bytes(hash_bytes, byteorder='big'))[2:].zfill(256)
    

    return len(binary_str) - len(binary_str.rstrip('0'))

def mine_block(k, prev_hash, rand_lines):
    """
        k - Number of trailing zeros in the binary representation (integer)
        prev_hash - the hash of the previous block (bytes)
        rand_lines - a set of "transactions," i.e., data to be included in this block (list of strings)

        Complete this function to find a nonce such that 
        sha256( prev_hash + rand_lines + nonce )
        has k trailing zeros in its *binary* representation
    """
    if not isinstance(k, int) or k < 0:
        print("mine_block expects positive integer")
        return b'\x00'

    # TODO your code to find a nonce here
    transactions_bytes = ''.join(rand_lines).encode('utf-8')

    block_data = prev_hash + transactions_bytes

    nonce = 0
    
    while True:
        try:
            nonce_bytes = nonce.to_bytes(8, byteorder='big')  # 8 bytes = 64 bits
        except OverflowError:
            print("Nonce has exceeded the maximum value for 8 bytes.")
            return b'\x00'

        hash_result = hashlib.sha256(block_data + nonce_bytes).digest()
        trailing_zeros = count_trailing_zero_bits(hash_result)
        if trailing_zeros >= k:
            # Valid nonce found
            return nonce_bytes
        
        nonce += 1




def get_random_lines(filename, quantity):
    """
    This is a helper function to get the quantity of lines ("transactions")
    as a list from the filename given. 
    Do not modify this function
    """
    lines = []
    with open(filename, 'r') as f:
        for line in f:
            lines.append(line.strip())

    random_lines = []
    for x in range(quantity):
        if len(lines) == 0:
            break  # Prevent IndexError if the file is empty
        random_index = random.randint(0, len(lines) - 1)
        random_lines.append(lines[random_index])
    return random_lines

def verify_nonce(k, prev_hash, rand_lines, nonce):
    """
        Verifies that the given nonce produces a hash with at least k trailing zero bits.

        Args:
            k (int): Number of trailing zero bits required.
            prev_hash (bytes): Previous block hash.
            rand_lines (list of str): Transaction lines.
            nonce (bytes): The nonce to verify.

        Returns:
            bool: True if valid, False otherwise.
    """
    transactions_bytes = ''.join(rand_lines).encode('utf-8')
    
    block_data = prev_hash + transactions_bytes + nonce
    
    hash_result = hashlib.sha256(block_data).digest()
    
    trailing_zeros = count_trailing_zero_bits(hash_result)
    
    return trailing_zeros >= k


if __name__ == '__main__':
    # This code will be helpful for your testing
    filename = "bitcoin_text.txt"
    num_lines = 10  # The number of "transactions" included in the block

    # The "difficulty" level. For our blocks this is the number of Least Significant Bits
    # that are 0s. For example, if diff = 5 then the last 5 bits of a valid block hash would be zeros
    # The grader will not exceed 20 bits of "difficulty" because larger values take to long
    k = 20

    rand_lines = get_random_lines(filename, num_lines)
    prev_hash = b'\x00' * 32

    # rand_lines = get_random_lines(filename, num_lines)
    nonce = mine_block(k, prev_hash, rand_lines)
    print(f"Valid Nonce Found: {nonce.hex()}")

    is_valid = verify_nonce(k, prev_hash, rand_lines, nonce)
    print(f"Nonce Verification: {'Passed' if is_valid else 'Failed'}")
