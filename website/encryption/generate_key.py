from cryptography.fernet import Fernet

def generate_key(filename):
    key = Fernet.generate_key()
    key_filename = f"{filename}.key"  # Save key with filename
    with open(key_filename, "wb") as key_file:
        key_file.write(key)
    
    print(f"🔑 Encryption key generated and saved as '{key_filename}'!")

if __name__ == "__main__":
    filename = input("Enter the filename (with extension) for which you want to generate a key: ")
    generate_key(filename)
