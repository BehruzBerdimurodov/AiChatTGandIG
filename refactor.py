import os
import re

db_functions = [
    "get_hotel", "update_hotel", "get_rooms", "get_room", "add_room", 
    "update_room", "delete_room", "register_user", "get_user", 
    "update_user", "get_user_count", "get_all_users", "get_user_ids", 
    "create_order", "get_orders", "get_order", "update_order", 
    "get_orders_count", "get_revenue", "get_admins", "add_admin", 
    "remove_admin", "is_admin", "get_channels", "add_channel", 
    "remove_channel", "get_post_channel", "set_post_channel", 
    "log_message", "log_activity", "get_daily_stats", 
    "get_monthly_stats", "init_db"
]

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    # For every db function, replace `func(` with `await func(` if it's not already preceded by `await ` or `def `.
    for func in db_functions:
        # Regex explanation: 
        # Negative lookbehind for `await ` or `def ` or `async def `
        # Match the word boundary, function name, and opening parenthesis
        pattern = r'(?<!await\s)(?<!def\s)(?<!async def\s)\b' + func + r'\s*\('
        
        # We need to be careful with imports like `from config.database import get_hotel`
        # Those don't have parenthesis usually.
        # But wait, what if it's `result = get_hotel()`? Then it will be matched.
        content = re.sub(pattern, f'await {func}(', content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Refactored {filepath}")

def main():
    base_dir = r"c:\Users\Behruz Lab\Desktop\AiChatTGandIG"
    
    # Process run.py
    run_py = os.path.join(base_dir, "run.py")
    if os.path.exists(run_py):
        refactor_file(run_py)
        
    # Process app and bot folders
    for folder in ["app", "bot"]:
        folder_path = os.path.join(base_dir, folder)
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    refactor_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
