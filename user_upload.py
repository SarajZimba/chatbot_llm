from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from helper_func import get_db_connection

user_bp = Blueprint('user', __name__, url_prefix='/user')

# ------------------------------
# Register User
# ------------------------------
@user_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    iframe_id = str(uuid.uuid4())
    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password, iframe_id) VALUES (%s, %s, %s)",
            (username, hashed_password, iframe_id)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": "Username might already exist"}), 400

    cursor.close()
    conn.close()
    return jsonify({"username": username, "iframe_id": iframe_id})


# ------------------------------
# Login User
# ------------------------------
@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not check_password_hash(user['password'], password):
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"username": username, "iframe_id": user['iframe_id']})


# ------------------------------
# Update Password
# ------------------------------
@user_bp.route('/update-password', methods=['POST'])
def update_password():
    data = request.get_json()
    username = data.get('username')
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not username or not old_password or not new_password:
        return jsonify({"error": "Username, old password and new password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['password'], old_password):
        cursor.close()
        conn.close()
        return jsonify({"error": "Invalid username or old password"}), 401

    hashed_new_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password=%s WHERE username=%s", (hashed_new_password, username))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Password updated successfully"})


# ------------------------------
# Delete User
# ------------------------------
@user_bp.route('/delete', methods=['POST'])
def delete_user():
    data = request.get_json()
    userid = data.get('user_id')
    # password = data.get('password')

    if not userid:
        return jsonify({"error": "Username is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    # user = cursor.fetchone()

    # if not user or not check_password_hash(user['password'], password):
    #     cursor.close()
    #     conn.close()
    #     return jsonify({"error": "Invalid username or password"}), 401

    cursor.execute("DELETE FROM users WHERE user_id=%s", (userid,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": f"User '{userid}' deleted successfully"})
