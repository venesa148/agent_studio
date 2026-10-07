with open("app/services/builder_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(85, min(130, len(lines))):
    print(f"{i+1}: {lines[i]}", end="")
