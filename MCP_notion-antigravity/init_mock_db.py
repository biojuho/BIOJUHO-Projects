import sqlite3
import pandas as pd
import numpy as np
import datetime
import os

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/analytics.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS post_history (
                id INTEGER PRIMARY KEY,
                generated_at TEXT,
                post_type TEXT,
                keyword TEXT,
                viral_score INTEGER,
                status TEXT,
                hook TEXT
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS trend_analytics (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                keyword TEXT,
                viral_potential INTEGER,
                search_volume INTEGER
            )''')
c.execute('DELETE FROM post_history')
c.execute('DELETE FROM trend_analytics')

# Insert mock data
now = datetime.datetime.now()
for i in range(25):
    gen_at = now - datetime.timedelta(days=np.random.randint(0, 14), hours=np.random.randint(0, 24))
    c.execute('INSERT INTO post_history (generated_at, post_type, keyword, viral_score, status, hook) VALUES (?, ?, ?, ?, ?, ?)',
              (gen_at.strftime('%Y-%m-%d %H:%M:%S'), 'tweet', 'AI', np.random.randint(40, 95), 'published' if np.random.rand() > 0.2 else 'draft', 'The future varies by perspective.'))

for i in range(8):
    c.execute('INSERT INTO trend_analytics (timestamp, keyword, viral_potential, search_volume) VALUES (?, ?, ?, ?)',
              (now.strftime('%Y-%m-%d %H:%M:%S'), f'Tech Trend {i}', np.random.randint(50, 100), np.random.randint(1000, 5000)))
conn.commit()
conn.close()
print("Mock db populated.")
