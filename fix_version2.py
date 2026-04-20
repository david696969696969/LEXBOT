with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_code = "elif existing['version'] < doc.version:"
new_code = "elif int(existing['version']) < doc.version:"

if old_code in content:
    content = content.replace(old_code, new_code)
    with open("main.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Исправлено!")
else:
    print("Не найдено")
