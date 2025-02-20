from flask import Flask, jsonify, request
from flask_pymongo import PyMongo
from flask_cors import CORS
import bcrypt

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/insightHub"
mongo = PyMongo(app)
CORS(app)

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        if mongo.db.users.find_one({'username': username}):
            return jsonify({'error': 'Username already exists'}), 400

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=10))
        mongo.db.users.insert_one({
            'username': username,
            'password': hashed.decode('utf-8')
        })

        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': 'Error registering user'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        user = mongo.db.users.find_one({'username': username})
        if not user:
            return jsonify({'error': 'Invalid username or password'}), 400

        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'message': 'Login successful'}), 200
        return jsonify({'error': 'Invalid username or password'}), 400
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Error logging in'}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)