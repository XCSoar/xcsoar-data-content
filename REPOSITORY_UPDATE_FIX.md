# Repository Update Field Fix

## Problem
The `update=` field was being updated daily due to a bug in the `git_commit_datetime()` function. The function had a broken line that always caused an exception, falling back to `datetime.datetime.now()` and ignoring JSON metadata.

## Root Cause
1. **Broken parsing**: `NewDate = datetime.datetime(out)` was incorrect
2. **Daily fallback**: Exception always triggered, returning today's date
3. **Ignored JSON**: JSON `update:` fields were not being read

## Solution
1. **Fixed git_commit_datetime**: Removed broken line
2. **Added json_update()**: Reads JSON update fields with "daily" support
3. **Added get_update_date()**: Uses JSON with git fallback
4. **Updated generators**: All functions now use proper update logic

## New Features
- **"daily" value support**: If JSON contains `"update": "daily"`, returns today's date
- **Proper fallback**: Uses git commit timestamp only when JSON is unavailable
- **Comprehensive tests**: Full test suite for all new functionality

## Testing
Run tests with: `./run_tests.sh`

## Files Changed
- `script/build/repository.py`: Main fixes and new functions
- `tests/test_repository.py`: Comprehensive test suite
- `run_tests.sh`: Test runner script