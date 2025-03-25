import os
from cryptography.fernet import Fernet

# Load key specific to a file
def load_key(filename):
    key_filename = f"{filename}.key"
    if not os.path.exists(key_filename):
        print(f"❌ Error: Key file '{key_filename}' not found! Skipping {filename}.")
        return None
    return open(key_filename, "rb").read()

# Decrypt a single file
def decrypt_file(filename):
    if not os.path.exists(filename):
        print(f"❌ Error: File '{filename}' not found! Skipping.")
        return
    
    if not filename.endswith(".enc"):
        print(f"❌ Error: '{filename}' does not have '.enc' extension! Skipping.")
        return
    
    original_filename = filename.replace(".enc", "")
    key = load_key(original_filename)
    if key is None:
        return
    
    f = Fernet(key)

    with open(filename, "rb") as file:
        encrypted_data = file.read()
    
    decrypted_data = f.decrypt(encrypted_data)

    with open(original_filename, "wb") as file:
        file.write(decrypted_data)

    print(f"✅ File decrypted successfully: {original_filename}")

if __name__ == "__main__":
    files = input("Enter encrypted filenames to decrypt (comma-separated): ").split(",")

    for file in files:
        file = file.strip()  # Remove extra spaces
        decrypt_file(file)
