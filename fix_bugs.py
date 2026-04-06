"""
Loyihadagi barcha xatolarni avtomatik tuzatuvchi script
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def read(path):
    with open(os.path.join(BASE, path), 'r', encoding='utf-8') as f:
        return f.readlines()

def write(path, lines):
    with open(os.path.join(BASE, path), 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)
    print(f"  [SAVED] {path}")

# ============================================================
# FIX 1: database.py - Dead code o'chirish (433-441 qatorlar)
# find_available_rooms ichida return dan keyingi SQL blok
# ============================================================
print("\n[FIX 1] database.py - Dead unreachable code after return...")
lines = read('config/database.py')
new_lines = []
i = 0
while i < len(lines):
    stripped = lines[i].strip()
    # 432-qator (0-indexed: 431): "    return available"
    if stripped == 'return available' and i >= 430 and i <= 435:
        new_lines.append(lines[i])
        i += 1
        # keyingi 9 qatorni o'tkazib yubor (dead code)
        skipped = 0
        while i < len(lines) and skipped < 9:
            next_stripped = lines[i].strip()
            # Bo'sh qator yoki keyingi funksiya boshlansa to'xta
            if next_stripped.startswith('async def ') or next_stripped.startswith('def '):
                break
            new_lines.append('')  # empty line instead, so we don't shift numbers too much
            # Actually just skip
            new_lines.pop()  # remove the empty we just added
            i += 1
            skipped += 1
        print(f"  Skipped {skipped} dead code lines after 'return available'")
        continue
    new_lines.append(lines[i])
    i += 1
write('config/database.py', new_lines)

# ============================================================
# FIX 2: admin.py - Duplicate decorator/handler qatorlarni o'chirish
# Line 17: from config.database import is_admin  (duplicate - line 19 ham bor)
# Line 798: @router.message(ChannelState.waiting) duplicate decorator
# Line 1053: @router.callback_query(...) duplicate decorator
# Line 1104-1105: duplicate decorators
# Line 1127: duplicate decorator
# Line 1191: payload = {"type": "text", "text": ""} duplicate
# ============================================================
print("\n[FIX 2] admin.py - Duplicate imports and decorators...")
lines = read('bot/handlers/admin.py')
new_lines = []
i = 0
removed = []

while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    lineno = i + 1  # 1-indexed

    # FIX 2a: Duplicate 'from config.database import is_admin' (line 17)
    if lineno == 17 and stripped == 'from config.database import is_admin':
        removed.append(f"Line {lineno}: duplicate import '{stripped}'")
        i += 1
        continue

    # FIX 2b: Duplicate @router.message(ChannelState.waiting) decorator (line 798)
    if lineno == 798 and stripped == '@router.message(ChannelState.waiting)':
        removed.append(f"Line {lineno}: duplicate decorator")
        i += 1
        continue

    # FIX 2c: Duplicate @router.callback_query(F.data == "available_rooms") (line 1053)
    if lineno == 1053 and '@router.callback_query' in stripped and 'available_rooms' in stripped:
        removed.append(f"Line {lineno}: duplicate decorator")
        i += 1
        continue

    # FIX 2d: Duplicate @router.message(AvailabilityState.waiting) lines 1104,1105
    if lineno in (1104, 1105) and '@router.message(AvailabilityState.waiting)' in stripped:
        removed.append(f"Line {lineno}: duplicate decorator")
        i += 1
        continue

    # FIX 2e: Duplicate @router.callback_query(F.data == "start_message") (line 1127)
    if lineno == 1127 and '@router.callback_query' in stripped and 'start_message' in stripped:
        removed.append(f"Line {lineno}: duplicate decorator")
        i += 1
        continue

    # FIX 2f: Duplicate payload = {"type": "text", "text": ""} (line 1191)
    if lineno == 1191 and 'payload' in stripped and '"type": "text"' in stripped:
        removed.append(f"Line {lineno}: duplicate payload initialization")
        i += 1
        continue

    new_lines.append(line)
    i += 1

for r in removed:
    print(f"  Removed: {r}")
write('bot/handlers/admin.py', new_lines)

# ============================================================
# FIX 3: app/main.py - Duplicate /webhook/telegram handler
# main.py da 2 ta /webhook/telegram endpoint bor (190 va 350-qatorlar)
# Ikkinchisi eskisi va noto'g'ri (bot_token query param orqali)
# ============================================================
print("\n[FIX 3] app/main.py - Duplicate /webhook/telegram endpoint...")
lines = read('app/main.py')
new_lines = []
i = 0
found_first_webhook = False
removed_second = False

while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    if '@app.post("/webhook/telegram")' in stripped or "@app.post('/webhook/telegram')" in stripped:
        if not found_first_webhook:
            found_first_webhook = True
            new_lines.append(line)
            i += 1
            continue
        else:
            # Second one - skip it and its function body
            print(f"  Removing duplicate /webhook/telegram at line {i+1}")
            removed_second = True
            i += 1
            # Skip the function body until next @app route or end
            while i < len(lines):
                next_stripped = lines[i].strip()
                # Stop if we hit another route or end of webhook block
                if next_stripped.startswith('@app.') or next_stripped.startswith('class ') or next_stripped.startswith('async def ') and not lines[i].startswith('    '):
                    break
                i += 1
            continue

    new_lines.append(line)
    i += 1

if not removed_second:
    print("  No duplicate found (may have been fixed already)")
write('app/main.py', new_lines)

# ============================================================
# Verify all files compile
# ============================================================
print("\n[VERIFY] Syntax check...")
import py_compile, sys
files = [
    'config/database.py',
    'bot/handlers/admin.py',
    'app/main.py',
    'app/ai_handler.py',
    'bot/handlers/user.py',
]
all_ok = True
for f in files:
    path = os.path.join(BASE, f)
    try:
        py_compile.compile(path, doraise=True)
        print(f"  OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"  ERROR: {f} -> {e}")
        all_ok = False

print("\n" + ("All files OK!" if all_ok else "Some files have errors!"))
