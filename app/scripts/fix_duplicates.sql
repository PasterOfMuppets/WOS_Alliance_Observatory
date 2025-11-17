-- Step 1: Normalize dates to midnight UTC
UPDATE contribution_snapshots
SET snapshot_date = datetime(date(snapshot_date)),
    week_start_date = datetime(date(week_start_date));

-- Step 2: Delete duplicates, keeping the earliest created_at for each unique combination
DELETE FROM contribution_snapshots
WHERE id NOT IN (
    SELECT MIN(id)
    FROM contribution_snapshots
    GROUP BY alliance_id, player_id, week_start_date, snapshot_date
);

-- Step 3: Verify no duplicates remain
SELECT
    alliance_id,
    player_id,
    week_start_date,
    snapshot_date,
    COUNT(*) as duplicate_count
FROM contribution_snapshots
GROUP BY alliance_id, player_id, week_start_date, snapshot_date
HAVING COUNT(*) > 1;
