-- Check alembic migration status
SELECT * FROM alembic_version;

-- Check for duplicate foundry signups
SELECT foundry_event_id, player_id, COUNT(*) as count
FROM foundry_signups
GROUP BY foundry_event_id, player_id
HAVING COUNT(*) > 1
ORDER BY count DESC
LIMIT 20;

-- Check for duplicate foundry results
SELECT foundry_event_id, player_id, COUNT(*) as count
FROM foundry_results
GROUP BY foundry_event_id, player_id
HAVING COUNT(*) > 1
ORDER BY count DESC
LIMIT 20;

-- Check if unique constraints exist
SELECT sql FROM sqlite_master
WHERE type='table' AND name='foundry_signups';

SELECT sql FROM sqlite_master
WHERE type='table' AND name='foundry_results';
