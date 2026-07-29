from src.utils import get_sql_connection

c = get_sql_connection()
cur = c.cursor()

cur.execute("""
    SELECT corpus_table_version, eu_chunk_ids[0]
    FROM ai_governance.compliance_navigator.assessment_log
    WHERE system_name = 'Claims Triage Model' AND synthesis_status = 'ok'
    ORDER BY created_at DESC LIMIT 1
""")
v, cid = cur.fetchone()
print("version:", v, "| chunk:", cid)

cur.execute(f"""
    SELECT LEFT(chunk_text, 200)
    FROM ai_governance.compliance_navigator.regulatory_chunks VERSION AS OF {v}
    WHERE chunk_id = '{cid}'
""")
print("--- text that assessment saw ---")
print(cur.fetchone()[0])

cur.close()
c.close()