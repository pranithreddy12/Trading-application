import os
import glob

def fix_jsonb():
    # Find all python files
    py_files = []
    for root, dirs, files in os.walk('.'):
        if '.gemini' in root or 'node_modules' in root or '.git' in root or 'venv' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
                
    fixed = 0
    for file in py_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            orig = content
            # Replace parameter casts
            content = content.replace('CAST(:meta AS jsonb)', 'CAST(:meta AS jsonb)')
            content = content.replace('CAST(:details AS jsonb)', 'CAST(:details AS jsonb)')
            content = content.replace('CAST(:reasons AS jsonb)', 'CAST(:reasons AS jsonb)')
            content = content.replace('CAST(:parameters AS jsonb)', 'CAST(:parameters AS jsonb)')
            
            # Replace literal default casts
            content = content.replace("CAST('{}' AS jsonb)", "CAST('{}' AS jsonb)")
            content = content.replace("CAST('[]' AS jsonb)", "CAST('[]' AS jsonb)")
            content = content.replace("'{\"retired\": true}'::jsonb", "CAST('{\"retired\": true}' AS jsonb)")
            
            if orig != content:
                with open(file, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed += 1
                print(f"Fixed {file}")
        except Exception as e:
            pass
            
    print(f"Total files fixed: {fixed}")

if __name__ == '__main__':
    fix_jsonb()
