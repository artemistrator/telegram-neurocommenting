# Script to add subscriber link to layout.html and catch-all route to main.py

# 1. Add subscriber link to layout.html
with open('layout.html', 'r', encoding='utf-8') as f:
    layout_content = f.read()

# Find the accounts link and add subscriber after it
accounts_link = '''            <a href="#" class="menu-item flex items-center px-4 py-3 rounded-lg mb-2 text-white no-underline"
                data-page="accounts">
                <span class="text-xl mr-3">👤</span>
                <span>Аккаунты</span>
            </a>'''

subscriber_link = '''            <a href="#" class="menu-item flex items-center px-4 py-3 rounded-lg mb-2 text-white no-underline"
                data-page="accounts">
                <span class="text-xl mr-3">👤</span>
                <span>Аккаунты</span>
            </a>
            <a href="#" class="menu-item flex items-center px-4 py-3 rounded-lg mb-2 text-white no-underline"
                data-page="subscriber">
                <span class="text-xl mr-3">🚀</span>
                <span>Автоподписка</span>
            </a>'''

layout_content = layout_content.replace(accounts_link, subscriber_link)

with open('layout.html', 'w', encoding='utf-8') as f:
    f.write(layout_content)

print("✓ Subscriber link added to layout.html")

# 2. Add catch-all route to main.py
with open('main.py', 'r', encoding='utf-8') as f:
    main_content = f.read()

catch_all_route = '''

# ============================================
# SPA ROUTING - Catch-all for page refreshes
# ============================================

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    """Catch-all route for SPA routing - returns layout.html for all non-API/static paths"""
    # Ignore API and static paths
    if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("pages"):
        raise HTTPException(status_code=404)
    
    # All other paths (home, accounts, subscriber, etc.) return layout
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


if __name__ == "__main__":'''

main_content = main_content.replace('\nif __name__ == "__main__":', catch_all_route)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(main_content)

print("✓ Catch-all route added to main.py")
print("\nBoth fixes applied successfully!")
