### Description
The production news curation pipeline is crashing with a `TypeError` because the `Article` dataclass expects a `published` field which is missing from the dictionary returned by the curation stage.

### Traceback
```
  File "/home/runner/work/BluBot/BluBot/bot.py", line 54, in curation_stage
    articles = [Article(**item) for item in raw_news]
TypeError: Article.__init__() missing 1 required positional argument: 'published'
```

### Root Cause
In `src/curator.py`, the entry parsing logic correctly calculates `pub_date` but fails to include it in the final `item` dictionary passed to the orchestrator.

### Proposed Fix
Include the `published` key (formatted as a string) in the `item` dictionary within `src/curator.py:fetch_single_feed`.
