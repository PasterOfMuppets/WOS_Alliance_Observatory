-- Check for duplicate contribution snapshots
SELECT
    alliance_id,
    player_id,
    week_start_date,
    snapshot_date,
    COUNT(*) as duplicate_count
FROM contribution_snapshots
GROUP BY alliance_id, player_id, week_start_date, snapshot_date
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC
LIMIT 20;
