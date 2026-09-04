import os
import re

os.makedirs('sql_new', exist_ok=True)

with open('main.sql', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to split the content based on the file markers
pattern = r'(-- ==========================================================\s*\n-- File: .+\.sql\s*\n-- ==========================================================)'
parts = re.split(pattern, content)

for i in range(1, len(parts), 2):
    marker = parts[i]
    body = parts[i+1] if i+1 < len(parts) else ""
    m = re.search(r'-- File:\s*(.+\.sql)', marker)
    if m:
        filename = m.group(1).strip()
        filepath = os.path.join('sql_new', filename)
        with open(filepath, 'w', encoding='utf-8') as out:
            out.write(marker)
            out.write(body)
        print(f"Created {filepath}")
