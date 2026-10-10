"""Election Night's readers: one module per family of results feed (readers/<family>.py).

Each reader turns one fetched or hand-saved file (or one set of files saved together) into a "reading", the shape
election.store.record checks and stores. A reader keeps only the fields it names (an allowlist); contact columns are
never read or printed. Every request goes through election.source.
"""
