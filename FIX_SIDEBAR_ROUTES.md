# КРИТИЧЕСКИ ВАЖНО: Добавить эти роуты в main.py

## Найти строку 119-123 (роут GET "/"):

```python
# Get HTML page
@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)
```

## ЗАМЕНИТЬ НА:

```python
# Get HTML page
@app.get("/", response_class=HTMLResponse)
async def get_layout():
    """Return layout with sidebar navigation"""
    with open("layout.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/pages/{page}", response_class=HTMLResponse)
async def get_page(page: str):
    """Return individual page content"""
    try:
        page_path = os.path.join("pages", f"{page}.html")
        with open(page_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Page '{page}' not found")
```

## ПОСЛЕ ЭТОГО:

1. Перезапустить сервер (Ctrl+C, затем python main.py)
2. Открыть http://localhost:8000
3. Должен показаться layout с sidebar
4. Навигация должна работать
