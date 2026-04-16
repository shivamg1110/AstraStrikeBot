from flask import Flask, request, jsonify
import subprocess
import os
import re

app = Flask(__name__)

def auto_pip(code):
    # Code se libraries extract karna
    imports = re.findall(r"^(?:import|from)\s+([\w\d]+)", code, re.MULTILINE)
    # List of pre-installed or standard libs to skip
    skip_libs = ['os', 'sys', 're', 'time', 'json', 'random', 'math', 'subprocess', 'flask']
    
    for lib in imports:
        if lib not in skip_libs:
            try:
                # Agar koi nayi library ho toh install kar lo
                subprocess.check_call(['pip', 'install', lib])
            except:
                pass

@app.route('/execute', methods=['POST'])
def execute_code():
    data = request.json
    code = data.get('code', '')
    
    if not code:
        return jsonify({"output": "No code provided!"})

    # Extra safety: Install if anything is missing
    auto_pip(code)
    
    # User ka script save karna
    with open("temp_script.py", "w") as f:
        f.write(code)
    
    try:
        # 15 seconds ka timeout taaki server hang na ho
        result = subprocess.run(
            ['python3', 'temp_script.py'], 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        
        # Output capture karna
        stdout = result.stdout
        stderr = result.stderr
        
        final_output = stdout if stdout else stderr
        if not final_output:
            final_output = "Script executed successfully (No output)."
            
    except subprocess.TimeoutExpired:
        final_output = "❌ Timeout: Script took too long to execute (>15s)."
    except Exception as e:
        final_output = str(e)
    
    return jsonify({"output": final_output})

if __name__ == "__main__":
    # Render ke port par run karna
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
