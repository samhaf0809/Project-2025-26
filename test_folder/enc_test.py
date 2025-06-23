import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import hashlib

def hasher_old():
    master_pass = str(input("Enter the master pasword: "))
    print(master_pass)
    hash_master_pass = hashlib.sha512(master_pass.encode()).hexdigest()
    return hash_master_pass

def hasher(passw):
    hash_master_pass = hashlib.sha512(passw.encode()).hexdigest()
    return hash_master_pass

if __name__ == "__main__":
    print(hasher_old())
