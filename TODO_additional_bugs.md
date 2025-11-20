# TODO – user reported bugs & enhancements

1. **✅ DONE - Include screenshot filename in upload logs**
   - Current logs only show "Player not found … skipping bear score" without telling which uploaded file triggered the warning. Update the upload handler (likely `app/src/observatory/api_upload.py` or equivalent) to log the manifest entry or screenshot filename alongside the player info so we can trace problematic OCR results.

2. **✅ DONE - Fuzzy-match player names when not found**
   - When OCR misreads a player name we currently just skip the entry. Implement fuzzy matching (e.g., `difflib.get_close_matches` or another scorer) against known player names to attempt automatic recovery when the miss is within a small distance. Log both the original OCR text and the matched canonical name so we can audit the decision, and fall back to the existing warning if no close match is found.

3. **Weekly contribution summary UX**  
   - The weekly contribution view should mimic the bear events UI: show a summary block with aggregate stats (e.g., number of participants) for the week, plus an expandable section to reveal the detailed player list. Update the relevant template / API payload to supply the totals.

4. **Legion roster collapsing**  
   - Allow the legion roster list to be collapsed/expanded per legion in the UI so users can hide long player lists when browsing multiple legions.

5. **Show legion event timestamp in UTC**  
   - Add the event’s UTC time to the legion view (and ensure the API shares the timestamp if it is not already exposed) so users can see when each legion event occurred without guessing the timezone.
