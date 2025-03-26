import os
from cryptography.fernet import Fernet
from typing import Dict, Optional, Tuple

class VideoEncryption:
    def __init__(self, key_path: Optional[str] = None):
        """
        Initialize VideoEncryption with optional existing key.
        
        Args:
            key_path: Path to existing key file. If None, new key will be generated.
        """
        self.key = None
        self.key_path = key_path
        
        if key_path and os.path.exists(key_path):
            self._load_key()
        else:
            self._generate_key()

    def _generate_key(self) -> None:
        """Generate a new encryption key."""
        self.key = Fernet.generate_key()
        if self.key_path:
            with open(self.key_path, 'wb') as key_file:
                key_file.write(self.key)

    def _load_key(self) -> None:
        """Load an existing encryption key."""
        try:
            with open(self.key_path, 'rb') as key_file:
                self.key = key_file.read()
        except Exception as e:
            raise Exception(f"Error loading key: {str(e)}")

    def save_key(self, key_path: str) -> Dict[str, bool | str]:
        """
        Save the current encryption key to a file.
        
        Args:
            key_path: Path where to save the key
            
        Returns:
            Dictionary with operation status and message
        """
        try:
            with open(key_path, 'wb') as key_file:
                key_file.write(self.key)
            return {
                'success': True,
                'message': f"Key saved to {key_path}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error saving key: {str(e)}"
            }

    def encrypt_file(self, input_path: str, output_path: Optional[str] = None) -> Dict[str, bool | str]:
        """
        Encrypt a video file.
        
        Args:
            input_path: Path to the video file to encrypt
            output_path: Path where to save encrypted file. If None, appends '.enc'
            
        Returns:
            Dictionary with operation status and message
        """
        try:
            if not os.path.exists(input_path):
                return {
                    'success': False,
                    'message': f"Input file not found: {input_path}"
                }

            if not self.key:
                return {
                    'success': False,
                    'message': "No encryption key available"
                }

            # Set default output path if none provided
            if not output_path:
                output_path = f"{input_path}.enc"

            # Initialize Fernet cipher
            fernet = Fernet(self.key)

            # Read and encrypt the file
            with open(input_path, 'rb') as file:
                file_data = file.read()

            # Encrypt the data
            encrypted_data = fernet.encrypt(file_data)

            # Write the encrypted file
            with open(output_path, 'wb') as file:
                file.write(encrypted_data)

            return {
                'success': True,
                'message': f"File encrypted successfully: {output_path}",
                'output_path': output_path
            }

        except Exception as e:
            return {
                'success': False,
                'message': f"Encryption error: {str(e)}"
            }

    def decrypt_file(self, input_path: str, output_path: Optional[str] = None) -> Dict[str, bool | str]:
        """
        Decrypt an encrypted video file.
        
        Args:
            input_path: Path to the encrypted file
            output_path: Path where to save decrypted file. If None, removes '.enc'
            
        Returns:
            Dictionary with operation status and message
        """
        try:
            if not os.path.exists(input_path):
                return {
                    'success': False,
                    'message': f"Input file not found: {input_path}"
                }

            if not self.key:
                return {
                    'success': False,
                    'message': "No decryption key available"
                }

            # Set default output path if none provided
            if not output_path:
                output_path = input_path.replace('.enc', '') if input_path.endswith('.enc') else f"{input_path}.dec"

            # Initialize Fernet cipher
            fernet = Fernet(self.key)

            # Read and decrypt the file
            with open(input_path, 'rb') as file:
                encrypted_data = file.read()

            # Decrypt the data
            decrypted_data = fernet.decrypt(encrypted_data)

            # Write the decrypted file
            with open(output_path, 'wb') as file:
                file.write(decrypted_data)

            return {
                'success': True,
                'message': f"File decrypted successfully: {output_path}",
                'output_path': output_path
            }

        except Exception as e:
            return {
                'success': False,
                'message': f"Decryption error: {str(e)}"
            }

    def verify_encryption(self, original_path: str, encrypted_path: str) -> Dict[str, bool | str]:
        """
        Verify that a file was encrypted correctly by attempting to decrypt it.
        
        Args:
            original_path: Path to the original file
            encrypted_path: Path to the encrypted file
            
        Returns:
            Dictionary with verification status and message
        """
        try:
            # Create a temporary file for decryption test
            temp_decrypted = f"{encrypted_path}.temp"
            
            # Try to decrypt the file
            decrypt_result = self.decrypt_file(encrypted_path, temp_decrypted)
            if not decrypt_result['success']:
                return decrypt_result

            # Compare file sizes
            original_size = os.path.getsize(original_path)
            decrypted_size = os.path.getsize(temp_decrypted)

            # Clean up temporary file
            os.remove(temp_decrypted)

            if original_size == decrypted_size:
                return {
                    'success': True,
                    'message': "Encryption verified successfully"
                }
            else:
                return {
                    'success': False,
                    'message': "Encryption verification failed: size mismatch"
                }

        except Exception as e:
            if os.path.exists(temp_decrypted):
                os.remove(temp_decrypted)
            return {
                'success': False,
                'message': f"Verification error: {str(e)}"
            } 