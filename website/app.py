from flask import Flask, render_template, request, redirect, url_for, flash, session
from users import User
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key
user_manager = User()

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/getin', methods=["GET", "POST"])
def getin():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        # First check if user exists by email
        user = user_manager.get_user_by_email(email)
        
        if user:
            # User exists, attempt login
            result = user_manager.login(user['username'], password)
            if result['success']:
                session['user'] = result['user']
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash(result['message'], 'error')
        else:
            # User doesn't exist, attempt registration
            # Generate username from email
            username = email.split('@')[0]
            result = user_manager.register(username, email, password)
            if result['success']:
                # Auto login after registration
                login_result = user_manager.login(username, password)
                if login_result['success']:
                    session['user'] = login_result['user']
                    flash('Registration and login successful!', 'success')
                    return redirect(url_for('index'))
            else:
                flash(result['message'], 'error')
                
    return render_template('getin.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin', methods=["GET", "POST"])
def admin():
    # Check if user is logged in as admin
    if 'user' not in session or session['user']['username'] != ADMIN_USERNAME:
        flash('Admin access required.', 'error')
        return redirect(url_for('getin'))

    if request.method == "POST":
        action = request.form.get('action')
        username = request.form.get('username')
        
        if action == 'delete':
            result = user_manager.delete_user(username)
            flash(result['message'], 'success' if result['success'] else 'error')
        elif action == 'toggle_active':
            user = user_manager.get_user_by_username(username)
            if user:
                new_status = not user['is_active']
                result = user_manager.update_user(username, is_active=new_status)
                flash(result['message'], 'success' if result['success'] else 'error')

    # Get all users for display
    users = user_manager.get_all_users()
    return render_template('admin.html', users=users)

if __name__ == '__main__':
    app.run(debug=True)