import os
from cryptography.fernet import Fernet

# Load key specific to a file
def load_key(filename):
    key_filename = f"{filename}.key"
    if not os.path.exists(key_filename):
        print(f"❌ Error: Key file '{key_filename}' not found! Skipping {filename}.")
        return None
    return open(key_filename, "rb").read()

# Encrypt a single file
def encrypt_file(filename):
    if not os.path.exists(filename):
        print(f"❌ Error: File '{filename}' not found! Skipping.")
        return
    
    key = load_key(filename)
    if key is None:
        return
    
    f = Fernet(key)

    with open(filename, "rb") as file:
        file_data = file.read()
    
    encrypted_data = f.encrypt(file_data)

    encrypted_filename = filename + ".enc"
    with open(encrypted_filename, "wb") as file:
        file.write(encrypted_data)

    print(f"✅ File encrypted successfully: {encrypted_filename}")

if __name__ == "__main__":
    files = input("Enter filenames to encrypt (comma-separated): ").split(",")

    for file in files:
        file = file.strip()  # Remove extra spaces
        encrypt_file(file)
