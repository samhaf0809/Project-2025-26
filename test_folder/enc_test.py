import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import hashlib


master_pass = str(input("Enter the master pasword: "))
print(master_pass)
hash_master_pass = hashlib.sha512(master_pass.encode()).digest()

print(hash_master_pass)


