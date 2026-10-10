"""Election Night: official results as each state's election office posts them, the feed and the forecasts.

The plan is election/ARCHITECTURE.md. This package holds the results store (store.py), the one gate every request
goes through (source.py), the state registry and crosswalks, and the readers (readers/<family>.py). Nothing here
writes to the ballot or record databases; they are read only.
"""
