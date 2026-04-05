import os
import ast

def extract_functions(source_path, target_names):
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = ast.parse(source)
    imports_and_globals = []
    
    # Just grab all the imports and assignments at module level
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign)):
            imports_and_globals.append(ast.get_source_segment(source, node))
            
    # Also grab try/except that contains imports
    for node in tree.body:
        if isinstance(node, ast.Try):
            imports_and_globals.append(ast.get_source_segment(source, node))
            
    # Filter functions
    target_funcs = []
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
            if node.name in target_names or any(node.name.replace('_unlocked', '') == tgt for tgt in target_names):
                target_funcs.append(ast.get_source_segment(source, node))
                
    header = '"""Split DB Repository"""\n\n' + "\n".join(imports_and_globals)
    body = "\n\n".join(target_funcs)
    return header + "\n\n" + body + "\n"

# Define function blocks to extract
run_funcs = ['save_run', 'update_run']
trend_funcs = ['save_trend', 'get_trend_history', 'get_recent_trends', 'get_recently_processed_keywords', 
               'get_recently_processed_fingerprints', 'is_duplicate_trend', 'get_volume_velocity',
               'record_watchlist_hit', 'get_trend_history_patterns_batch', 'get_cached_score']
tweet_funcs = ['save_tweet', '_save_tweet_unlocked', 'save_thread', '_save_thread_unlocked', 'save_tweets_batch',
               '_resolve_tweet_row_id_for_publish', '_mark_tweet_posted_unlocked', 'mark_tweet_posted',
               '_sync_tweet_metrics_unlocked', 'sync_tweet_metrics', 'get_recent_tweet_contents',
               '_record_posting_time_stat_unlocked', 'record_posting_time_stat', 'get_best_posting_hours',
               'get_cached_content']
metrics_funcs = ['_record_source_quality_unlocked', 'record_source_quality', 'get_source_quality_summary']
draft_funcs = ['record_content_feedback', '_record_content_feedback_unlocked', 'get_qa_summary', 'get_content_hashes',
               '_json_text', '_json_list', 'record_trend_quarantine', 'save_validated_trend', 'save_draft_bundle',
               'get_draft_bundle', 'update_draft_bundle_status', 'save_qa_report', 'promote_draft_to_ready',
               'save_review_decision', 'record_publish_receipt', 'record_feedback_summary', 'attach_draft_to_notion_page',
               'get_review_queue_snapshot']
admin_funcs = ['_cleanup_old_records_unlocked', 'cleanup_old_records', 'get_trend_stats', 'get_meta', '_set_meta_unlocked', 'set_meta', 'get_recent_avg_viral_score']

db_file = 'automation/getdaytrends/db.py'

base_dir = 'automation/getdaytrends/db_layer'

with open(f'{base_dir}/__init__.py', 'w', encoding='utf-8') as f:
    f.write('"""DB Repositories Layer"""\n')

with open(f'{base_dir}/run_repository.py', 'w', encoding='utf-8') as f:
    f.write(extract_functions(db_file, run_funcs))

with open(f'{base_dir}/trend_repository.py', 'w', encoding='utf-8') as f:
    f.write(extract_functions(db_file, trend_funcs))
    
with open(f'{base_dir}/tweet_repository.py', 'w', encoding='utf-8') as f:
    f.write(extract_functions(db_file, tweet_funcs))
    
with open(f'{base_dir}/metrics_repository.py', 'w', encoding='utf-8') as f:
    f.write(extract_functions(db_file, metrics_funcs))

with open(f'{base_dir}/draft_repository.py', 'w', encoding='utf-8') as f:
    f.write(extract_functions(db_file, draft_funcs))
    
with open(f'{base_dir}/admin_repository.py', 'w', encoding='utf-8') as f:
    f.write(extract_functions(db_file, admin_funcs))

print("Created repository files.")
