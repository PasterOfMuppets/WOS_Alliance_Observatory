# TODO – foundry regression fixes

1. **✅ DONE - Restore legion info in player history payload**
   - File: `app/src/observatory/api.py` (player_history route around lines 408‑414).
   - Reintroduce the `legion_id` field on each foundry participation entry so `templates/roster.html` can keep rendering "Legion {n}`. Pull the legion number from `fr.foundry_event.legion_number` (or the equivalent attribute already on the related model). Confirm the response schema still matches the `PlayerFoundryHistory` Pydantic model if one exists.

2. **✅ DONE - Keep `/api/events/foundry/{event_id}/results` compatible with UI**
   - File: `app/src/observatory/api.py` (results endpoint around lines 617‑671).
   - Continue accepting the `legion` query parameter the events page sends (default to `None`). When provided, filter the SQL query accordingly so `/results?legion=1` works instead of returning FastAPI 422 errors.
   - Include `legion_id` (or `legion_number`) per result record in the JSON payload so `templates/events_foundry.html` can keep displaying "Legion {result.legion_id}`. Make sure both the ORM query and response schema supply this field.

3. **✅ DONE - Add legion data back to foundry no‑shows**
   - File: `app/src/observatory/api.py` (no‑shows endpoint around lines 724‑729).
   - Each no‑show entry should again contain `legion_id` derived from the player's signup (`signup.foundry_event.legion_number`). Without it the UI prints `Legion undefined`. Update any response models to include the field.

4. **✅ DONE - Regression coverage**
   - Add or update tests under `tests/observatory` (mirroring the module path) to assert that the three endpoints return `legion_id` and still honor the `legion` filter. This prevents future API/UI drift.
