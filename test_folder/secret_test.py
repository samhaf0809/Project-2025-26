import secrets

# Generate a random integer from 0 to 99
random_number = secrets.randbelow(100)
print(random_number)

token1 = secrets.token_bytes()
token2 = secrets.token_bytes(10)
token3 = secrets.token_hex()
token4 = secrets.token_hex(10)


print(token1)
print(token2)
print(token3)
print(token4)
print(type(token1))
print(type(token3))
print(int(token1,2)) # doesnt work stick to hex
print(int(token3,16))
