import secrets
print(f"PG_PROD={secrets.token_hex(24)}")
print(f"REDIS_PROD={secrets.token_hex(24)}")
print(f"PG_DEV={secrets.token_hex(24)}")
print(f"REDIS_DEV={secrets.token_hex(24)}")
