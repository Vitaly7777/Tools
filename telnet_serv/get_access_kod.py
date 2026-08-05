import os

ACCESS_CODE = os.getenv('TELNET_ACCESS', '').strip()
if __name__ == "__main__":
    print(ACCESS_CODE)
