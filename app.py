from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def execute_code():
    data = request.json
    code = data.get('code')
    
    # Save the user's code temporarily
    with open("temp_script.py", "w") as f:
        f.write(code)
    
    try:
        # Execute the script and capture output
        result = subprocess.run(['python3', 'temp_script.py'], capture_output=True, text=True, timeout=10)
        output = result.stdout if result.stdout else result.stderr
    except Exception as e:
        output = str(e)
    
    return jsonify({"output": output})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
