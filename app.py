from flask import Flask, request, jsonify
import subprocess
import os
import re

app = Flask(__name__)

# List of libraries that should NEVER be pip installed
BUILT_IN_LIBS = [
    'os', 'sys', 're', 'time', 'json', 'random', 'math', 
    'subprocess', 'threading', 'base64', 'hashlib', 'datetime'
]

def auto_pip(code):
    imports = re.findall(r"^(?:import|from)\s+([\w\d]+)", code, re.MULTILINE)
    
    for lib in imports:
        # Agar built-in nahi hai aur standard list mein nahi hai, tabhi install kare
        if lib not in BUILT_IN_LIBS:
            try:
                subprocess.check_call(['pip', 'install', lib])
            except:
                pass

@app.route('/execute', methods=['POST'])
def execute_code():
    data = request.json
    code = data.get('code', '')
    
    if not code:
        return jsonify({"output": "❌ No code provided!"})

    auto_pip(code)
    
    with open("temp_script.py", "w") as f:
        f.write(code)
    
    try:
        result = subprocess.run(
            ['python3', 'temp_script.py'], 
            capture_output=True, 
            text=True, 
            timeout=25
        )
        final_output = result.stdout if result.stdout else result.stderr
    except Exception as e:
        final_output = f"❌ Error: {str(e)}"
    
    return jsonify({"output": final_output})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
