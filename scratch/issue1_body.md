### Description
The production post-news workflow is currently crashing with a TypeError.

### Traceback
```
File "/home/runner/work/BluBot/BluBot/bot.py", line 54, in curation_stage
  articles = [Article(**item) for item in raw_news]
TypeError: Article.__init__() got an unexpected keyword argument '_score_debug'
```

### Root Cause
The `curator.py` logic injects diagnostic metadata (`_score_debug`) into article dictionaries for scoring transparency, but the `Article` frozen dataclass in `src/models.py` does not define this field.

### Proposed Fix
Add `_score_debug: Optional[Dict[str, Any]] = None` to the `Article` dataclass in `src/models.py`.
