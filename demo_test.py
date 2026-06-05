import sqlite3
# 하드코딩된 API Key (보안 취약점 테스트용)
API_SECRET_KEY = "sk-proj-1234567890abcdef"
def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # SQL Injection에 노출된 쿼리 (리뷰어 코멘트 대상)
    query = f"SELECT * FROM accounts WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchall()
