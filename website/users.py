import sqlite3
import hashlib
import os
from typing import Optional, Dict, Any

class User:
    def __init__(self, db_path: str = 'users.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()

    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash the password using SHA-256 with salt."""
        if salt is None:
            salt = os.urandom(32).hex()
        
        # Combine password and salt
        salted_password = f"{password}{salt}"
        # Create hash
        password_hash = hashlib.sha256(salted_password.encode()).hexdigest()
        
        return password_hash, salt

    def register(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user.
        Returns a dictionary with success status and message.
        """
        try:
            # Check if username or email already exists
            if self.get_user_by_username(username):
                return {"success": False, "message": "Username already exists"}
            if self.get_user_by_email(email):
                return {"success": False, "message": "Email already exists"}

            # Hash password and generate salt
            password_hash, salt = self._hash_password(password)

            # Insert new user
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, salt)
            )
            conn.commit()
            conn.close()

            return {"success": True, "message": "User registered successfully"}
        except Exception as e:
            return {"success": False, "message": f"Registration failed: {str(e)}"}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user.
        Returns a dictionary with success status, message, and user data if successful.
        """
        try:
            # Get user data
            user = self.get_user_by_username(username)
            if not user:
                return {"success": False, "message": "Invalid username or password"}

            # Verify password
            password_hash, _ = self._hash_password(password, user['salt'])
            if password_hash != user['password_hash']:
                return {"success": False, "message": "Invalid username or password"}

            # Update last login
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?",
                (username,)
            )
            conn.commit()
            conn.close()

            # Remove sensitive data before returning
            user_data = {k: v for k, v in user.items() if k not in ['password_hash', 'salt']}
            return {"success": True, "message": "Login successful", "user": user_data}
        except Exception as e:
            return {"success": False, "message": f"Login failed: {str(e)}"}

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user data by username."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'password_hash': user[3],
                'salt': user[4],
                'created_at': user[5],
                'last_login': user[6],
                'is_active': user[7]
            }
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user data by email."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'password_hash': user[3],
                'salt': user[4],
                'created_at': user[5],
                'last_login': user[6],
                'is_active': user[7]
            }
        return None

    def get_all_users(self) -> list[Dict[str, Any]]:
        """Get all users (excluding sensitive data)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        conn.close()

        return [{
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'created_at': user[5],
            'last_login': user[6],
            'is_active': user[7]
        } for user in users]

    def update_user(self, username: str, **kwargs) -> Dict[str, Any]:
        """
        Update user information.
        Available fields: email, is_active
        """
        try:
            user = self.get_user_by_username(username)
            if not user:
                return {"success": False, "message": "User not found"}

            allowed_fields = {'email', 'is_active'}
            update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

            if not update_fields:
                return {"success": False, "message": "No valid fields to update"}

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            set_clause = ", ".join(f"{k} = ?" for k in update_fields)
            values = list(update_fields.values())
            values.append(username)
            
            cursor.execute(
                f"UPDATE users SET {set_clause} WHERE username = ?",
                values
            )
            
            conn.commit()
            conn.close()

            return {"success": True, "message": "User updated successfully"}
        except Exception as e:
            return {"success": False, "message": f"Update failed: {str(e)}"}

    def delete_user(self, username: str) -> Dict[str, Any]:
        """Delete a user by username."""
        try:
            user = self.get_user_by_username(username)
            if not user:
                return {"success": False, "message": "User not found"}

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            conn.close()

            return {"success": True, "message": "User deleted successfully"}
        except Exception as e:
            return {"success": False, "message": f"Deletion failed: {str(e)}"}

# Example usage:
if __name__ == "__main__":
    user_manager = User()
    
    # Register a new user
    result = user_manager.register("testuser", "test@example.com", "password123")
    print("Registration:", result)
    
    # Login
    result = user_manager.login("testuser", "password123")
    print("Login:", result)
    
    # Get all users
    users = user_manager.get_all_users()
    print("All users:", users)