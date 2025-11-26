# Fix accounts.html proxy display issue

with open('pages/accounts.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the problematic line
old_code = "                    const proxyText = acc.proxy ? `${acc.proxy.host}:${acc.proxy.port}` : '-';"

new_code = """                    // Handle proxy display - check if proxy exists and has required fields
                    let proxyText = '-';
                    if (acc.proxy && acc.proxy.host && acc.proxy.port) {
                        proxyText = `${acc.proxy.host}:${acc.proxy.port}`;
                    }"""

content = content.replace(old_code, new_code)

with open('pages/accounts.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Fixed proxy display in accounts.html")
