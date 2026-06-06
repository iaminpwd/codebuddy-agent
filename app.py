import sqlite3
import pickle

# 하드코딩된 API 키 (OWASP 취약점)
API_KEY = "12345"

def add(a, b):
    # 비효율적인 연산 (복잡도/리팩토링 테스트)
    result = 0
    for i in range(b):
        result += 1
    return a + result

def get_user(id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # SQL Injection 취약점 (OWASP)
    query = f"SELECT * FROM users WHERE id = {id}"
    cursor.execute(query)
    return cursor.fetchall()

def load_data(data):
    # 안전하지 않은 역직렬화 (OWASP)
    return pickle.loads(data)
